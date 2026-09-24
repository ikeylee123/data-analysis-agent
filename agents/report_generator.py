import json
import math
import os
import re
from datetime import datetime

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()


class ReportGeneratorAgent:
    INVALID_API_KEY_VALUES = {"", "your_api_key_here", "your_google_api_key_here"}
    MAX_JSON_CHARS = 20000

    def __init__(self):
        api_key = (
            os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        ).strip()
        self.has_api_key = api_key not in self.INVALID_API_KEY_VALUES
        self.llm = (
            ChatGoogleGenerativeAI(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                temperature=0.7,
                google_api_key=api_key,
            )
            if self.has_api_key
            else None
        )

    @staticmethod
    def format_value(value):
        if value is None:
            return "N/A"
        if isinstance(value, float):
            return f"{value:,.2f}"
        if isinstance(value, int):
            return f"{value:,}"
        return str(value)

    @staticmethod
    def metric_unavailable() -> str:
        return "Not available from current dataset"

    @staticmethod
    def to_number(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "").replace("%", ""))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def format_percent(value: float | None) -> str:
        if value is None:
            return ReportGeneratorAgent.metric_unavailable()
        return f"{value:.2%}"

    def format_kpi_value(self, metric: str, value):
        if value == self.metric_unavailable():
            return value
        if isinstance(value, str) and (value.endswith("%") or value in {"High", "Medium", "Low"}):
            return value

        numeric_value = self.to_number(value)
        if numeric_value is None:
            return self.format_value(value)

        count_metrics = {
            "record_count",
            "order_count",
            "total_quantity",
            "total_new_customers",
            "total_churned_customers",
            "total_support_tickets",
            "total_shipments",
            "delayed_shipments",
            "damage_shipments",
        }
        percent_metrics = {
            "profit_margin_percent",
            "average_discount_percent",
            "loss_record_ratio",
            "loss_amount_vs_total_profit",
            "high_discount_loss_ratio",
            "profit_margin",
            "mrr_growth_percent",
            "average_churn_rate_percent",
            "shipping_cost_ratio",
            "delay_rate",
            "damage_rate",
        }
        if metric in count_metrics:
            return f"{numeric_value:,.0f}"
        if metric in percent_metrics:
            percent_value = numeric_value if numeric_value <= 1 else numeric_value / 100
            return f"{percent_value:.2%}"
        return f"{numeric_value:,.2f}"

    def normalize_kpi_snapshot(self, kpi_rows: list[dict]) -> list[dict]:
        canonical_duplicates = {
            "profit_margin": "profit_margin_percent",
            "average_order_value": "average_order_value",
        }
        existing_metrics = {row.get("metric") for row in kpi_rows if isinstance(row, dict)}
        normalized = []
        seen = set()
        for row in kpi_rows:
            metric = row.get("metric") if isinstance(row, dict) else None
            if not metric:
                continue
            if metric == "profit_margin" and "profit_margin_percent" in existing_metrics:
                continue
            if metric in seen:
                continue
            seen.add(canonical_duplicates.get(metric, metric))
            normalized.append(row)
        return normalized

    @staticmethod
    def escape_table(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    def markdown_table(self, headers: list[str], rows: list[list]) -> list[str]:
        if not rows:
            return ["No data available."]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        for row in rows:
            lines.append("| " + " | ".join(self.escape_table(cell) for cell in row) + " |")
        return lines

    @staticmethod
    def has_numbered_section(content: str, section_number: int) -> bool:
        pattern = rf"(?m)^\s*(?:#{{1,3}}\s*)?{section_number}\.\s+\S+"
        return bool(re.search(pattern, content))

    @staticmethod
    def section_block(content: str, start_number: int, end_number: int) -> str:
        start_pattern = rf"(?m)^\s*(?:#{{1,3}}\s*)?{start_number}\.\s+\S+"
        start_match = re.search(start_pattern, content)
        if not start_match:
            return ""

        end_pattern = rf"(?m)^\s*(?:#{{1,3}}\s*)?{end_number}\.\s+\S+"
        end_match = re.search(end_pattern, content[start_match.end():])
        if not end_match:
            return content[start_match.end():]
        return content[start_match.end():start_match.end() + end_match.start()]

    @staticmethod
    def is_markdown_separator(line: str) -> bool:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            return False
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            return False
        return all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)

    @staticmethod
    def has_overlong_table_separator(line: str) -> bool:
        stripped = line.strip()
        if not stripped.startswith("|"):
            return False
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        return any(re.fullmatch(r":?-{20,}:?", cell or "") for cell in cells)

    def validate_report_markdown(self, content: str, report_settings: dict | None = None) -> list[str]:
        settings = self.normalize_report_settings(report_settings)
        errors = []

        if not isinstance(content, str) or not content.strip():
            return ["Report content is empty."]

        for section_number in range(1, 8):
            if not self.has_numbered_section(content, section_number):
                errors.append(f"Missing section {section_number}.")

        if settings["language"] == "English":
            required_labels = [
                "Executive Summary",
                "KPI Snapshot",
                "Key Insights with Evidence",
                "Segment Deep Dive",
                "Root Cause Hypotheses",
                "Recommended Action Plan",
                "Data Limitations",
            ]
            for label in required_labels:
                if label not in content:
                    errors.append(f"Missing English section label: {label}.")

        kpi_block = self.section_block(content, 2, 3)
        if not kpi_block:
            errors.append("KPI Snapshot section is missing or not isolated.")
            return errors

        if "## 3." in kpi_block or "\n3. " in kpi_block:
            errors.append("KPI table appears to swallow the next section heading.")

        table_lines = [line.strip() for line in kpi_block.splitlines() if line.strip().startswith("|")]
        if len(table_lines) < 3:
            errors.append("KPI Snapshot does not contain a complete markdown table.")
            return errors

        header = table_lines[0]
        expected_headers = (
            ["Metric", "Value", "Business Interpretation"]
            if settings["language"] == "English"
            else None
        )
        if expected_headers and not all(header_name in header for header_name in expected_headers):
            errors.append("KPI Snapshot table header does not match the requested language.")

        separator = table_lines[1]
        if not self.is_markdown_separator(separator):
            errors.append("KPI Snapshot table separator is invalid markdown.")
        if self.has_overlong_table_separator(separator) or len(separator) > 120:
            errors.append("KPI Snapshot table separator is suspiciously long.")

        for line in table_lines:
            if "## 3." in line or "3. Key Insights" in line:
                errors.append("KPI Snapshot table contains the next section heading.")
                break

        return errors

    @staticmethod
    def markdown_table_row_count(block: str) -> int | None:
        table_lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
        if len(table_lines) < 3:
            return None
        separator_index = None
        for index, line in enumerate(table_lines):
            if ReportGeneratorAgent.is_markdown_separator(line):
                separator_index = index
                break
        if separator_index is None:
            return None
        return max(0, len(table_lines) - separator_index - 1)

    @staticmethod
    def parse_reported_number(value: str) -> float | None:
        match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value)
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def normalized_kpi_label(value: str) -> str:
        return "".join(character for character in value.casefold() if character.isalnum())

    @staticmethod
    def critical_metrics_for_industry(industry: str) -> set[str]:
        return {
            "retail": {"total_sales", "total_profit", "profit_margin_percent"},
            "generic": {"total_sales", "total_profit", "profit_margin_percent"},
            "saas": {"current_mrr", "current_arr", "mrr_growth_percent", "average_churn_rate_percent"},
            "logistics": {"total_shipments", "shipping_cost_ratio", "average_delivery_time_days", "delay_rate", "damage_rate"},
        }.get(industry, set())

    def kpi_label_aliases(self, metric: str, settings: dict) -> set[str]:
        aliases = {metric, self.localize_metric_name(metric, settings)}
        explicit = {
            "profit_margin_percent": {"Profit Margin (%)", "Profit Margin Percent"},
            "average_churn_rate_percent": {"Churn Rate", "Average Churn"},
            "average_delivery_time_days": {"Avg Delivery Time", "Average Delivery Time (Days)"},
        }
        aliases.update(explicit.get(metric, set()))
        return {self.normalized_kpi_label(alias) for alias in aliases}

    def normalized_reported_kpi_value(self, cell: str, metric: str) -> float | None:
        value = self.parse_reported_number(cell)
        if value is None:
            return None
        percent_metrics = {
            "profit_margin_percent", "mrr_growth_percent", "average_churn_rate_percent",
            "shipping_cost_ratio", "delay_rate", "damage_rate",
        }
        if metric in percent_metrics and "%" not in cell and abs(value) <= 1:
            return value * 100
        return value

    def validate_critical_kpi_fidelity(
        self,
        content: str,
        report_schema: dict,
        report_settings: dict | None = None,
    ) -> list[str]:
        industry = report_schema.get("Industry", "retail")
        critical_metrics = self.critical_metrics_for_industry(industry)
        settings = self.normalize_report_settings(report_settings)
        block = self.section_block(content, 2, 3)
        table_rows = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
        errors = []
        parsed_rows = []
        for row in table_rows[2:]:
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(cells) >= 2:
                parsed_rows.append((self.normalized_kpi_label(cells[0]), cells[1]))
        for item in report_schema.get("KPI Snapshot", []):
            metric = item.get("metric") if isinstance(item, dict) else None
            value = item.get("value") if isinstance(item, dict) else None
            if metric not in critical_metrics or self.to_number(value) is None:
                continue
            aliases = self.kpi_label_aliases(metric, settings)
            matching = [cell for label, cell in parsed_rows if label in aliases]
            if not matching:
                errors.append(f"Critical KPI is missing from KPI Snapshot: {metric}.")
                continue
            actual = self.normalized_reported_kpi_value(matching[0], metric)
            expected_display = self.format_kpi_value(metric, value)
            expected = self.normalized_reported_kpi_value(expected_display, metric)
            tolerance = max(0.01, abs(expected or 0) * 0.0001)
            if actual is None or expected is None or not math.isclose(actual, expected, abs_tol=tolerance):
                errors.append(f"Critical KPI value does not match deterministic schema: {metric}.")
        return errors

    @staticmethod
    def schema_item_count(report_schema: dict, key: str) -> int:
        items = report_schema.get(key, [])
        return len(items) if isinstance(items, list) else 0

    def validate_schema_fidelity(
        self,
        content: str,
        report_schema: dict,
        report_settings: dict | None = None,
    ) -> list[str]:
        settings = self.normalize_report_settings(report_settings)
        errors = []

        section_limits = [
            ("KPI Snapshot", 2, 3, self.schema_item_count(report_schema, "KPI Snapshot")),
            (
                "Root Cause Hypotheses",
                5,
                6,
                self.schema_item_count(report_schema, "Root Cause Hypotheses"),
            ),
            (
                "Recommended Action Plan",
                6,
                7,
                self.schema_item_count(report_schema, "Recommended Action Plan"),
            ),
        ]
        for label, start_number, end_number, expected_count in section_limits:
            block = self.section_block(content, start_number, end_number)
            row_count = self.markdown_table_row_count(block)
            if row_count is None:
                errors.append(f"{label} must use a markdown table.")
                continue
            if expected_count and row_count > expected_count:
                errors.append(
                    f"{label} has {row_count} rows, exceeding schema count {expected_count}."
                )

        lowered = content.lower()
        unsupported_causal_patterns = [
            r"\broot cause is\b",
            r"\broot causes are\b",
            r"\bcaused by weather\b",
            r"\bcaused by traffic\b",
            r"\bdue to weather\b",
            r"\bdue to traffic\b",
            r"\bdue to infrastructure\b",
            r"\bweather caused\b",
            r"\btraffic caused\b",
            r"\binfrastructure caused\b",
            r"\bservice quality caused\b",
            r"\bcustomer behavior caused\b",
        ]
        for pattern in unsupported_causal_patterns:
            if re.search(pattern, lowered):
                errors.append(f"Unsupported deterministic causal claim detected: {pattern}.")
                break

        if settings["language"] == "English":
            forbidden_labels = ["指标", "业务解读", "根因假设", "建议行动计划"]
            for label in forbidden_labels:
                if label in content:
                    errors.append(f"English report contains Chinese table or section label: {label}.")
                    break

        return errors

    def validate_generated_report(
        self,
        content: str,
        report_schema: dict,
        report_settings: dict | None = None,
    ) -> list[str]:
        return (
            self.validate_report_markdown(content, report_settings)
            + self.validate_schema_fidelity(content, report_schema, report_settings)
            + self.validate_critical_kpi_fidelity(content, report_schema, report_settings)
        )

    @staticmethod
    def high_confidence() -> str:
        return "High confidence"

    @staticmethod
    def medium_confidence() -> str:
        return "Medium confidence"

    @staticmethod
    def low_confidence_hypothesis() -> str:
        return "Hypothesis / Low confidence"

    @staticmethod
    def normalize_report_settings(report_settings: dict | None = None) -> dict:
        settings = report_settings or {}
        language = settings.get("language", "Chinese")
        tone = settings.get("tone", "Analyst Report")
        length = settings.get("length", "Detailed")

        if language not in {"Chinese", "English"}:
            language = "Chinese"
        if tone not in {"Executive Summary", "Analyst Report"}:
            tone = "Analyst Report"
        if length not in {"Brief", "Detailed"}:
            length = "Detailed"

        return {
            "language": language,
            "tone": tone,
            "length": length,
        }

    @staticmethod
    def is_chinese(settings: dict) -> bool:
        return settings.get("language") == "Chinese"

    def localize_confidence(self, value: str, settings: dict) -> str:
        if not self.is_chinese(settings):
            return value
        labels = {
            self.high_confidence(): "高置信度",
            self.medium_confidence(): "中等置信度",
            self.low_confidence_hypothesis(): "假设 / 低置信度",
        }
        return labels.get(value, value)

    @staticmethod
    def localize_priority(value: str, settings: dict) -> str:
        if settings.get("language") != "Chinese":
            return value
        labels = {
            "High": "高",
            "Medium": "中",
            "Low": "低",
        }
        return labels.get(value, value)

    @staticmethod
    def localize_metric_name(metric: str, settings: dict) -> str:
        english_labels = {
            "record_count": "Record Count",
            "total_sales": "Total Sales",
            "average_sales": "Average Sales",
            "total_profit": "Total Profit",
            "profit_margin_percent": "Profit Margin",
            "total_quantity": "Total Quantity",
            "average_discount_percent": "Average Discount",
            "order_count": "Order Count",
            "average_order_value": "Average Order Value",
            "loss_record_ratio": "Loss Record Ratio",
            "loss_amount_vs_total_profit": "Loss Amount vs Total Profit",
            "high_discount_loss_ratio": "High-Discount Loss Ratio",
            "profit_margin": "Profit Margin",
            "discount_risk_level": "Discount Risk Level",
            "current_mrr": "Current MRR",
            "current_arr": "Current ARR",
            "mrr_growth_percent": "MRR Growth",
            "total_new_customers": "New Customers",
            "total_churned_customers": "Churned Customers",
            "average_churn_rate_percent": "Average Churn Rate",
            "total_expansion_revenue": "Expansion Revenue",
            "total_support_tickets": "Support Tickets",
            "average_cac": "Average CAC",
            "total_shipments": "Total Shipments",
            "total_order_value": "Total Order Value",
            "total_shipping_cost": "Total Shipping Cost",
            "shipping_cost_ratio": "Shipping Cost Ratio",
            "average_delivery_time_days": "Average Delivery Time",
            "delayed_shipments": "Delayed Shipments",
            "delay_rate": "Delay Rate",
            "damage_shipments": "Damage-Flagged Shipments",
            "damage_rate": "Damage Rate",
            "plan_type": "Plan Type",
            "customer_segment": "Customer Segment",
            "carrier": "Carrier",
            "route": "Route",
            "warehouse": "Warehouse",
            "mrr / churn_rate": "MRR / Churn Rate",
            "delay_rate / delivery_time": "Delay Rate / Delivery Time",
        }
        if settings.get("language") != "Chinese":
            return english_labels.get(metric, metric)
        labels = {
            "record_count": "记录数",
            "total_sales": "总销售额",
            "average_sales": "平均销售额",
            "total_profit": "总利润",
            "profit_margin_percent": "利润率（%）",
            "total_quantity": "总数量",
            "average_discount_percent": "平均折扣率（%）",
            "order_count": "订单数",
            "average_order_value": "平均订单金额",
            "loss_record_ratio": "亏损记录占比",
            "loss_amount_vs_total_profit": "亏损金额 / 总利润",
            "high_discount_loss_ratio": "高折扣亏损占亏损记录比例",
            "profit_margin": "利润率",
            "discount_risk_level": "折扣风险等级",
            "current_mrr": "当前 MRR",
            "current_arr": "当前 ARR",
            "mrr_growth_percent": "MRR 增长率",
            "total_new_customers": "新增客户数",
            "total_churned_customers": "流失客户数",
            "average_churn_rate_percent": "平均流失率",
            "total_expansion_revenue": "扩张收入",
            "total_support_tickets": "支持工单数",
            "average_cac": "平均 CAC",
            "total_shipments": "总发运量",
            "total_order_value": "总订单价值",
            "total_shipping_cost": "总运输成本",
            "shipping_cost_ratio": "运输成本率",
            "average_delivery_time_days": "平均交付天数",
            "delayed_shipments": "延迟发运量",
            "delay_rate": "延迟率",
            "damage_shipments": "损坏发运量",
            "damage_rate": "损坏率",
            "plan_type": "套餐类型",
            "customer_segment": "客户分层",
            "carrier": "承运商",
            "route": "路线",
            "warehouse": "仓库",
            "mrr / churn_rate": "MRR / 流失率",
            "delay_rate / delivery_time": "延迟率 / 交付时间",
            "Sales": "销售额",
            "Profit": "利润",
            "Discount": "折扣",
            "Quantity": "数量",
            "Product Name": "产品名称",
            "Region": "地区",
            "Category": "品类",
            "Segment": "客群",
            "Customer Name": "客户名称",
            "Order Date": "订单日期",
            "N/A": "不适用",
        }
        return labels.get(metric, metric)

    def localize_text(self, value, settings: dict) -> str:
        text = self.format_value(value)
        if not self.is_chinese(settings):
            return text

        phrase_map = {
            "This report is based on the provided BusinessInsightAgent output.": "本报告基于 BusinessInsightAgent 提供的结构化洞察生成。",
            "BusinessInsightAgent output was used as the primary report input.": "BusinessInsightAgent 输出已作为本次报告的主要输入。",
            "Evidence was not provided in business_insights.": "business_insights 未提供对应证据。",
            "Business implication was not provided.": "business_insights 未提供业务影响说明。",
            "Review this insight against source metrics before making decisions.": "在形成决策前，需要回到原始指标验证该洞察。",
            "Evidence was not provided.": "未提供对应证据。",
            "Review the trend or risk signal before making decisions.": "在形成决策前，需要复核该趋势或风险信号。",
            "BusinessInsightAgent did not provide segment_insights.": "BusinessInsightAgent 未提供 segment_insights。",
            "BusinessInsightAgent did not provide explicit data limitations.": "BusinessInsightAgent 未提供明确的数据限制说明。",
            "Report conclusions depend on the completeness and quality of the supplied business_insights object.": "报告结论依赖所提供 business_insights 对象的完整性和质量。",
            "Business insights were provided but no major insight entries were found": "已提供业务洞察输入，但未发现主要洞察条目",
            "The business_insights object did not include major_insights, trend_insights, or list-based risk_detection.": "business_insights 对象未包含 major_insights、trend_insights 或列表形式的 risk_detection。",
            "The report can summarize available KPI and recommendation fields, but insight quality is limited.": "报告可以汇总现有 KPI 和建议字段，但洞察质量有限。",
            "Business insight": "业务洞察",
            "Trend insight": "趋势洞察",
            "Risk detection": "风险识别",
            "business performance": "业务表现",
            "Recommendation was provided as free text.": "该建议来自自由文本输入。",
            "business impact": "业务影响",
            "Dataset contains": "数据集包含",
            "The report is based on local computed metrics, field-role detection, trend summaries, risk checks, and small sample rows.": "本报告基于本地计算指标、字段角色识别、趋势摘要、风险检查和少量样本行生成。",
            "Revenue and profit are both measurable in the uploaded dataset": "上传数据集中可以同时衡量收入和利润",
            "The dataset can support profitability-oriented business reporting, not only volume reporting.": "该数据集可以支持以盈利能力为核心的业务报告，而不仅是规模描述。",
            "Loss-making records require management attention": "亏损记录需要管理层关注",
            "Loss-making records:": "亏损记录数：",
            "total loss:": "总亏损：",
            "Profit leakage may be concentrated in specific products, customers, regions, or discount patterns.": "利润流失可能集中在特定产品、客户、地区或折扣模式中。",
            "Use the segment deep dive to identify where negative-profit records should be reviewed first.": "应结合分群深入分析，优先定位需要复核的负利润记录对象。",
            "High-discount loss records may indicate promotion pressure": "高折扣亏损记录可能提示促销压力",
            "High-discount loss records:": "高折扣亏损记录数：",
            "high-discount threshold:": "高折扣阈值：",
            "Discount policy may need review where discounting coincides with negative profit.": "当折扣与负利润同时出现时，需要复核折扣政策。",
            "A product-level revenue concentration exists": "产品层面存在收入集中现象",
            "The highest-contributing products should be reviewed for margin quality and concentration exposure.": "应复核高贡献产品的利润质量和收入集中度。",
            "Some regions show relatively weaker profit contribution": "部分地区显示相对较弱的利润贡献",
            "Weakest": "相对较弱",
            "Regional profitability differences should be reviewed before assigning a cause.": "地区利润差异需要进一步复核后才能判断原因。",
            "Limited business-specific fields were detected": "检测到的业务字段有限",
            "The analysis did not identify enough sales, profit, segment, or time fields for strong business conclusions.": "当前分析未识别到足够的销售、利润、分群或时间字段，因此难以形成强业务结论。",
            "The report should be treated as a general data quality and descriptive analysis.": "本报告应被视为一般性数据质量和描述性分析。",
            "No suitable segment fields were detected for deep-dive analysis.": "未检测到适合深入分群分析的字段。",
            "Discounting may be contributing to profit leakage.": "折扣可能正在造成利润流失。",
            "High-discount records overlap with loss-making records.": "高折扣记录与亏损记录存在重叠。",
            "Promotion rules, product cost, approved discount policy, and customer contract terms.": "促销规则、产品成本、已批准折扣政策和客户合同条款。",
            "Losses may be concentrated in specific products, regions, or customers.": "亏损可能集中在特定产品、地区或客户中。",
            "Negative-profit records are present; segment-level Bottom analysis should be reviewed.": "数据中存在负利润记录，应进一步复核分群层面的表现最低对象。",
            "Cost drivers, fulfillment costs, return rates, and customer-level contract terms.": "成本驱动因素、履约成本、退货率和客户级合同条款。",
            "Seasonality or monthly operational patterns may affect performance.": "季节性或月度运营模式可能影响业务表现。",
            "A date field was detected and monthly trend data is available.": "已检测到日期字段，并可生成月度趋势数据。",
            "Multiple years of comparable history, campaign calendar, inventory constraints, and market events.": "多年可比历史数据、营销活动日历、库存约束和市场事件。",
            "No strong root-cause hypothesis is supported by the current computed results.": "当前计算结果不足以支持强根因假设。",
            "The available analysis does not show enough risk, segment, or trend evidence.": "现有分析未显示足够的风险、分群或趋势证据。",
            "Clear sales, profit, date, product, customer, and operating cost fields.": "清晰的销售、利润、日期、产品、客户和运营成本字段。",
            "Review high-discount loss-making transactions": "复核高折扣亏损交易",
            "Identify products, customers, or regions where discounts coincide with negative profit.": "识别折扣与负利润同时出现的产品、客户或地区。",
            "Sales Operations": "销售运营",
            "2 weeks": "2 周",
            "average discount and loss-making order ratio": "平均折扣和亏损订单比例",
            "Reduce loss-making records": "减少亏损记录",
            "Prioritize the largest negative-profit records and review pricing, cost allocation, and contract terms.": "优先复核负利润最大的记录，并检查定价、成本分摊和合同条款。",
            "Finance": "财务",
            "1 month": "1 个月",
            "loss-making order ratio and total loss": "亏损订单比例和总亏损额",
            "Improve profit margin governance": "加强利润率治理",
            "Sales and profit are both available, enabling margin-based management.": "销售额和利润字段均可用，因此可以进行利润率管理。",
            "Sales Director": "销售总监",
            "1 quarter": "1 个季度",
            "profit margin": "利润率",
            "Validate numeric anomalies": "验证数值异常",
            "Outliers may represent large valid deals, special promotions, or data entry issues.": "异常值可能代表真实大单、特殊促销或数据录入问题。",
            "Data Team": "数据团队",
            "anomaly resolution rate": "异常处理完成率",
            "Run segment-level deep dive": "开展分群深入分析",
            "Detected segment fields can help isolate which products, regions, customers, or segments drive performance differences.": "已检测到的分群字段可帮助定位哪些产品、地区、客户或客群导致表现差异。",
            "gross margin by segment": "分群毛利率",
            "Strengthen business data capture": "加强业务数据采集",
            "Current fields are insufficient for stronger business conclusions.": "当前字段不足以支撑更强的业务结论。",
            "field completeness and report confidence": "字段完整率和报告置信度",
            "No major risk was identified from the computed results.": "当前计算结果未识别出主要风险。",
            "Confirm field mappings and rerun the analysis.": "确认字段映射后重新运行分析。",
            "Run a segment-level deep dive on the weakest profit contributors and strongest revenue contributors.": "针对利润贡献最弱和收入贡献最强的分群开展深入分析。",
            "Top and Bottom segment analysis can separate growth engines from profitability drags.": "高低表现分群分析可以区分增长来源和盈利拖累项。",
            "profit margin by segment, revenue growth": "分群利润率、收入增长",
            "Monitor monthly trend changes and flag unusual months.": "监控月度趋势变化并标记异常月份。",
            "Trend monitoring helps identify periods that deserve further review, without assuming the cause from this dataset alone.": "趋势监控有助于识别需要进一步复盘的时间段，但不能仅凭当前数据假定原因。",
            "monthly revenue growth, monthly profit margin": "月度收入增长、月度利润率",
            "Confirm business field mappings before drawing deeper conclusions.": "在形成更深入结论前确认业务字段映射。",
            "Reliable business reporting depends on correctly identified sales, profit, date, product, and customer fields.": "可靠的业务报告依赖对销售、利润、日期、产品和客户字段的正确识别。",
            "Field mapping completeness": "字段映射完整率",
            "Audit high-discount loss-making transactions and pause repeat approvals until reviewed.": "审查高折扣亏损交易，并在复核完成前暂停重复审批。",
            "Review and escalate approval for": "复核并升级审批",
            "high-discount loss transactions.": "高折扣亏损交易。",
            "High-discount transactions that also lose money are directly linked to profit leakage in the computed results.": "计算结果显示，高折扣且亏损的交易与利润流失直接相关。",
            "High-discount records overlap with loss-making records in the computed results.": "计算结果显示，高折扣记录与亏损记录存在重叠。",
            "loss-making order ratio, average discount": "亏损订单比例、平均折扣",
            "Create a loss-making order review by product, customer, region, and discount band.": "按产品、客户、地区和折扣区间建立亏损订单复盘。",
            "The data shows negative-profit records; segmenting them identifies where corrective action should start.": "数据中存在负利润记录，分群拆解可以定位应优先整改的对象。",
            "total loss, loss-making order ratio": "总亏损额、亏损订单比例",
            "Prioritize margin improvement in high-revenue, low-profit segments.": "优先改善高收入、低利润分群的利润率。",
            "Revenue without sufficient profit can hide pricing, cost, or discount issues that reduce enterprise value.": "有收入但利润不足，可能掩盖定价、成本或折扣问题，并降低企业价值。",
            "profit margin, gross margin": "利润率、毛利率",
            "Sample-check numeric anomalies before using them for management decisions.": "在用于管理决策前，对数值异常记录进行抽样检查。",
            "Outliers may represent major accounts, unusual orders, special promotions, or data quality issues.": "异常值可能代表大客户、非常规订单、特殊促销或数据质量问题。",
            "validated anomaly rate, data correction rate": "异常验证率、数据修正率",
            "No sales or revenue field was confidently identified.": "未能高置信度识别销售或收入字段。",
            "No profit or margin field was confidently identified.": "未能高置信度识别利润或利润率字段。",
            "No reliable date field was identified, so trend conclusions are limited.": "未识别到可靠日期字段，因此趋势结论有限。",
            "No strong segment fields were identified for business deep dives.": "未识别到足够明确的分群字段，难以开展业务深入分析。",
            "Some fields have high missing rates and may reduce reliability.": "部分字段缺失率较高，可能降低结论可靠性。",
            "Schema metadata is missing from the analysis result.": "分析结果中缺少 schema 元数据。",
            "The dataset does not include market competition, inventory, customer behavior, or product lifecycle fields; those causes should not be treated as confirmed.": "数据集中不包含市场竞争、库存、客户行为或产品生命周期字段，因此这些原因不能被视为已确认原因。",
            "The report is based on computed summaries and samples, not a manual review of every raw record.": "本报告基于计算摘要和样本生成，并非对每条原始记录的人工复核。",
            "Supporting evidence was not provided.": "未提供支撑证据。",
            "Additional operational data is needed for validation.": "需要补充运营数据进行验证。",
            "No root-cause hypothesis was provided by BusinessInsightAgent.": "BusinessInsightAgent 未提供根因假设。",
            "No hypothesis-specific evidence was supplied.": "未提供针对该假设的具体证据。",
            "Provide driver fields or explicit hypothesis evidence.": "需要提供驱动因素字段或明确的假设证据。",
            "Review BusinessInsightAgent outputs and define follow-up actions.": "复核 BusinessInsightAgent 输出并制定后续行动。",
            "No explicit recommendations were supplied.": "未提供明确建议。",
            "recommendation coverage": "建议覆盖率",
            "Review recommended action.": "复核建议行动。",
            "Rationale was not provided.": "未提供行动理由。",
            "Segment evidence is not available in compact form.": "当前分群证据无法以紧凑形式展示。",
            "Validate segment mapping and rerun the analysis.": "验证分群字段映射后重新运行分析。",
            "Negative profit object; prioritize review of margin, cost, and discount records.": "该对象为负利润，应优先复核利润率、成本和折扣记录。",
            "Relatively weaker profit contribution; review before treating it as a true profit problem.": "利润贡献相对较弱，但在确认为真实利润问题前需要进一步复核。",
            "Lower revenue contribution; review only if this object is strategically important.": "收入贡献相对较低，仅在该对象具有战略重要性时需要进一步复核。",
            "Relative performance gap; review supporting records before drawing stronger conclusions.": "存在相对表现差距，需要复核支撑记录后再形成更强结论。",
            "Not available from current dataset": "当前数据集无法获得",
            "High": "高",
            "Medium": "中",
            "Low": "低",
        }

        for source, target in phrase_map.items():
            text = text.replace(source, target)
        text = text.replace("User focus:", "用户关注点：")
        text = text.replace("Audit ", "审查 ")
        text = text.replace("复核并升级审批 ", "复核并升级审批 ")
        text = text.replace(" high-discount loss transactions.", " 条高折扣亏损交易。")
        text = text.replace(" before approving similar discounts.", "，再审批类似折扣。")
        text = text.replace(" pricing and discount records.", " 的定价和折扣记录。")
        text = text.replace("Review ", "复核 ")
        text = text.replace("records", "记录")
        text = text.replace("record", "记录")
        text = text.replace("regional", "地区")
        text = text.replace("category", "品类")
        text = text.replace("ratio", "比例")
        text = text.replace("Product Name", "产品名称")
        text = text.replace("Customer Name", "客户名称")
        text = text.replace("Region", "地区")
        text = text.replace("Category", "品类")
        text = text.replace("Segment", "客群")
        text = text.replace("Sales", "销售额")
        text = text.replace("Profit", "利润")
        text = text.replace(" category margin structure.", " 品类利润结构。")
        text = text.replace(" regional margin performance.", " 地区利润表现。")
        text = text.replace(" account profitability records.", " 客户盈利记录。")
        text = text.replace(" margin structure and discount records.", " 利润结构和折扣记录。")
        text = text.replace(" contribution and decide whether it needs commercial follow-up.", " 贡献表现，并判断是否需要商业跟进。")
        text = text.replace(" is the lowest-profit product in the segment analysis, with ", " 是分群分析中的最低利润产品，利润为 ")
        text = text.replace(" is the relatively weakest category by profit, with ", " 是按利润衡量相对最弱的品类，利润为 ")
        text = text.replace(" is the relatively weakest region by profit, with ", " 是按利润衡量相对最弱的地区，利润为 ")
        text = text.replace(" is the relatively weakest customer by profit, with ", " 是按利润衡量相对最弱的客户，利润为 ")
        text = text.replace("Outliers may represent large valid deals, unusual orders, or data quality issues.", "异常值可能代表真实大额交易、非常规订单或数据质量问题。")
        text = text.replace("Total sales:", "总销售额：")
        text = text.replace("total profit:", "总利润：")
        text = text.replace("profit margin:", "利润率：")
        text = text.replace("Total profit is", "总利润为")
        text = text.replace("Total sales are", "总销售额为")
        text = text.replace("Overall profit margin is", "整体利润率为")
        text = text.replace("Overall 利润率 is", "整体利润率为")
        text = text.replace("利润率 is", "利润率为")
        text = text.replace("profit margin:", "利润率：")
        text = text.replace("Profit margin:", "利润率：")
        text = text.replace("records have negative profit", "条记录为负利润")
        text = text.replace("with total loss of", "总亏损为")
        text = text.replace("records are both high-discount and loss-making", "条记录同时为高折扣且亏损")
        text = text.replace("high-discount threshold is", "高折扣阈值为")
        text = text.replace("negative profit", "负利润")
        text = text.replace("high-discount", "高折扣")
        text = text.replace("loss-making", "亏损")
        text = text.replace("revenue", "收入")
        text = text.replace("profit", "利润")
        text = text.replace("discount", "折扣")
        text = text.replace("sales", "销售额")
        text = text.replace("order", "订单")
        text = text.replace("orders", "订单")
        text = text.replace("customer", "客户")
        text = text.replace("customers", "客户")
        text = text.replace("product", "产品")
        text = text.replace("products", "产品")
        text = text.replace("region", "地区")
        text = text.replace("regions", "地区")
        text = text.replace("Top", "最高")
        text = text.replace("Bottom", "低表现")
        text = text.replace("Lowest", "最低")
        text = text.replace("低est", "最低")
        text = text.replace("by", "按")
        text = text.replace("最高/Bottom", "高低表现")
        text = text.replace("最高/低表现", "高低表现")
        text = text.replace("gross margin", "毛利率")
        text = text.replace("revenue growth", "收入增长")
        text = text.replace("利润率, 毛利率", "利润率、毛利率")
        text = text.replace("segment", "分群")
        text = text.replace("monthly", "月度")
        text = text.replace("低表现 表现", "低表现")
        text = text.replace("分群层面的 低表现", "分群层面的表现最低对象")
        text = text.replace("高低表现 分群分析", "高低表现分群分析")
        text = text.replace("利润率 按 分群, 收入 growth", "分群利润率、收入增长")
        text = text.replace("月度 收入 growth, 月度 利润率", "月度收入增长、月度利润率")
        text = text.replace("收入 growth", "收入增长")
        text = text.replace("按 分群", "按分群")
        text = text.replace(" margin structure and 折扣 记录.", " 利润结构和折扣记录。")
        text = text.replace(" 品类 margin structure.", " 品类利润结构。")
        text = text.replace(" margin performance.", " 利润表现。")
        text = text.replace(" account 利润ability 记录.", " 客户盈利记录。")
        text = text.replace("category 利润率", "品类利润率")
        text = text.replace("regional 利润率", "地区利润率")
        text = text.replace("customer 利润率", "客户利润率")
        text = text.replace(" is the relatively weakest 品类 按 利润, with ", " 是按利润衡量相对最弱的品类，利润为 ")
        text = text.replace("产品 利润, 亏损 订单 比例", "产品利润、亏损订单比例")
        text = text.replace("品类 利润率", "品类利润率")
        text = text.replace("地区 利润率", "地区利润率")
        text = text.replace("地区 利润表现", "地区利润表现")
        text = text.replace("客户 利润率", "客户利润率")
        text = text.replace("高折扣 亏损 记录", "高折扣亏损记录")
        text = text.replace(" 利润.", "。")
        text = text.replace("利润.", "利润。")
        text = text.replace(" .", "。")
        text = text.replace("订单s", "订单")
        text = text.replace("客户s", "客户")
        text = text.replace("产品s", "产品")
        text = text.replace("地区s", "地区")
        text = text.replace("rows and", "行，")
        text = text.replace("columns.", "列。")
        return text

    @staticmethod
    def first_top_bottom(top_bottom: dict, metric: str, dimension: str, side: str) -> dict | None:
        rows = top_bottom.get(metric, {}).get(dimension, {}).get(side, [])
        return rows[0] if rows else None

    def segment_object_and_value(self, row: dict | None, metric: str) -> tuple[str, str, float | None]:
        if not isinstance(row, dict) or not row:
            return self.metric_unavailable(), self.metric_unavailable(), None
        object_name = None
        for key, value in row.items():
            if key != metric and not isinstance(value, (int, float)):
                object_name = str(value)
                break
        if object_name is None:
            for key, value in row.items():
                if key != metric:
                    object_name = str(value)
                    break
        metric_value = self.to_number(row.get(metric))
        if metric_value is None:
            for value in row.values():
                metric_value = self.to_number(value)
                if metric_value is not None:
                    break
        value_display = f"{metric_value:,.2f}" if metric_value is not None else self.metric_unavailable()
        return object_name or self.metric_unavailable(), value_display, metric_value

    def segment_interpretation(self, metric: str, weakest_value: float | None) -> str:
        if "profit" in metric.lower():
            if weakest_value is not None and weakest_value < 0:
                return "Negative profit object; prioritize review of margin, cost, and discount records."
            return "Relatively weaker profit contribution; review before treating it as a true profit problem."
        if "sales" in metric.lower():
            return "Lower revenue contribution; review only if this object is strategically important."
        return "Relative performance gap; review supporting records before drawing stronger conclusions."

    def segment_follow_up(self, dimension: str, weakest_object: str, metric: str) -> str:
        if weakest_object == self.metric_unavailable():
            return "Validate segment mapping and rerun the analysis."
        if "profit" in metric.lower():
            return f"Review {dimension} '{weakest_object}' margin structure and discount records."
        return f"Review {dimension} '{weakest_object}' contribution and decide whether it needs commercial follow-up."

    def segment_management_rows(self, segment_deep_dive: list[dict], settings: dict) -> list[list]:
        rows = []
        for segment in segment_deep_dive:
            if "best_object" in segment:
                rows.append(
                    [
                        self.localize_metric_name(segment.get("segment", "N/A"), settings),
                        self.localize_metric_name(segment.get("metric", "N/A"), settings),
                        segment.get("best_object", self.metric_unavailable()),
                        segment.get("best_value", self.metric_unavailable()),
                        segment.get("weakest_object", self.metric_unavailable()),
                        segment.get("weakest_value", self.metric_unavailable()),
                        self.localized_field(segment, "business_interpretation", settings),
                        self.localized_field(segment, "recommended_follow_up", settings),
                    ]
                )
                continue

            observations = segment.get("observations", [])
            for observation in observations:
                if isinstance(observation, dict):
                    metric = observation.get("metric", "N/A")
                    best_object, best_value, _ = self.segment_object_and_value((observation.get("top") or [None])[0], metric)
                    weakest_object, weakest_value, weakest_numeric = self.segment_object_and_value((observation.get("bottom") or [None])[0], metric)
                    rows.append(
                        [
                            self.localize_metric_name(segment.get("segment", "N/A"), settings),
                            self.localize_metric_name(metric, settings),
                            best_object,
                            best_value,
                            weakest_object,
                            weakest_value,
                            self.localize_text(self.segment_interpretation(metric, weakest_numeric), settings),
                            self.localize_text(
                                self.segment_follow_up(segment.get("segment", "segment"), weakest_object, metric),
                                settings,
                            ),
                        ]
                    )
                else:
                    rows.append(
                        [
                            self.localize_metric_name(segment.get("segment", "N/A"), settings),
                            self.localize_metric_name("N/A", settings),
                            self.metric_unavailable(),
                            self.metric_unavailable(),
                            self.localize_text(observation, settings),
                            self.metric_unavailable(),
                            self.localize_text("Segment evidence is not available in compact form.", settings),
                            self.localize_text("Validate segment mapping and rerun the analysis.", settings),
                        ]
                    )
        return rows

    def localized_field(self, item: dict, key: str, settings: dict):
        if self.is_chinese(settings) and f"{key}_zh" in item:
            return item[f"{key}_zh"]
        return self.localize_text(item.get(key, ""), settings)

    def compact_analysis_results(self, analysis_results: dict) -> dict:
        if self.is_business_insights(analysis_results):
            return {
                "input_type": "business_insights",
                "kpi_summary": analysis_results.get("kpi_summary") or analysis_results.get("kpis"),
                "trend_insights": analysis_results.get("trend_insights"),
                "segment_insights": analysis_results.get("segment_insights"),
                "risk_detection": analysis_results.get("risk_detection") or analysis_results.get("risks"),
                "recommendations": analysis_results.get("recommendations"),
                "data_limitations": analysis_results.get("data_limitations"),
                "major_insights": analysis_results.get("major_insights") or analysis_results.get("insights"),
            }

        compact = {
            "status": analysis_results.get("status"),
            "analysis_task": analysis_results.get("analysis_task"),
            "summary_text": analysis_results.get("summary_text"),
            "schema": analysis_results.get("schema"),
            "field_roles": analysis_results.get("field_roles"),
            "overview": analysis_results.get("overview"),
            "kpis": analysis_results.get("kpis"),
            "numeric_analysis": analysis_results.get("numeric_analysis"),
            "category_analysis": analysis_results.get("category_analysis"),
            "time_trends": analysis_results.get("time_trends"),
            "top_bottom": analysis_results.get("top_bottom"),
            "risks": analysis_results.get("risks"),
            "industry_analysis": analysis_results.get("industry_analysis"),
            "sample_rows": analysis_results.get("sample_rows", [])[:5],
        }
        payload = json.dumps(compact, ensure_ascii=False)
        if len(payload) <= self.MAX_JSON_CHARS:
            return compact

        compact["numeric_analysis"] = {}
        compact["category_analysis"] = {}
        compact["top_bottom"] = {}
        compact["time_trends"] = {
            "note": "Time trend rows were shortened before sending to Gemini.",
            "rows": (analysis_results.get("time_trends", {}).get("rows") or [])[-6:],
        }
        return compact

    @staticmethod
    def is_business_insights(report_input: dict) -> bool:
        business_keys = {
            "business_insights",
            "kpi_summary",
            "trend_insights",
            "segment_insights",
            "risk_detection",
            "recommendations",
            "data_limitations",
            "major_insights",
        }
        return any(key in report_input for key in business_keys)

    def build_report_schema_from_business_insights(self, business_insights: dict, user_requirements: str) -> dict:
        kpis = business_insights.get("kpi_summary") or business_insights.get("kpis") or {}
        trend_insights = business_insights.get("trend_insights") or []
        segment_insights = business_insights.get("segment_insights") or []
        risk_detection = business_insights.get("risk_detection") or business_insights.get("risks") or {}
        recommendations = business_insights.get("recommendations") or []
        data_limitations = business_insights.get("data_limitations") or []
        major_insights = business_insights.get("major_insights") or business_insights.get("insights") or []

        if isinstance(kpis, list):
            kpi_snapshot = kpis
            kpi_dict = {
                item.get("metric"): item.get("value")
                for item in kpis
                if isinstance(item, dict) and item.get("metric")
            }
        else:
            kpi_snapshot = [{"metric": key, "value": value} for key, value in kpis.items()]
            kpi_dict = kpis
        derived_metrics = self.build_derived_metrics(
            overview={},
            kpis=kpi_dict,
            risks=risk_detection if isinstance(risk_detection, dict) else {},
        )

        executive_summary = [
            "This report is based on the provided BusinessInsightAgent output.",
            "BusinessInsightAgent output was used as the primary report input.",
        ]
        if user_requirements.strip():
            executive_summary.append(f"User focus: {user_requirements.strip()}")

        insights = []
        for item in major_insights:
            if isinstance(item, dict):
                insights.append(
                    {
                        "Finding": item.get("finding") or item.get("title") or item.get("Finding") or "Business insight",
                        "Evidence": item.get("evidence") or item.get("Evidence") or "Evidence was not provided in business_insights.",
                        "Business Implication": item.get("business_implication") or item.get("Business Implication") or item.get("implication") or "Business implication was not provided.",
                        "Confidence Level": item.get("confidence_level") or item.get("Confidence Level") or self.medium_confidence(),
                    }
                )
            else:
                insights.append(
                    {
                        "Finding": str(item),
                        "Evidence": "Evidence was not provided in business_insights.",
                        "Business Implication": "Review this insight against source metrics before making decisions.",
                        "Confidence Level": self.low_confidence_hypothesis(),
                    }
                )

        if isinstance(trend_insights, dict):
            trend_insights = [trend_insights]
        if not isinstance(trend_insights, list):
            trend_insights = []
        risk_items = risk_detection if isinstance(risk_detection, list) else []

        for item in trend_insights:
            insights.append(self.business_insight_to_finding(item, "Trend insight"))
        for item in risk_items:
            insights.append(self.business_insight_to_finding(item, "Risk detection"))

        if not insights:
            insights.append(
                {
                    "Finding": "Business insights were provided but no major insight entries were found",
                    "Evidence": "The business_insights object did not include major_insights, trend_insights, or list-based risk_detection.",
                    "Business Implication": "The report can summarize available KPI and recommendation fields, but insight quality is limited.",
                    "Confidence Level": self.low_confidence_hypothesis(),
                }
            )

        segment_deep_dive = self.build_segment_deep_dive_from_business_insights(segment_insights)
        root_cause_hypotheses = self.build_hypotheses_from_business_insights(trend_insights, risk_detection)
        recommended_actions = self.build_actions_from_business_insights(recommendations)

        if not data_limitations:
            data_limitations = [
                "BusinessInsightAgent did not provide explicit data limitations.",
                "Report conclusions depend on the completeness and quality of the supplied business_insights object.",
            ]

        return {
            "Industry": "retail",
            "Executive Summary": executive_summary,
            "KPI Snapshot": self.normalize_kpi_snapshot(
                (kpi_snapshot or [{"metric": "business_insights", "value": "provided"}])
                + self.derived_metrics_as_kpi_rows(derived_metrics)
            ),
            "Derived Metrics": derived_metrics,
            "Key Insights with Evidence": insights,
            "Segment Deep Dive": segment_deep_dive,
            "Root Cause Hypotheses": root_cause_hypotheses,
            "Recommended Action Plan": recommended_actions,
            "Data Limitations": data_limitations,
        }

    def business_insight_to_finding(self, item, default_title: str) -> dict:
        if isinstance(item, dict):
            return {
                "Finding": item.get("finding") or item.get("title") or item.get("Finding") or default_title,
                "Evidence": item.get("evidence") or item.get("Evidence") or "Evidence was not provided.",
                "Business Implication": item.get("business_implication") or item.get("Business Implication") or item.get("implication") or "Business implication was not provided.",
                "Confidence Level": item.get("confidence_level") or item.get("Confidence Level") or self.medium_confidence(),
            }
        return {
            "Finding": default_title,
            "Evidence": str(item),
            "Business Implication": "Review the trend or risk signal before making decisions.",
            "Confidence Level": self.medium_confidence(),
        }

    def build_segment_deep_dive_from_business_insights(self, segment_insights) -> list[dict]:
        if not segment_insights:
            return [
                {
                    "segment": "N/A",
                    "observations": ["BusinessInsightAgent did not provide segment_insights."],
                }
            ]
        if isinstance(segment_insights, dict):
            segment_insights = [segment_insights]
        sections = []
        for item in segment_insights:
            if isinstance(item, dict):
                sections.append(
                    {
                        "segment": item.get("segment") or item.get("dimension") or item.get("name") or "Segment",
                        "observations": [
                            {
                                "metric": item.get("metric", "business performance"),
                                "top": item.get("top") or item.get("top_performers") or [],
                                "bottom": item.get("bottom") or item.get("bottom_performers") or [],
                            }
                        ],
                    }
                )
            else:
                sections.append({"segment": "Segment", "observations": [str(item)]})
        return sections

    def build_hypotheses_from_business_insights(self, trend_insights, risk_detection) -> list[dict]:
        hypotheses = []
        source_items = []
        if isinstance(trend_insights, list):
            source_items.extend(trend_insights)
        if isinstance(risk_detection, list):
            source_items.extend(risk_detection)
        elif isinstance(risk_detection, dict) and risk_detection:
            source_items.append(risk_detection)

        for item in source_items[:5]:
            if isinstance(item, dict):
                hypothesis_text = item.get("hypothesis") or item.get("possible_cause")
                if not hypothesis_text:
                    continue
                hypotheses.append(
                    {
                        "Hypothesis": hypothesis_text,
                        "Evidence Level": item.get("evidence_level") or item.get("confidence_level") or self.low_confidence_hypothesis(),
                        "Supporting Evidence": item.get("evidence") or item.get("supporting_evidence") or "Supporting evidence was not provided.",
                        "Additional Data Needed": item.get("data_needed") or item.get("Data Needed for Validation") or "Additional operational data is needed for validation.",
                        "Data Needed for Validation": item.get("data_needed") or item.get("Data Needed for Validation") or "Additional operational data is needed for validation.",
                    }
                )
        if not hypotheses:
            hypotheses.append(
                {
                    "Hypothesis": "No root-cause hypothesis was provided by BusinessInsightAgent.",
                    "Evidence Level": self.low_confidence_hypothesis(),
                    "Supporting Evidence": "No hypothesis-specific evidence was supplied.",
                    "Additional Data Needed": "Provide driver fields or explicit hypothesis evidence.",
                    "Data Needed for Validation": "Provide driver fields or explicit hypothesis evidence.",
                }
            )
        return hypotheses

    def build_actions_from_business_insights(self, recommendations) -> list[dict]:
        if not recommendations:
            return [
                {
                    "priority": "Medium",
                    "action": "Review BusinessInsightAgent outputs and define follow-up actions.",
                    "business_rationale": "No explicit recommendations were supplied.",
                    "suggested_owner": "Data Team",
                    "timeframe": "2 weeks",
                    "KPI to track": "recommendation coverage",
                }
            ]
        if isinstance(recommendations, dict):
            recommendations = [recommendations]
        actions = []
        for item in recommendations:
            if isinstance(item, dict):
                actions.append(
                    {
                        "priority": item.get("priority", "Medium"),
                        "action": item.get("action") or item.get("recommendation") or "Review recommended action.",
                        "business_rationale": item.get("business_rationale") or item.get("rationale") or "Rationale was not provided.",
                        "suggested_owner": item.get("suggested_owner") or item.get("owner") or "Data Team",
                        "timeframe": item.get("timeframe", "1 month"),
                        "KPI to track": item.get("KPI to track") or item.get("kpi_to_track") or "business impact",
                    }
                )
            else:
                actions.append(
                    {
                        "priority": "Medium",
                        "action": str(item),
                        "business_rationale": "Recommendation was provided as free text.",
                        "suggested_owner": "Data Team",
                        "timeframe": "1 month",
                        "KPI to track": "business impact",
                    }
                )
        return actions

    def build_derived_metrics(self, overview: dict, kpis: dict, risks: dict) -> dict:
        total_records = self.to_number(kpis.get("record_count") or overview.get("row_count"))
        total_sales = self.to_number(kpis.get("total_sales"))
        total_profit = self.to_number(kpis.get("total_profit"))
        order_count = self.to_number(kpis.get("order_count"))
        average_discount = self.to_number(kpis.get("average_discount_percent"))

        loss_records = risks.get("loss_records", {}) if isinstance(risks, dict) else {}
        high_discount_loss_records = (
            risks.get("high_discount_loss_records", {}) if isinstance(risks, dict) else {}
        )
        loss_count = self.to_number(loss_records.get("count"))
        total_loss = self.to_number(loss_records.get("total_loss"))
        high_discount_loss_count = self.to_number(high_discount_loss_records.get("count"))

        loss_record_ratio = loss_count / total_records if loss_count is not None and total_records else None
        loss_amount_vs_total_profit = (
            abs(total_loss) / total_profit
            if total_loss is not None and total_profit not in {None, 0}
            else None
        )
        high_discount_loss_ratio = (
            high_discount_loss_count / loss_count
            if high_discount_loss_count is not None and loss_count
            else None
        )
        average_order_value = total_sales / order_count if total_sales is not None and order_count else None
        profit_margin = total_profit / total_sales if total_profit is not None and total_sales else None

        discount_risk_level = self.metric_unavailable()
        if average_discount is not None and high_discount_loss_count is not None:
            discount_percent = average_discount / 100 if average_discount > 1 else average_discount
            if high_discount_loss_count > 0 and (discount_percent >= 0.20 or (high_discount_loss_ratio or 0) >= 0.50):
                discount_risk_level = "High"
            elif high_discount_loss_count > 0 or discount_percent >= 0.10:
                discount_risk_level = "Medium"
            else:
                discount_risk_level = "Low"

        return {
            "loss_record_ratio": {
                "value": loss_record_ratio,
                "display": self.format_percent(loss_record_ratio),
            },
            "loss_amount_vs_total_profit": {
                "value": loss_amount_vs_total_profit,
                "display": self.format_percent(loss_amount_vs_total_profit),
            },
            "high_discount_loss_ratio": {
                "value": high_discount_loss_ratio,
                "display": self.format_percent(high_discount_loss_ratio),
            },
            "average_order_value": {
                "value": average_order_value,
                "display": self.format_value(average_order_value) if average_order_value is not None else self.metric_unavailable(),
            },
            "profit_margin": {
                "value": profit_margin,
                "display": self.format_percent(profit_margin),
            },
            "discount_risk_level": {
                "value": discount_risk_level,
                "display": discount_risk_level,
            },
        }

    @staticmethod
    def derived_metric_display(derived_metrics: dict, metric: str) -> str:
        item = derived_metrics.get(metric, {})
        return item.get("display") or ReportGeneratorAgent.metric_unavailable()

    def derived_metrics_as_kpi_rows(self, derived_metrics: dict) -> list[dict]:
        return [
            {"metric": metric, "value": details.get("display", self.metric_unavailable())}
            for metric, details in derived_metrics.items()
        ]

    @staticmethod
    def industry_type(analysis_results: dict) -> str:
        industry_analysis = analysis_results.get("industry_analysis") or {}
        if industry_analysis.get("industry"):
            return industry_analysis["industry"]
        columns = {
            column.lower()
            for column in analysis_results.get("schema", {}).get("columns", [])
        }
        if {"mrr", "arr", "churn_rate"}.issubset(columns):
            return "saas"
        if {"shipping_cost", "delivery_time_days", "delay_flag"}.issubset(columns):
            return "logistics"
        return "generic"

    @staticmethod
    def clean_kpi_rows(kpis: dict, preferred_metrics: list[str]) -> list[dict]:
        return [
            {"metric": metric, "value": kpis.get(metric)}
            for metric in preferred_metrics
            if kpis.get(metric) is not None
        ]

    @staticmethod
    def pct_display(value) -> str:
        number = ReportGeneratorAgent.to_number(value)
        if number is None:
            return ReportGeneratorAgent.metric_unavailable()
        return f"{number:.2%}" if number <= 1 else f"{number:.2f}%"

    def industry_segment_row(
        self,
        dimension: str,
        metric: str,
        best: dict,
        risk: dict,
        best_key: str,
        risk_key: str,
        interpretation: str,
        follow_up: str,
        interpretation_zh: str | None = None,
        follow_up_zh: str | None = None,
    ) -> dict:
        row = {
            "segment": dimension,
            "metric": metric,
            "best_object": best.get(dimension, self.metric_unavailable()),
            "best_value": best_key,
            "weakest_object": risk.get(dimension, self.metric_unavailable()),
            "weakest_value": risk_key,
            "business_interpretation": interpretation,
            "recommended_follow_up": follow_up,
        }
        if interpretation_zh:
            row["business_interpretation_zh"] = interpretation_zh
        if follow_up_zh:
            row["recommended_follow_up_zh"] = follow_up_zh
        return row

    def build_saas_report_schema(self, analysis_results: dict, user_requirements: str) -> dict:
        industry_analysis = analysis_results.get("industry_analysis", {})
        kpis = industry_analysis.get("kpis", {})
        segments = industry_analysis.get("segments", {})
        preferred_metrics = [
            "current_mrr",
            "current_arr",
            "mrr_growth_percent",
            "total_new_customers",
            "total_churned_customers",
            "average_churn_rate_percent",
            "total_expansion_revenue",
            "total_support_tickets",
            "average_cac",
        ]
        kpi_snapshot = self.clean_kpi_rows(kpis, preferred_metrics)

        plan_segment = segments.get("plan_type", {})
        customer_segment = segments.get("customer_segment", {})
        plan_best = plan_segment.get("best_by_mrr", {})
        plan_risk = plan_segment.get("risk_by_churn", {})
        customer_best = customer_segment.get("best_by_mrr", {})
        customer_risk = customer_segment.get("risk_by_churn", {})

        insights = []
        if kpis.get("mrr_growth_percent") is not None:
            insights.append(
                {
                    "Finding": "MRR increased across the available period",
                    "Finding_zh": "MRR 在当前周期内增长",
                    "Evidence": f"MRR growth from the first to last available month is {self.format_kpi_value('mrr_growth_percent', kpis.get('mrr_growth_percent'))}.",
                    "Evidence_zh": f"从首月到末月，MRR 增长率为 {self.format_kpi_value('mrr_growth_percent', kpis.get('mrr_growth_percent'))}。",
                    "Business Implication": "Revenue momentum is visible, but retention quality should be reviewed alongside churn and support workload.",
                    "Business Implication_zh": "收入动能明确，但需要结合流失率和支持工单量判断增长质量。",
                    "Confidence Level": self.high_confidence(),
                }
            )
        if plan_risk:
            insights.append(
                {
                    "Finding": f"{plan_risk.get('plan_type')} has the highest churn rate among plan types",
                    "Finding_zh": f"{plan_risk.get('plan_type')} 是套餐类型中流失率最高的对象",
                    "Evidence": f"{plan_risk.get('plan_type')} churn rate is {self.pct_display(plan_risk.get('churn_rate'))}; total churned customers are {self.format_value(plan_risk.get('churned_customers'))}.",
                    "Evidence_zh": f"{plan_risk.get('plan_type')} 流失率为 {self.pct_display(plan_risk.get('churn_rate'))}；流失客户数为 {self.format_value(plan_risk.get('churned_customers'))}。",
                    "Business Implication": "Retention review should prioritize the segment with the highest observed churn before scaling acquisition spend.",
                    "Business Implication_zh": "在扩大获客投入前，应优先复核当前流失率最高的套餐分层。",
                    "Confidence Level": self.high_confidence(),
                }
            )
        if kpis.get("total_support_tickets") is not None:
            insights.append(
                {
                    "Finding": "Support workload is a measurable retention signal",
                    "Finding_zh": "支持工单量是可衡量的留存风险信号",
                    "Evidence": f"Total support tickets are {self.format_value(kpis.get('total_support_tickets'))}.",
                    "Evidence_zh": f"支持工单总数为 {self.format_value(kpis.get('total_support_tickets'))}。",
                    "Business Implication": "Support volume should be monitored with churn; it is a signal, not a confirmed churn cause.",
                    "Business Implication_zh": "支持工单量应与流失率联动监控；它是风险信号，不是已确认的流失原因。",
                    "Confidence Level": self.medium_confidence(),
                }
            )

        segment_rows = []
        if plan_best and plan_risk:
            segment_rows.append(
                self.industry_segment_row(
                    "plan_type",
                    "mrr / churn_rate",
                    plan_best,
                    plan_risk,
                    f"MRR {self.format_value(plan_best.get('mrr'))}",
                    f"Churn {self.pct_display(plan_risk.get('churn_rate'))}",
                    "Plan performance differs by revenue contribution and churn pressure.",
                    "Review pricing, onboarding, and retention signals for the highest-churn plan.",
                    "不同套餐在收入贡献和流失压力上存在差异。",
                    "复核流失率最高套餐的定价、onboarding 和留存信号。",
                )
            )
        if customer_best and customer_risk:
            segment_rows.append(
                self.industry_segment_row(
                    "customer_segment",
                    "mrr / churn_rate",
                    customer_best,
                    customer_risk,
                    f"MRR {self.format_value(customer_best.get('mrr'))}",
                    f"Churn {self.pct_display(customer_risk.get('churn_rate'))}",
                    "Customer segment performance differs by recurring revenue and churn exposure.",
                    "Build a retention review for the highest-churn customer segment.",
                    "不同客户分层在经常性收入和流失风险上存在差异。",
                    "针对流失率最高的客户分层建立留存复盘。",
                )
            )

        hypotheses = [
            {
                "Hypothesis": "Starter or SMB churn may be related to onboarding or support friction.",
                "Hypothesis_zh": "Starter 或 SMB 流失可能与 onboarding 或支持摩擦相关。",
                "Evidence Level": self.low_confidence_hypothesis(),
                "Supporting Evidence": "The current dataset shows churn and support tickets, but does not include ticket categories or product usage.",
                "Supporting Evidence_zh": "当前数据包含流失率和支持工单，但不包含工单类别或产品使用数据。",
                "Additional Data Needed": "Ticket categories, response time, product usage, cancellation reasons, and cohort retention.",
                "Additional Data Needed_zh": "工单类别、响应时间、产品使用、取消原因和 cohort 留存数据。",
                "Data Needed for Validation": "Ticket categories, response time, product usage, cancellation reasons, and cohort retention.",
                "Data Needed for Validation_zh": "工单类别、响应时间、产品使用、取消原因和 cohort 留存数据。",
            }
        ]
        actions = [
            {
                "priority": "High",
                "action": f"Review retention drivers for {plan_risk.get('plan_type', 'the highest-churn plan')}.",
                "action_zh": f"复核 {plan_risk.get('plan_type', '流失率最高套餐')} 的留存驱动因素。",
                "business_rationale": "This plan has the highest observed churn rate in the current dataset.",
                "business_rationale_zh": "该套餐在当前数据集中流失率最高。",
                "suggested_owner": "Customer Success",
                "suggested_owner_zh": "客户成功团队",
                "timeframe": "1 month",
                "timeframe_zh": "1 个月",
                "KPI to track": "churn rate, net MRR retention",
                "KPI to track_zh": "流失率、净 MRR 留存",
            },
            {
                "priority": "Medium",
                "action": "Create a support-ticket watchlist for accounts with rising churn.",
                "action_zh": "为流失压力上升的账户建立支持工单观察清单。",
                "business_rationale": "Support tickets are measurable and can be reviewed with churn, but are not confirmed as a cause.",
                "business_rationale_zh": "支持工单可与流失率共同监控，但当前不能将其确认为流失原因。",
                "suggested_owner": "Support Operations",
                "suggested_owner_zh": "支持运营团队",
                "timeframe": "1 month",
                "timeframe_zh": "1 个月",
                "KPI to track": "support tickets, first response time, churn rate",
                "KPI to track_zh": "支持工单数、首次响应时间、流失率",
            },
        ]
        limitations = [
            "The dataset does not include product usage, cancellation reasons, cohort retention, or customer feedback, so churn causes remain hypotheses.",
            "Profit, gross margin, and LTV are not included; CAC efficiency cannot be fully evaluated without LTV or margin data.",
        ]
        limitations_zh = [
            "数据集不包含产品使用、取消原因、cohort 留存或客户反馈，因此流失原因仍属于假设。",
            "数据集不包含利润、毛利率和 LTV，因此无法完整评估 CAC 效率。",
        ]
        return {
            "Industry": "saas",
            "Executive Summary": [],
            "KPI Snapshot": kpi_snapshot,
            "Derived Metrics": {},
            "Key Insights with Evidence": insights,
            "Segment Deep Dive": segment_rows,
            "Root Cause Hypotheses": hypotheses,
            "Recommended Action Plan": actions,
            "Data Limitations": limitations,
            "Data Limitations_zh": limitations_zh,
        }

    def build_logistics_report_schema(self, analysis_results: dict, user_requirements: str) -> dict:
        industry_analysis = analysis_results.get("industry_analysis", {})
        kpis = industry_analysis.get("kpis", {})
        segments = industry_analysis.get("segments", {})
        preferred_metrics = [
            "total_shipments",
            "total_order_value",
            "total_shipping_cost",
            "shipping_cost_ratio",
            "average_delivery_time_days",
            "delayed_shipments",
            "delay_rate",
            "damage_shipments",
            "damage_rate",
        ]
        kpi_snapshot = self.clean_kpi_rows(kpis, preferred_metrics)

        segment_rows = []
        for dimension in ["region", "carrier", "route", "warehouse"]:
            segment = segments.get(dimension, {})
            best = segment.get("best_by_delivery", {})
            risk = segment.get("risk_by_delay", {})
            if not best or not risk:
                continue
            segment_rows.append(
                self.industry_segment_row(
                    dimension,
                    "delay_rate / delivery_time",
                    best,
                    risk,
                    f"Delay {self.pct_display(best.get('delay_rate'))}; {self.format_value(best.get('average_delivery_time_days'))} days",
                    f"Delay {self.pct_display(risk.get('delay_rate'))}; {self.format_value(risk.get('average_delivery_time_days'))} days",
                    "Operational performance differs by delay rate, delivery time, and shipping cost.",
                    f"Review {dimension} '{risk.get(dimension, self.metric_unavailable())}' delay and cost records.",
                    "运营表现差异主要体现在延迟率、交付时间和运输成本。",
                    f"复核 {dimension} '{risk.get(dimension, self.metric_unavailable())}' 的延迟和成本记录。",
                )
            )

        carrier_risk = segments.get("carrier", {}).get("risk_by_delay", {})
        region_risk = segments.get("region", {}).get("risk_by_delay", {})
        route_risk = segments.get("route", {}).get("risk_by_delay", {})
        insights = [
            {
                "Finding": "Delivery delays are a material operational issue",
                "Finding_zh": "交付延迟是当前样例中的主要运营问题",
                "Evidence": f"Delayed shipments are {self.format_value(kpis.get('delayed_shipments'))}, equal to {self.format_kpi_value('delay_rate', kpis.get('delay_rate'))} of shipments.",
                "Evidence_zh": f"延迟发运量为 {self.format_value(kpis.get('delayed_shipments'))}，占总发运量的 {self.format_kpi_value('delay_rate', kpis.get('delay_rate'))}。",
                "Business Implication": "The operations team should prioritize delay reduction before treating this as a financial profit issue.",
                "Business Implication_zh": "运营团队应优先降低延迟，而不是把该问题误判为利润字段缺失导致的财务问题。",
                "Confidence Level": self.high_confidence(),
            },
            {
                "Finding": f"{carrier_risk.get('carrier', 'A carrier segment')} shows the highest delay pressure",
                "Finding_zh": f"{carrier_risk.get('carrier', '某个承运商分层')} 显示最高延迟压力",
                "Evidence": f"Carrier delay rate is {self.pct_display(carrier_risk.get('delay_rate'))}; average delivery time is {self.format_value(carrier_risk.get('average_delivery_time_days'))} days.",
                "Evidence_zh": f"该承运商延迟率为 {self.pct_display(carrier_risk.get('delay_rate'))}；平均交付时间为 {self.format_value(carrier_risk.get('average_delivery_time_days'))} 天。",
                "Business Implication": "Carrier-level SLA and route performance should be reviewed, but the dataset does not prove the root cause.",
                "Business Implication_zh": "应复核运营 SLA 和路线表现，但当前数据不能证明具体根因。",
                "Confidence Level": self.high_confidence(),
            },
            {
                "Finding": "Damage flags overlap with a subset of shipments",
                "Finding_zh": "部分发运记录出现损坏标记",
                "Evidence": f"Damage-flagged shipments are {self.format_value(kpis.get('damage_shipments'))}, equal to {self.format_kpi_value('damage_rate', kpis.get('damage_rate'))} of shipments.",
                "Evidence_zh": f"损坏标记发运量为 {self.format_value(kpis.get('damage_shipments'))}，占总发运量的 {self.format_kpi_value('damage_rate', kpis.get('damage_rate'))}。",
                "Business Implication": "Damage should be tracked as an operational quality signal; handling or packaging causes require additional data.",
                "Business Implication_zh": "损坏应作为运营质量信号跟踪；处理流程或包装原因需要额外数据验证。",
                "Confidence Level": self.medium_confidence(),
            },
        ]
        hypotheses = [
            {
                "Hypothesis": "Carrier or route execution may be contributing to delays.",
                "Hypothesis_zh": "承运商或路线执行可能影响延迟表现。",
                "Evidence Level": self.medium_confidence(),
                "Supporting Evidence": f"Highest-risk segment examples include {carrier_risk.get('carrier', 'carrier')} and {route_risk.get('route', 'route')}.",
                "Supporting Evidence_zh": f"当前高风险分层包括 {carrier_risk.get('carrier', '承运商')} 和 {route_risk.get('route', '路线')}。",
                "Additional Data Needed": "Carrier SLA, pickup timestamp, route distance, exception codes, weather, and traffic data.",
                "Additional Data Needed_zh": "承运商 SLA、取件时间戳、路线距离、异常代码、天气和交通数据。",
                "Data Needed for Validation": "Carrier SLA, pickup timestamp, route distance, exception codes, weather, and traffic data.",
                "Data Needed for Validation_zh": "承运商 SLA、取件时间戳、路线距离、异常代码、天气和交通数据。",
            }
        ]
        actions = [
            {
                "priority": "High",
                "action": f"Review delay exceptions for {carrier_risk.get('carrier', 'the highest-delay carrier')}.",
                "action_zh": f"复核 {carrier_risk.get('carrier', '延迟率最高承运商')} 的延迟异常。",
                "business_rationale": "This carrier has the highest observed delay pressure in the current dataset.",
                "business_rationale_zh": "该承运商在当前数据中显示最高延迟压力。",
                "suggested_owner": "Logistics Operations",
                "suggested_owner_zh": "物流运营团队",
                "timeframe": "2 weeks",
                "timeframe_zh": "2 周",
                "KPI to track": "delay rate, on-time delivery rate",
                "KPI to track_zh": "延迟率、准时交付率",
            },
            {
                "priority": "High",
                "action": f"Audit route {route_risk.get('route', 'with highest delay')} for delay and cost exceptions.",
                "action_zh": f"审计路线 {route_risk.get('route', '延迟最高路线')} 的延迟与成本异常。",
                "business_rationale": "Route-level review links the action to the specific operational object with the weakest observed performance.",
                "business_rationale_zh": "路线级复核能把行动绑定到当前表现最弱的具体运营对象。",
                "suggested_owner": "Transportation Manager",
                "suggested_owner_zh": "运输管理团队",
                "timeframe": "2 weeks",
                "timeframe_zh": "2 周",
                "KPI to track": "delivery time, shipping cost per shipment",
                "KPI to track_zh": "交付时间、单票运输成本",
            },
            {
                "priority": "Medium",
                "action": "Add structured exception reason tracking for delayed and damaged shipments.",
                "action_zh": "为延迟和损坏发运记录增加结构化异常原因跟踪。",
                "business_rationale": "The dataset identifies delay and damage flags but does not explain operational causes.",
                "business_rationale_zh": "当前数据能识别延迟和损坏标记，但不能解释运营根因。",
                "suggested_owner": "Data Team",
                "suggested_owner_zh": "数据团队",
                "timeframe": "1 month",
                "timeframe_zh": "1 个月",
                "KPI to track": "exception reason completeness",
                "KPI to track_zh": "异常原因记录完整率",
            },
        ]
        limitations = [
            "The dataset does not include route distance, package weight, service level, weather, traffic, or carrier SLA, so operational causes remain hypotheses.",
            "Profit fields are not required for this logistics operational report; delay, damage, delivery time, and shipping cost are the primary KPIs.",
        ]
        limitations_zh = [
            "数据集不包含路线距离、包裹重量、服务等级、天气、交通或承运商 SLA，因此运营根因仍属于假设。",
            "物流运营报告不必须依赖利润字段；延迟、损坏、交付时间和运输成本是本报告的主要 KPI。",
        ]
        return {
            "Industry": "logistics",
            "Executive Summary": [],
            "KPI Snapshot": kpi_snapshot,
            "Derived Metrics": {},
            "Key Insights with Evidence": insights,
            "Segment Deep Dive": segment_rows,
            "Root Cause Hypotheses": hypotheses,
            "Recommended Action Plan": actions,
            "Data Limitations": limitations,
            "Data Limitations_zh": limitations_zh,
        }

    def build_report_schema(self, analysis_results: dict, user_requirements: str) -> dict:
        if self.is_business_insights(analysis_results):
            return self.build_report_schema_from_business_insights(analysis_results, user_requirements)

        industry = self.industry_type(analysis_results)
        if industry == "saas":
            return self.build_saas_report_schema(analysis_results, user_requirements)
        if industry == "logistics":
            return self.build_logistics_report_schema(analysis_results, user_requirements)

        overview = analysis_results.get("overview", {})
        schema = analysis_results.get("schema", {})
        roles = analysis_results.get("field_roles", {})
        kpis = analysis_results.get("kpis", {})
        risks = analysis_results.get("risks", {})
        top_bottom = analysis_results.get("top_bottom", {})
        time_trends = analysis_results.get("time_trends", {})

        sales_col = roles.get("sales")
        profit_col = roles.get("profit")
        product_col = roles.get("product")
        region_col = roles.get("region")
        category_col = roles.get("category")
        segment_col = roles.get("segment")
        date_col = roles.get("date")

        executive_summary = [
            f"Dataset contains {self.format_value(overview.get('row_count'))} rows and {self.format_value(overview.get('column_count'))} columns.",
            "The report is based on local computed metrics, field-role detection, trend summaries, risk checks, and small sample rows.",
        ]
        if user_requirements.strip():
            executive_summary.append(f"User focus: {user_requirements.strip()}")
        if kpis.get("total_sales") is not None:
            executive_summary.append(f"Total sales are {self.format_value(kpis.get('total_sales'))}.")
        if kpis.get("total_profit") is not None:
            executive_summary.append(f"Total profit is {self.format_value(kpis.get('total_profit'))}.")
        if kpis.get("profit_margin_percent") is not None:
            executive_summary.append(f"Overall profit margin is {self.format_value(kpis.get('profit_margin_percent'))}%.")

        derived_metrics = self.build_derived_metrics(
            overview=overview,
            kpis=kpis,
            risks=risks,
        )

        kpi_snapshot = [
            {"metric": key, "value": value}
            for key, value in kpis.items()
        ] or [{"metric": "record_count", "value": overview.get("row_count", 0)}]
        kpi_snapshot.extend(self.derived_metrics_as_kpi_rows(derived_metrics))
        kpi_snapshot = self.normalize_kpi_snapshot(kpi_snapshot)

        insights = self.build_key_insights(
            kpis=kpis,
            risks=risks,
            top_bottom=top_bottom,
            roles=roles,
        )

        segment_deep_dive = self.build_segment_deep_dive(
            top_bottom=top_bottom,
            roles=roles,
            sales_col=sales_col,
            profit_col=profit_col,
        )

        root_cause_hypotheses = self.build_root_cause_hypotheses(
            risks=risks,
            roles=roles,
            time_trends=time_trends,
        )

        recommended_actions = self.build_recommended_actions(
            roles=roles,
            risks=risks,
            top_bottom=top_bottom,
            has_sales=bool(sales_col),
            has_profit=bool(profit_col),
        )

        data_limitations = self.build_data_limitations(
            schema=schema,
            roles=roles,
            date_col=date_col,
            product_col=product_col,
            region_col=region_col,
            category_col=category_col,
            segment_col=segment_col,
            risks=risks,
        )

        return {
            "Industry": "retail",
            "Executive Summary": executive_summary,
            "KPI Snapshot": kpi_snapshot,
            "Derived Metrics": derived_metrics,
            "Key Insights with Evidence": insights,
            "Segment Deep Dive": segment_deep_dive,
            "Root Cause Hypotheses": root_cause_hypotheses,
            "Recommended Action Plan": recommended_actions,
            "Data Limitations": data_limitations,
        }

    def build_key_insights(self, kpis: dict, risks: dict, top_bottom: dict, roles: dict) -> list[dict]:
        insights = []
        sales_col = roles.get("sales")
        profit_col = roles.get("profit")
        product_col = roles.get("product")
        region_col = roles.get("region")

        if profit_col and risks.get("loss_records", {}).get("count", 0) > 0:
            loss = risks["loss_records"]
            insights.append(
                {
                    "Finding": "Loss-making records require management attention",
                    "Evidence": (
                        f"Loss-making records: {self.format_value(loss.get('count'))}; "
                        f"total loss: {self.format_value(loss.get('total_loss'))}."
                    ),
                    "Business Implication": "Use the segment deep dive to identify where negative-profit records should be reviewed first.",
                    "Confidence Level": self.high_confidence(),
                }
            )

        if risks.get("high_discount_loss_records", {}).get("count", 0) > 0:
            discount_loss = risks["high_discount_loss_records"]
            discount_evidence = f"High-discount loss records: {self.format_value(discount_loss.get('count'))}."
            if discount_loss.get("discount_threshold") is not None:
                discount_evidence = (
                    f"High-discount loss records: {self.format_value(discount_loss.get('count'))}; "
                    f"high-discount threshold: {self.format_value(discount_loss.get('discount_threshold'))}."
                )
            insights.append(
                {
                    "Finding": "High-discount loss records may indicate promotion pressure",
                    "Evidence": discount_evidence,
                    "Business Implication": "Discount policy may need review where discounting coincides with negative profit.",
                    "Confidence Level": self.medium_confidence(),
                }
            )

        if sales_col and product_col:
            top_product = self.first_top_bottom(top_bottom, sales_col, product_col, "top")
            if top_product:
                product_name, sales_value, _ = self.segment_object_and_value(top_product, sales_col)
                insights.append(
                    {
                        "Finding": "A product-level revenue concentration exists",
                        "Evidence": f"Top {product_col} by {sales_col}: {product_name} ({sales_value}).",
                        "Business Implication": "The highest-contributing products should be reviewed for margin quality and concentration exposure.",
                        "Confidence Level": self.medium_confidence(),
                    }
                )

        if profit_col and region_col:
            bottom_region = self.first_top_bottom(top_bottom, profit_col, region_col, "bottom")
            if bottom_region:
                region_name, profit_value, _ = self.segment_object_and_value(bottom_region, profit_col)
                insights.append(
                    {
                        "Finding": "Some regions show relatively weaker profit contribution",
                        "Evidence": f"Weakest {region_col} by {profit_col}: {region_name} ({profit_value}).",
                        "Business Implication": "Regional profitability differences should be reviewed before assigning a cause.",
                        "Confidence Level": self.medium_confidence(),
                    }
                )

        if not insights:
            insights.append(
                {
                    "Finding": "Limited business-specific fields were detected",
                    "Evidence": "The analysis did not identify enough sales, profit, segment, or time fields for strong business conclusions.",
                    "Business Implication": "The report should be treated as a general data quality and descriptive analysis.",
                    "Confidence Level": self.low_confidence_hypothesis(),
                }
            )

        return insights

    def build_segment_deep_dive(self, top_bottom: dict, roles: dict, sales_col: str | None, profit_col: str | None) -> list[dict]:
        dimensions = [
            roles.get("region"),
            roles.get("category"),
            roles.get("segment"),
            roles.get("product"),
            roles.get("customer"),
        ]
        rows = []
        for dimension in [item for item in dimensions if item]:
            metric = None
            if profit_col and dimension in top_bottom.get(profit_col, {}):
                metric = profit_col
            elif dimension not in {roles.get("product"), roles.get("customer")} and sales_col and dimension in top_bottom.get(sales_col, {}):
                metric = sales_col
            if not metric:
                continue

            best_row = self.first_top_bottom(top_bottom, metric, dimension, "top")
            weakest_row = self.first_top_bottom(top_bottom, metric, dimension, "bottom")
            best_object, best_value, _ = self.segment_object_and_value(best_row, metric)
            weakest_object, weakest_value_display, weakest_value = self.segment_object_and_value(weakest_row, metric)
            rows.append(
                {
                    "segment": dimension,
                    "metric": metric,
                    "best_object": best_object,
                    "best_value": best_value,
                    "weakest_object": weakest_object,
                    "weakest_value": weakest_value_display,
                    "business_interpretation": self.segment_interpretation(metric, weakest_value),
                    "recommended_follow_up": self.segment_follow_up(dimension, weakest_object, metric),
                }
            )

        return rows or [
            {
                "segment": "N/A",
                "observations": ["No suitable segment fields were detected for deep-dive analysis."],
            }
        ]

    def weakest_profit_object(self, top_bottom: dict, profit_col: str | None, dimension: str | None) -> tuple[str | None, str | None]:
        if not profit_col or not dimension:
            return None, None
        row = self.first_top_bottom(top_bottom, profit_col, dimension, "bottom")
        object_name, value_display, _ = self.segment_object_and_value(row, profit_col)
        if object_name == self.metric_unavailable():
            return None, None
        return object_name, value_display

    def build_root_cause_hypotheses(self, risks: dict, roles: dict, time_trends: dict) -> list[dict]:
        hypotheses = []
        if risks.get("high_discount_loss_records", {}).get("count", 0) > 0:
            hypotheses.append(
                {
                    "Hypothesis": "Discounting may be contributing to profit leakage.",
                    "Evidence Level": self.medium_confidence(),
                    "Supporting Evidence": "High-discount records overlap with loss-making records.",
                    "Additional Data Needed": "Promotion rules, product cost, approved discount policy, and customer contract terms.",
                    "Data Needed for Validation": "Promotion rules, product cost, approved discount policy, and customer contract terms.",
                }
            )
        if risks.get("loss_records", {}).get("count", 0) > 0:
            hypotheses.append(
                {
                    "Hypothesis": "Losses may be concentrated in specific products, regions, or customers.",
                    "Evidence Level": self.medium_confidence(),
                    "Supporting Evidence": "Negative-profit records are present; segment-level Bottom analysis should be reviewed.",
                    "Additional Data Needed": "Cost drivers, fulfillment costs, return rates, and customer-level contract terms.",
                    "Data Needed for Validation": "Cost drivers, fulfillment costs, return rates, and customer-level contract terms.",
                }
            )
        if roles.get("date") and time_trends.get("rows"):
            hypotheses.append(
                {
                    "Hypothesis": "Seasonality or monthly operational patterns may affect performance.",
                    "Evidence Level": self.low_confidence_hypothesis(),
                    "Supporting Evidence": "A date field was detected and monthly trend data is available.",
                    "Additional Data Needed": "Multiple years of comparable history, campaign calendar, inventory constraints, and market events.",
                    "Data Needed for Validation": "Multiple years of comparable history, campaign calendar, inventory constraints, and market events.",
                }
            )
        if not hypotheses:
            hypotheses.append(
                {
                    "Hypothesis": "No strong root-cause hypothesis is supported by the current computed results.",
                    "Evidence Level": self.low_confidence_hypothesis(),
                    "Supporting Evidence": "The available analysis does not show enough risk, segment, or trend evidence.",
                    "Additional Data Needed": "Clear sales, profit, date, product, customer, and operating cost fields.",
                    "Data Needed for Validation": "Clear sales, profit, date, product, customer, and operating cost fields.",
                }
            )
        return hypotheses

    def build_recommended_actions(
        self,
        roles: dict,
        risks: dict,
        top_bottom: dict,
        has_sales: bool,
        has_profit: bool,
    ) -> list[dict]:
        actions = []
        profit_col = roles.get("profit")
        lowest_region, lowest_region_value = self.weakest_profit_object(top_bottom, profit_col, roles.get("region"))
        lowest_category, lowest_category_value = self.weakest_profit_object(top_bottom, profit_col, roles.get("category"))
        lowest_product, lowest_product_value = self.weakest_profit_object(top_bottom, profit_col, roles.get("product"))
        lowest_customer, lowest_customer_value = self.weakest_profit_object(top_bottom, profit_col, roles.get("customer"))

        if risks.get("high_discount_loss_records", {}).get("count", 0) > 0:
            actions.append(
                {
                    "priority": "High",
                    "action": f"Review and escalate approval for {self.format_value(risks['high_discount_loss_records'].get('count'))} high-discount loss transactions.",
                    "business_rationale": "High-discount records overlap with loss-making records in the computed results.",
                    "suggested_owner": "Sales Operations",
                    "timeframe": "2 weeks",
                    "KPI to track": "loss-making order ratio, average discount",
                }
            )

        if lowest_product:
            actions.append(
                {
                    "priority": "High",
                    "action": f"Audit {lowest_product} pricing and discount records.",
                    "business_rationale": f"{lowest_product} is the lowest-profit product in the segment analysis, with {lowest_product_value} profit.",
                    "suggested_owner": "Finance",
                    "timeframe": "2 weeks",
                    "KPI to track": "product profit, loss-making order ratio",
                }
            )

        if lowest_category:
            actions.append(
                {
                    "priority": "High",
                    "action": f"Review {lowest_category} category margin structure.",
                    "business_rationale": f"{lowest_category} is the relatively weakest category by profit, with {lowest_category_value} profit.",
                    "suggested_owner": "Sales Director",
                    "timeframe": "1 month",
                    "KPI to track": "category profit margin, gross margin",
                }
            )

        if lowest_region:
            actions.append(
                {
                    "priority": "Medium",
                    "action": f"Review {lowest_region} regional margin performance.",
                    "business_rationale": f"{lowest_region} is the relatively weakest region by profit, with {lowest_region_value} profit.",
                    "suggested_owner": "Sales Operations",
                    "timeframe": "1 month",
                    "KPI to track": "regional profit margin",
                }
            )

        if lowest_customer:
            actions.append(
                {
                    "priority": "Medium",
                    "action": f"Review {lowest_customer} account profitability records.",
                    "business_rationale": f"{lowest_customer} is the relatively weakest customer by profit, with {lowest_customer_value} profit.",
                    "suggested_owner": "Sales Operations",
                    "timeframe": "1 month",
                    "KPI to track": "customer profit margin",
                }
            )

        if risks.get("loss_records", {}).get("count", 0) > 0 and not any([lowest_product, lowest_category, lowest_region, lowest_customer]):
            actions.append(
                {
                    "priority": "High",
                    "action": "Create a loss-making order review by available segment fields.",
                    "business_rationale": "The data shows negative-profit records, but no specific profit segment object was available.",
                    "suggested_owner": "Finance",
                    "timeframe": "2 weeks",
                    "KPI to track": "total loss, loss-making order ratio",
                }
            )

        if risks.get("numeric_outliers"):
            actions.append(
                {
                    "priority": "Medium",
                    "action": "Sample-check numeric anomalies before using them for management decisions.",
                    "business_rationale": "Outliers may represent large valid deals, unusual orders, or data quality issues.",
                    "suggested_owner": "Data Team",
                    "timeframe": "2 weeks",
                    "KPI to track": "validated anomaly rate, data correction rate",
                }
            )

        if roles.get("date"):
            actions.append(
                {
                    "priority": "Low",
                    "action": "Monitor monthly trend changes and flag unusual months.",
                    "business_rationale": "Trend monitoring helps identify periods that deserve further review, without assuming the cause from this dataset alone.",
                    "suggested_owner": "Data Team",
                    "timeframe": "1 quarter",
                    "KPI to track": "monthly revenue growth, monthly profit margin",
                }
            )

        if not actions:
            actions.append(
                {
                    "priority": "Medium",
                    "action": "Confirm business field mappings before drawing deeper conclusions.",
                    "business_rationale": "Reliable business reporting depends on correctly identified sales, profit, date, product, and customer fields.",
                    "suggested_owner": "Data Team",
                    "timeframe": "2 weeks",
                    "KPI to track": "Field mapping completeness",
                }
            )
        return actions

    def build_data_limitations(
        self,
        schema: dict,
        roles: dict,
        date_col: str | None,
        product_col: str | None,
        region_col: str | None,
        category_col: str | None,
        segment_col: str | None,
        risks: dict,
    ) -> list[str]:
        limitations = []
        if not roles.get("sales"):
            limitations.append("No sales or revenue field was confidently identified.")
        if not roles.get("profit"):
            limitations.append("No profit or margin field was confidently identified.")
        if not date_col:
            limitations.append("No reliable date field was identified, so trend conclusions are limited.")
        if not any([product_col, region_col, category_col, segment_col]):
            limitations.append("No strong segment fields were identified for business deep dives.")
        if risks.get("high_missing_columns"):
            limitations.append("Some fields have high missing rates and may reduce reliability.")
        if not schema.get("columns"):
            limitations.append("Schema metadata is missing from the analysis result.")
        unsupported_cause_columns = [
            "competition",
            "competitor",
            "market share",
            "inventory",
            "stock",
            "clearance",
            "lifecycle",
            "return",
            "churn",
            "behavior",
        ]
        available_columns = " ".join(schema.get("columns", [])).lower()
        if not any(column in available_columns for column in unsupported_cause_columns):
            limitations.append(
                "The dataset does not include market competition, inventory, customer behavior, or product lifecycle fields; those causes should not be treated as confirmed."
            )
        if not limitations:
            limitations.append("The report is based on computed summaries and samples, not a manual review of every raw record.")
        return limitations

    def kpi_interpretation(self, metric: str, settings: dict | None = None, value=None) -> str:
        settings = self.normalize_report_settings(settings)
        number = self.to_number(value)
        if isinstance(value, str) and "%" in value and number is not None:
            number = number / 100
        if self.is_chinese(settings):
            if metric in {"profit_margin", "profit_margin_percent"}:
                percent = number if number is not None and number <= 1 else (number / 100 if number is not None else None)
                if percent is None:
                    return "当前数据无法计算利润率，盈利质量判断受限。"
                if percent < 0:
                    return "整体为负利润率，应优先复核亏损来源。"
                return "利润为正，但需要结合亏损记录占比和亏损金额判断利润质量。"
            if metric == "loss_record_ratio":
                if number is None:
                    return "当前数据无法计算亏损记录占比。"
                if number >= 0.10:
                    return "亏损记录占比较高，适合优先做订单级利润复盘。"
                return "亏损记录占比较低，但仍应抽查大额亏损记录。"
            if metric == "loss_amount_vs_total_profit":
                if number is None:
                    return "当前数据无法衡量亏损金额对总利润的侵蚀。"
                if number >= 0.50:
                    return "亏损金额相对总利润较高，说明利润质量需要重点复核。"
                return "亏损金额对总利润有可见影响，应结合分群继续定位。"
            if metric == "high_discount_loss_ratio":
                if number is None:
                    return "当前数据无法判断高折扣与亏损的重叠程度。"
                if number <= 0:
                    return "当前未发现高折扣亏损重叠记录，但仍应监控折扣变化。"
                if number >= 0.50:
                    return "多数亏损记录与高折扣重叠，折扣审批应优先复核。"
                return "部分亏损记录与高折扣重叠，建议抽样检查折扣规则。"
            if metric == "discount_risk_level":
                return f"折扣风险等级为 {self.localize_text(value, settings)}，用于确定折扣复核优先级。"
            if metric == "average_discount_percent":
                return "用于判断折扣强度是否可能影响利润质量。"
            if metric == "total_profit":
                return "用于衡量收入最终转化出的利润规模，应与亏损金额一起解读。"
            if metric == "total_sales":
                return "收入规模需要结合利润率和亏损记录占比解读，不能单独代表经营质量。"
            if metric == "average_order_value":
                return "用于观察订单价值结构，并辅助判断大额订单异常。"
            if metric == "current_mrr":
                return "衡量 SaaS 经常性收入规模，是增长质量分析的核心指标。"
            if metric == "current_arr":
                return "反映年度化经常性收入规模，适合观察合同收入基础。"
            if metric == "mrr_growth_percent":
                return "衡量 MRR 从首期到末期的增长动能。"
            if metric == "total_new_customers":
                return "反映获客规模，需要与流失客户数一起判断净增长质量。"
            if metric == "total_churned_customers":
                return "反映客户流失压力，应与新增客户和 MRR 增长一起解读。"
            if metric == "average_churn_rate_percent":
                return "用于衡量留存压力，应该按套餐和客户分层进一步拆解。"
            if metric == "total_expansion_revenue":
                return "反映现有客户扩张贡献，但不应被等同为总销售额。"
            if metric == "total_support_tickets":
                return "可作为留存风险观察信号，但不能单独证明流失原因。"
            if metric == "average_cac":
                return "用于观察获客成本水平，完整 ROI 仍需要 LTV 或毛利数据。"
            if metric == "total_shipments":
                return "表示本次物流运营分析覆盖的发运规模。"
            if metric == "total_order_value":
                return "表示发运订单价值规模，可与运输成本联动观察。"
            if metric == "total_shipping_cost":
                return "表示运输成本压力，应结合路线、承运商和延迟率拆解。"
            if metric == "shipping_cost_ratio":
                return "衡量运输成本占订单价值的比例，用于观察成本压力。"
            if metric == "average_delivery_time_days":
                return "衡量平均交付效率，应结合延迟率和承运商表现解读。"
            if metric == "delayed_shipments":
                return "表示已被标记为延迟的发运记录数量。"
            if metric == "delay_rate":
                return "衡量延迟问题的覆盖面，是物流运营优先级指标。"
            if metric == "damage_shipments":
                return "表示有损坏标记的发运记录数量。"
            if metric == "damage_rate":
                return "衡量运营质量风险，但具体原因需要额外字段验证。"

        if metric in {"profit_margin", "profit_margin_percent"}:
            percent = number if number is not None and number <= 1 else (number / 100 if number is not None else None)
            if percent is None:
                return "Profit margin cannot be calculated from the current dataset."
            if percent < 0:
                return "Overall margin is negative, so loss sources should be reviewed first."
            return "Profit is positive, but profit quality should be read together with loss-making records and loss exposure."
        if metric == "loss_record_ratio":
            if number is None:
                return "Loss-making record ratio cannot be calculated from the current dataset."
            if number >= 0.10:
                return "A meaningful share of records are loss-making, making order-level review a priority."
            return "Loss-making records are limited, but large losses should still be sampled."
        if metric == "loss_amount_vs_total_profit":
            if number is None:
                return "Loss exposure versus total profit cannot be calculated from the current dataset."
            if number >= 0.50:
                return "Loss exposure is large relative to total profit, so profit quality needs review."
            return "Loss exposure is visible and should be traced by segment."
        if metric == "high_discount_loss_ratio":
            if number is None:
                return "Overlap between high discounts and losses cannot be calculated from the current dataset."
            if number <= 0:
                return "No high-discount loss overlap is currently detected, but discount changes should still be monitored."
            if number >= 0.50:
                return "Most loss-making records overlap with high discounts, making discount approval review a priority."
            return "Some loss-making records overlap with high discounts; discount rules should be sampled."
        if metric == "discount_risk_level":
            return f"Discount risk level is {value}, guiding the priority of discount review."
        if metric == "average_discount_percent":
            return "Helps assess whether discount intensity may be affecting profit quality."
        if metric == "total_profit":
            return "Shows realized profit scale and should be read alongside loss exposure."
        if metric == "total_sales":
            return "Revenue scale should be assessed together with margin and loss-making record ratio."
        if metric == "average_order_value":
            return "Helps assess order value structure and spot potential large-order exposure."
        if metric == "current_mrr":
            return "Measures SaaS recurring revenue scale and anchors growth-quality analysis."
        if metric == "current_arr":
            return "Shows annualized recurring revenue base across the available records."
        if metric == "mrr_growth_percent":
            return "Shows recurring revenue momentum from the first to the last available period."
        if metric == "total_new_customers":
            return "Shows acquisition volume and should be read with churned customers."
        if metric == "total_churned_customers":
            return "Shows retention pressure and should be read with new customers and MRR growth."
        if metric == "average_churn_rate_percent":
            return "Measures retention pressure and should be drilled down by plan and customer segment."
        if metric == "total_expansion_revenue":
            return "Shows expansion contribution from existing customers; it should not be treated as total sales."
        if metric == "total_support_tickets":
            return "Can be monitored as a retention-risk signal, but does not prove churn cause by itself."
        if metric == "average_cac":
            return "Shows acquisition cost level; full ROI still needs LTV or gross margin."
        if metric == "total_shipments":
            return "Shows the operational shipment volume covered by this analysis."
        if metric == "total_order_value":
            return "Shows shipment order value and should be read with shipping cost."
        if metric == "total_shipping_cost":
            return "Shows transportation cost pressure to drill down by route and carrier."
        if metric == "shipping_cost_ratio":
            return "Measures shipping cost as a share of order value."
        if metric == "average_delivery_time_days":
            return "Measures delivery efficiency and should be read with delay rate."
        if metric == "delayed_shipments":
            return "Shows how many shipments are explicitly flagged as delayed."
        if metric == "delay_rate":
            return "Measures how widespread the delay issue is across shipments."
        if metric == "damage_shipments":
            return "Shows how many shipments are explicitly flagged as damaged."
        if metric == "damage_rate":
            return "Measures operational quality risk, but causes require additional data."

        interpretations = {
            "record_count": "Shows the amount of data supporting this report.",
            "total_sales": "Indicates overall revenue scale.",
            "average_sales": "Shows average transaction or row-level sales value.",
            "total_profit": "Shows aggregate financial contribution.",
            "profit_margin_percent": "Measures how efficiently sales convert into profit.",
            "total_quantity": "Indicates total unit volume.",
            "average_discount_percent": "Shows typical discounting intensity.",
            "order_count": "Indicates order volume.",
            "average_order_value": "Shows average revenue per order.",
            "loss_record_ratio": "Shows how much of the dataset is directly loss-making.",
            "loss_amount_vs_total_profit": "Compares total negative-profit exposure with reported total profit.",
            "high_discount_loss_ratio": "Shows how often loss-making records overlap with high discounting.",
            "profit_margin": "Shows total profit as a share of total sales.",
            "discount_risk_level": "Summarizes discount-related risk using average discount and high-discount loss records.",
        }
        chinese_interpretations = {
            "record_count": "表示支撑本报告的数据量。",
            "total_sales": "表示整体收入规模。",
            "average_sales": "表示单笔交易或单行记录的平均销售额。",
            "total_profit": "表示整体财务贡献。",
            "profit_margin_percent": "衡量销售额转化为利润的效率。",
            "total_quantity": "表示总销量或总件数。",
            "average_discount_percent": "表示典型折扣强度。",
            "order_count": "表示订单规模。",
            "average_order_value": "表示平均订单收入。",
            "loss_record_ratio": "表示数据中直接亏损记录的占比。",
            "loss_amount_vs_total_profit": "比较亏损金额对总利润的侵蚀程度。",
            "high_discount_loss_ratio": "表示亏损记录中有多少同时属于高折扣记录。",
            "profit_margin": "表示总利润占总销售额的比例。",
            "discount_risk_level": "基于平均折扣和高折扣亏损记录汇总折扣风险。",
        }
        if self.is_chinese(settings):
            return chinese_interpretations.get(metric, "用于业务复盘的辅助指标。")
        return interpretations.get(metric, "Useful supporting metric for business review.")

    def executive_summary_text(self, report_schema: dict, settings: dict | None = None) -> str:
        settings = self.normalize_report_settings(settings)
        industry = report_schema.get("Industry", "generic")
        kpi_values = {
            item.get("metric"): item.get("value")
            for item in report_schema.get("KPI Snapshot", [])
            if isinstance(item, dict)
        }
        derived_metrics = report_schema.get("Derived Metrics", {})
        insights = report_schema["Key Insights with Evidence"]
        actions = report_schema["Recommended Action Plan"]
        limitations = report_schema.get("Data Limitations", [])
        main_risk = next(
            (item["Finding"] for item in insights if "loss" in item["Finding"].lower() or "risk" in item["Finding"].lower()),
            insights[0]["Finding"] if insights else "No major risk was identified from the computed results.",
        )
        priority_action = actions[0]["action"] if actions else "Confirm field mappings and rerun the analysis."
        total_sales = self.format_value(kpi_values.get("total_sales"))
        total_profit = self.format_value(kpi_values.get("total_profit"))
        order_count = self.format_value(kpi_values.get("order_count"))
        profit_margin = self.derived_metric_display(derived_metrics, "profit_margin")
        loss_record_ratio = self.derived_metric_display(derived_metrics, "loss_record_ratio")
        loss_amount_vs_profit = self.derived_metric_display(derived_metrics, "loss_amount_vs_total_profit")
        high_discount_loss_ratio = self.derived_metric_display(derived_metrics, "high_discount_loss_ratio")
        average_order_value = self.derived_metric_display(derived_metrics, "average_order_value")
        discount_risk = self.derived_metric_display(derived_metrics, "discount_risk_level")
        confidence = self.high_confidence()
        if self.metric_unavailable() in {profit_margin, loss_record_ratio, loss_amount_vs_profit}:
            confidence = self.medium_confidence()
        localized_limitations = (
            report_schema.get("Data Limitations_zh")
            if self.is_chinese(settings) and report_schema.get("Data Limitations_zh")
            else limitations
        )
        limitation = (
            localized_limitations[0]
            if localized_limitations
            else "The report is based on computed summaries and samples, not a manual review of every raw record."
        )

        if industry == "saas":
            if self.is_chinese(settings):
                return "\n".join(
                    [
                        f"- **总体表现:** 最新月度快照 MRR 为 {self.format_kpi_value('current_mrr', kpi_values.get('current_mrr'))}，ARR 为 {self.format_kpi_value('current_arr', kpi_values.get('current_arr'))}；MRR 增长率为 {self.format_kpi_value('mrr_growth_percent', kpi_values.get('mrr_growth_percent'))}。",
                        f"- **主要管理问题:** 平均流失率为 {self.format_kpi_value('average_churn_rate_percent', kpi_values.get('average_churn_rate_percent'))}，需要优先复核最高流失套餐和客户分层。",
                        f"- **业务影响:** 新增客户数为 {self.format_kpi_value('total_new_customers', kpi_values.get('total_new_customers'))}，流失客户数为 {self.format_kpi_value('total_churned_customers', kpi_values.get('total_churned_customers'))}；增长质量需要结合 churn 和支持工单判断。",
                        f"- **优先行动:** {(self.localized_field(actions[0], 'action', settings) if actions else '复核 SaaS 留存和分层表现').rstrip('。.')}。",
                        f"- **置信度 / 限制:** 高置信度。{self.localize_text(limitation, settings)}",
                    ]
                )
            return "\n".join(
                [
                    f"- **Overall performance:** Current MRR is {self.format_kpi_value('current_mrr', kpi_values.get('current_mrr'))}, current ARR is {self.format_kpi_value('current_arr', kpi_values.get('current_arr'))}, and MRR growth is {self.format_kpi_value('mrr_growth_percent', kpi_values.get('mrr_growth_percent'))}.",
                    f"- **Main management issue:** Average churn rate is {self.format_kpi_value('average_churn_rate_percent', kpi_values.get('average_churn_rate_percent'))}; the highest-churn plan and customer segment need priority review.",
                    f"- **Business impact:** New customers are {self.format_kpi_value('total_new_customers', kpi_values.get('total_new_customers'))}, while churned customers are {self.format_kpi_value('total_churned_customers', kpi_values.get('total_churned_customers'))}; growth quality should be read with churn and support workload.",
                    f"- **Priority action:** {actions[0]['action'] if actions else 'Review SaaS retention and segment performance.'}",
                    f"- **Confidence / limitation:** High confidence. {limitation}",
                ]
            )

        if industry == "logistics":
            if self.is_chinese(settings):
                return "\n".join(
                    [
                        f"- **总体表现:** 总发运量为 {self.format_kpi_value('total_shipments', kpi_values.get('total_shipments'))}，平均交付时间为 {self.format_kpi_value('average_delivery_time_days', kpi_values.get('average_delivery_time_days'))} 天，运输成本率为 {self.format_kpi_value('shipping_cost_ratio', kpi_values.get('shipping_cost_ratio'))}。",
                        f"- **主要管理问题:** 延迟发运量为 {self.format_kpi_value('delayed_shipments', kpi_values.get('delayed_shipments'))}，延迟率为 {self.format_kpi_value('delay_rate', kpi_values.get('delay_rate'))}；应优先复核延迟率最高的承运商和路线。",
                        f"- **运营影响:** 损坏发运量为 {self.format_kpi_value('damage_shipments', kpi_values.get('damage_shipments'))}，损坏率为 {self.format_kpi_value('damage_rate', kpi_values.get('damage_rate'))}；损坏是质量信号，但当前数据不能证明具体原因。",
                        f"- **优先行动:** {(self.localized_field(actions[0], 'action', settings) if actions else '复核物流延迟和损坏异常').rstrip('。.')}。",
                        f"- **置信度 / 限制:** 高置信度。{self.localize_text(limitation, settings)}",
                    ]
                )
            return "\n".join(
                [
                    f"- **Overall performance:** Total shipments are {self.format_kpi_value('total_shipments', kpi_values.get('total_shipments'))}, average delivery time is {self.format_kpi_value('average_delivery_time_days', kpi_values.get('average_delivery_time_days'))} days, and shipping cost ratio is {self.format_kpi_value('shipping_cost_ratio', kpi_values.get('shipping_cost_ratio'))}.",
                    f"- **Main management issue:** Delayed shipments are {self.format_kpi_value('delayed_shipments', kpi_values.get('delayed_shipments'))}, with delay rate of {self.format_kpi_value('delay_rate', kpi_values.get('delay_rate'))}; the highest-delay carrier and route should be reviewed first.",
                    f"- **Operational impact:** Damage-flagged shipments are {self.format_kpi_value('damage_shipments', kpi_values.get('damage_shipments'))}, with damage rate of {self.format_kpi_value('damage_rate', kpi_values.get('damage_rate'))}; damage is a quality signal, but the current data does not prove the cause.",
                    f"- **Priority action:** {actions[0]['action'] if actions else 'Review logistics delay and damage exceptions.'}",
                    f"- **Confidence / limitation:** High confidence. {limitation}",
                ]
            )

        if self.is_chinese(settings):
            localized_action = self.localize_text(priority_action, settings).rstrip("。.")
            localized_discount_risk = self.localize_text(discount_risk, settings)
            localized_confidence = self.localize_confidence(confidence, settings)
            return "\n".join(
                [
                    f"- **总体表现:** 总销售额为 {total_sales}，总利润为 {total_profit}，利润率为 {self.localize_text(profit_margin, settings)}；"
                    f"订单数为 {order_count}，平均订单金额为 {self.localize_text(average_order_value, settings)}。",
                    f"- **主要管理问题:** {self.localize_text(main_risk, settings)}。亏损记录占比为 {self.localize_text(loss_record_ratio, settings)}，"
                    f"高折扣亏损占亏损记录比例为 {self.localize_text(high_discount_loss_ratio, settings)}，折扣风险等级为 {localized_discount_risk}。",
                    f"- **财务影响:** 亏损金额相当于总利润的 {self.localize_text(loss_amount_vs_profit, settings)}；"
                    "该指标用于衡量负利润记录对已实现利润的侵蚀程度。",
                    f"- **优先行动:** {localized_action}。",
                    f"- **置信度 / 限制:** {localized_confidence}。{self.localize_text(limitation, settings)}",
                ]
            )

        return "\n".join(
            [
                f"- **Overall performance:** Total sales are {total_sales}, total profit is {total_profit}, and profit margin is {profit_margin}; "
                f"order count is {order_count}, with average order value of {average_order_value}.",
                f"- **Main management issue:** {main_risk}. Loss-making records represent {loss_record_ratio} of records; "
                f"high-discount loss records represent {high_discount_loss_ratio} of loss-making records; discount risk level is {discount_risk}.",
                f"- **Financial impact:** Loss amount equals {loss_amount_vs_profit} of total profit; "
                "this metric quantifies how much negative-profit activity offsets reported profit.",
                f"- **Priority action:** {priority_action}",
                f"- **Confidence / limitation:** {confidence}. {limitation}",
            ]
        )

    def render_schema_markdown(
        self,
        report_schema: dict,
        fallback_reason: str | None = None,
        report_settings: dict | None = None,
    ) -> str:
        settings = self.normalize_report_settings(report_settings)
        chinese = self.is_chinese(settings)
        title = "业务绩效洞察报告" if chinese else "Business Performance Insight Report"
        labels = {
            "generated_at": "生成时间" if chinese else "Generated at",
            "executive_summary": "执行摘要" if chinese else "Executive Summary",
            "kpi_snapshot": "KPI 快照" if chinese else "KPI Snapshot",
            "key_insights": "关键洞察与证据" if chinese else "Key Insights with Evidence",
            "segment_deep_dive": "分群深入分析" if chinese else "Segment Deep Dive",
            "root_cause_hypotheses": "根因假设" if chinese else "Root Cause Hypotheses",
            "recommended_action_plan": "建议行动计划" if chinese else "Recommended Action Plan",
            "data_limitations": "数据限制" if chinese else "Data Limitations",
            "finding": "发现" if chinese else "Finding",
            "evidence": "证据" if chinese else "Evidence",
            "business_implication": "业务影响" if chinese else "Business Implication",
            "confidence_level": "置信度" if chinese else "Confidence Level",
        }
        lines = [
            f"# {title}",
            "",
            f"{labels['generated_at']}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"## 1. {labels['executive_summary']}",
            "",
            self.executive_summary_text(report_schema, settings),
            "",
        ]

        lines.extend(["", f"## 2. {labels['kpi_snapshot']}"])
        kpi_rows = []
        for item in report_schema["KPI Snapshot"]:
            kpi_rows.append(
                [
                    self.localize_metric_name(item["metric"], settings),
                    self.localize_text(self.format_kpi_value(item["metric"], item["value"]), settings),
                    self.kpi_interpretation(item["metric"], settings, item.get("value")),
                ]
            )
        kpi_headers = ["指标", "数值", "业务解读"] if chinese else ["Metric", "Value", "Business Interpretation"]
        lines.extend(self.markdown_table(kpi_headers, kpi_rows))

        lines.extend(["", f"## 3. {labels['key_insights']}"])
        insights_to_render = report_schema["Key Insights with Evidence"]
        if settings["length"] == "Brief":
            insights_to_render = insights_to_render[:3]
        for insight in insights_to_render:
            finding = self.localized_field(insight, "Finding", settings)
            lines.extend(
                [
                    f"### {finding}",
                    f"- **{labels['finding']}:** {finding}",
                    f"- **{labels['evidence']}:** {self.localized_field(insight, 'Evidence', settings)}",
                    f"- **{labels['business_implication']}:** {self.localized_field(insight, 'Business Implication', settings)}",
                    f"- **{labels['confidence_level']}:** {self.localize_confidence(insight['Confidence Level'], settings)}",
                    "",
                ]
            )

        lines.extend([f"## 4. {labels['segment_deep_dive']}"])
        segment_rows = self.segment_management_rows(report_schema["Segment Deep Dive"], settings)
        segment_headers = (
            ["分群字段", "指标", "最佳对象", "最佳值", "相对较弱对象", "较弱值", "业务解读", "建议跟进"]
            if chinese
            else [
                "Segment Field",
                "Metric",
                "Best Object",
                "Best Value",
                "Weakest Object",
                "Weakest Value",
                "Business Interpretation",
                "Recommended Follow-up",
            ]
        )
        lines.extend(
            self.markdown_table(
                segment_headers,
                segment_rows,
            )
        )

        lines.extend([f"## 5. {labels['root_cause_hypotheses']}"])
        hypothesis_rows = [
            [
                self.localized_field(item, "Hypothesis", settings),
                self.localize_confidence(item["Evidence Level"], settings),
                self.localized_field(item, "Supporting Evidence", settings),
                self.localized_field(item, "Data Needed for Validation", settings)
                or self.localized_field(item, "Additional Data Needed", settings),
            ]
            for item in report_schema["Root Cause Hypotheses"]
        ]
        hypothesis_headers = (
            ["假设", "证据等级", "支撑证据", "验证所需数据"]
            if chinese
            else ["Hypothesis", "Evidence Level", "Supporting Evidence", "Data Needed for Validation"]
        )
        lines.extend(
            self.markdown_table(
                hypothesis_headers,
                hypothesis_rows,
            )
        )

        lines.extend(["", f"## 6. {labels['recommended_action_plan']}"])
        action_rows = []
        actions_to_render = report_schema["Recommended Action Plan"]
        if settings["length"] == "Brief":
            actions_to_render = actions_to_render[:4]
        for action in actions_to_render:
            action_rows.append(
                [
                    self.localize_priority(action["priority"], settings),
                    self.localized_field(action, "action", settings),
                    self.localized_field(action, "business_rationale", settings),
                    self.localized_field(action, "suggested_owner", settings),
                    self.localized_field(action, "timeframe", settings),
                    self.localized_field(action, "KPI to track", settings),
                ]
            )
        action_headers = (
            ["优先级", "行动", "理由", "负责人", "时间范围", "跟踪 KPI"]
            if chinese
            else ["Priority", "Action", "Rationale", "Owner", "Timeframe", "KPI to Track"]
        )
        lines.extend(
            self.markdown_table(
                action_headers,
                action_rows,
            )
        )

        lines.extend(["", f"## 7. {labels['data_limitations']}"])
        data_limitations = (
            report_schema.get("Data Limitations_zh")
            if chinese and report_schema.get("Data Limitations_zh")
            else report_schema["Data Limitations"]
        )
        lines.extend([f"- {self.localize_text(item, settings)}" for item in data_limitations])

        if fallback_reason:
            if chinese:
                lines.extend(
                    [
                        "",
                        "> 说明：Gemini 生成失败，因此已使用本地结构化模板生成该 markdown 报告。",
                        f"> 错误信息：{fallback_reason}",
                    ]
                )
            else:
                lines.extend(
                    [
                        "",
                        "> Note: Gemini generation failed, so this markdown report was produced from the local structured schema.",
                        f"> Error: {fallback_reason}",
                    ]
                )

        return "\n".join(lines)

    def generate_summary(self, analysis_results: dict) -> str:
        schema = self.build_report_schema(analysis_results, "")
        return "\n".join(f"- {item}" for item in schema["Executive Summary"])

    def generate_insights(self, analysis_results: dict, user_requirements: str) -> str:
        schema = self.build_report_schema(analysis_results, user_requirements)
        lines = []
        for insight in schema["Key Insights with Evidence"]:
            lines.append(
                f"- {insight['Finding']} | Evidence: {insight['Evidence']} | "
                f"Implication: {insight['Business Implication']} | Confidence: {insight['Confidence Level']}"
            )
        return "\n".join(lines)

    def generate_recommendations(self, analysis_results: dict) -> str:
        schema = self.build_report_schema(analysis_results, "")
        return "\n".join(
            f"- [{action['priority']}] {action['action']} ({action['timeframe']}; owner: {action['suggested_owner']})"
            for action in schema["Recommended Action Plan"]
        )

    def generate_local_report(
        self,
        analysis_results: dict,
        user_requirements: str,
        fallback_reason: str | None = None,
        report_settings: dict | None = None,
    ) -> str:
        report_schema = self.build_report_schema(analysis_results, user_requirements)
        return self.render_schema_markdown(report_schema, fallback_reason, report_settings)

    def generate_ai_report(
        self,
        analysis_results: dict,
        user_requirements: str,
        report_settings: dict | None = None,
    ) -> str:
        settings = self.normalize_report_settings(report_settings)
        compact_results = self.compact_analysis_results(analysis_results)
        report_schema = self.build_report_schema(analysis_results, user_requirements)
        industry = report_schema.get("Industry") or self.industry_type(analysis_results)
        if self.is_chinese(settings):
            report_title = "业务绩效洞察报告"
            sections = [
                "1. 执行摘要",
                "2. KPI 快照",
                "3. 关键洞察与证据",
                "4. 分群深入分析",
                "5. 根因假设",
                "6. 建议行动计划",
                "7. 数据限制",
            ]
            language_rule = (
                "- The final report language is Simplified Chinese. "
                "All headings, table headers, bullets, explanations, confidence labels, and body text must be in Chinese. "
                "Only source data values such as product names, column names, and numeric values may remain unchanged."
            )
            kpi_columns = "指标 | 数值 | 业务解读"
            hypothesis_columns = "假设 | 证据等级 | 支撑证据 | 验证所需数据"
            action_columns = "优先级 | 行动 | 理由 | 负责人 | 时间范围 | 跟踪 KPI"
            confidence_labels = "高置信度, 中等置信度, 假设 / 低置信度"
            empty_requirements = "未指定"
        else:
            report_title = "Business Performance Insight Report"
            sections = [
                "1. Executive Summary",
                "2. KPI Snapshot",
                "3. Key Insights with Evidence",
                "4. Segment Deep Dive",
                "5. Root Cause Hypotheses",
                "6. Recommended Action Plan",
                "7. Data Limitations",
            ]
            language_rule = "- The final report language is English. All headings and body text must be in English."
            kpi_columns = "Metric | Value | Business Interpretation"
            hypothesis_columns = "Hypothesis | Evidence Level | Supporting Evidence | Data Needed for Validation"
            action_columns = "Priority | Action | Rationale | Owner | Timeframe | KPI to Track"
            confidence_labels = "High confidence, Medium confidence, Hypothesis / Low confidence"
            empty_requirements = "Not specified"

        tone_rule = (
            "Use a concise management-facing tone focused on decisions and priorities."
            if settings["tone"] == "Executive Summary"
            else "Use an analyst report tone with clear evidence, caveats, and operational detail."
        )
        length_rule = (
            "Keep the report brief: use short paragraphs and only the most important rows."
            if settings["length"] == "Brief"
            else "Make the report detailed: include richer evidence, practical caveats, and complete action rows."
        )
        industry_rule = {
            "saas": (
                "- This is a SaaS metrics report. Prioritize MRR, ARR, churn, new customers, churned customers, "
                "expansion revenue, support tickets, CAC, plan type, and customer segment. "
                "Do not rewrite expansion_revenue as total sales."
            ),
            "logistics": (
                "- This is a logistics operations report. Prioritize shipments, delay rate, damage rate, delivery time, "
                "shipping cost, region, route, carrier, and warehouse. "
                "Do not say the report is invalid just because sales or profit fields are absent."
            ),
        }.get(
            industry,
            "- Use the available business fields. For retail or sales-style data, prioritize sales, profit, margin, discounts, loss records, and segments.",
        )
        prompt = (
            "Generate a markdown business performance insight report using exactly this title and these sections:\n"
            f"# {report_title}\n"
            + "\n".join(sections)
            + "\n\n"
            f"Report settings:\n"
            f"- Language: {settings['language']}\n"
            f"- Tone: {settings['tone']}\n"
            f"- Length: {settings['length']}\n"
            f"{language_rule}\n"
            f"- {tone_rule}\n"
            f"- {length_rule}\n\n"
            "Rules:\n"
            "- Keep the output in markdown.\n"
            f"{industry_rule}\n"
            f"- KPI Snapshot must be a markdown table with columns: {kpi_columns}.\n"
            f"- Root Cause Hypotheses must be a markdown table with columns: {hypothesis_columns}.\n"
            "- Each hypothesis must include Data Needed for Validation.\n"
            f"- Recommended Action Plan must be a markdown table with columns: {action_columns}.\n"
            "- Do not invent unsupported business facts.\n"
            "- Do not present market competition, inventory clearance, customer behavior, or product lifecycle as confirmed causes unless the dataset contains relevant columns.\n"
            "- Explain what happened, why it matters, what evidence supports it, what the business should do next, and what data limitations exist.\n"
            "- Recommended actions should be practical and linked to the strongest available evidence objects in the structured schema.\n"
            "- Separate data-backed findings from hypotheses.\n"
            "- Each key insight must include Finding, Evidence, Business Implication, and Confidence Level.\n"
            f"- Use exactly these confidence labels in the selected language: {confidence_labels}.\n"
            "- Each recommended action must include priority, action, business rationale, suggested owner, timeframe, and KPI to track.\n"
            "- If a conclusion is inferred rather than directly proven by data, label it as a hypothesis.\n\n"
            f"Structured report schema:\n{json.dumps(report_schema, ensure_ascii=False)}\n\n"
            f"Computed analysis context:\n{json.dumps(compact_results, ensure_ascii=False)}\n\n"
            f"User requirements: {user_requirements or empty_requirements}"
        )
        response = self.llm.invoke(prompt)
        return getattr(response, "content", response)

    def repair_report_markdown(
        self,
        content: str,
        validation_errors: list[str],
        report_schema: dict,
        report_settings: dict | None = None,
    ) -> str:
        settings = self.normalize_report_settings(report_settings)
        if self.is_chinese(settings):
            title = "业务绩效洞察报告"
            sections = [
                "1. 执行摘要",
                "2. KPI 快照",
                "3. 关键洞察与证据",
                "4. 分群深入分析",
                "5. 根因假设",
                "6. 建议行动计划",
                "7. 数据限制",
            ]
            kpi_columns = "指标 | 数值 | 业务解读"
            hypothesis_columns = "假设 | 证据等级 | 支撑证据 | 验证所需数据"
            action_columns = "优先级 | 行动 | 理由 | 负责人 | 时间范围 | 跟踪 KPI"
            language_rule = "Keep the repaired report in Simplified Chinese."
        else:
            title = "Business Performance Insight Report"
            sections = [
                "1. Executive Summary",
                "2. KPI Snapshot",
                "3. Key Insights with Evidence",
                "4. Segment Deep Dive",
                "5. Root Cause Hypotheses",
                "6. Recommended Action Plan",
                "7. Data Limitations",
            ]
            kpi_columns = "Metric | Value | Business Interpretation"
            hypothesis_columns = "Hypothesis | Evidence Level | Supporting Evidence | Data Needed for Validation"
            action_columns = "Priority | Action | Rationale | Owner | Timeframe | KPI to Track"
            language_rule = "Keep the repaired report in English."

        prompt = (
            "Repair this business report so it matches the required markdown format and structured schema.\n"
            "Keep the existing business meaning when it is supported by the schema.\n"
            "Remove unsupported additions that are not present in the schema.\n"
            "Do not add new KPIs, hypotheses, actions, causes, or recommendations.\n"
            "Return only the corrected markdown report, with no commentary.\n\n"
            f"{language_rule}\n"
            f"Use exactly this title: # {title}\n"
            "Keep exactly these numbered sections:\n"
            + "\n".join(sections)
            + "\n\n"
            "Table formatting rules:\n"
            f"- KPI Snapshot must be a markdown table with columns: {kpi_columns}.\n"
            f"- Root Cause Hypotheses must be a markdown table with columns: {hypothesis_columns}.\n"
            f"- Recommended Action Plan must be a markdown table with columns: {action_columns}.\n"
            "- Markdown table separator rows must use short cells such as | --- | --- | --- |.\n"
            "- Do not create long dashed separator lines.\n"
            "- Do not place section headings inside table rows.\n\n"
            "Schema fidelity rules:\n"
            "- Use only the provided structured report schema as the source of truth.\n"
            "- Do not exceed the number of KPI, hypothesis, or action rows in the schema.\n"
            "- Do not turn hypotheses into confirmed root causes.\n"
            "- Remove deterministic causal claims that are not directly supported by the schema.\n\n"
            f"Validation errors to fix:\n{json.dumps(validation_errors, ensure_ascii=False)}\n\n"
            f"Structured report schema:\n{json.dumps(report_schema, ensure_ascii=False)}\n\n"
            f"Broken markdown report:\n{content}"
        )
        response = self.llm.invoke(prompt)
        return getattr(response, "content", response)

    @staticmethod
    def classify_provider_status(error: Exception | str) -> str:
        message = str(error).casefold()
        if "429" in message or "rate limit" in message or "rate_limit" in message or "quota" in message:
            return "rate_limited"
        if any(token in message for token in ("401", "403", "api key", "credential", "authentication", "configuration")):
            return "configuration_error"
        return "unavailable"

    @staticmethod
    def contains_kpi_fidelity_error(errors: list[str]) -> bool:
        return any("critical kpi" in error.casefold() for error in errors)

    def run(
        self,
        analysis_results: dict,
        user_requirements: str,
        report_settings: dict | None = None,
    ) -> dict:
        report_settings = self.normalize_report_settings(report_settings)
        source = "local"
        fallback_reason = None
        validation_errors = []
        repair_attempted = False
        repair_errors = []
        provider_status = "available" if self.has_api_key else "configuration_error"
        report_validation_status = "not_run"
        kpi_fidelity_status = "not_run"
        fallback_used = not self.has_api_key
        validation_ran = False
        report_schema = self.build_report_schema(analysis_results, user_requirements)

        if self.has_api_key:
            try:
                report_content = self.generate_ai_report(analysis_results, user_requirements, report_settings)
                validation_errors = self.validate_generated_report(
                    report_content,
                    report_schema,
                    report_settings,
                )
                validation_ran = True
                if validation_errors:
                    repair_attempted = True
                    repaired_content = self.repair_report_markdown(
                        report_content,
                        validation_errors,
                        report_schema,
                        report_settings,
                    )
                    repair_errors = self.validate_generated_report(
                        repaired_content,
                        report_schema,
                        report_settings,
                    )
                    if repair_errors:
                        report_validation_status = "failed"
                        kpi_fidelity_status = (
                            "failed" if self.contains_kpi_fidelity_error(repair_errors) else "passed"
                        )
                        fallback_used = True
                        fallback_reason = (
                            "Gemini output failed markdown validation after repair: "
                            + "; ".join(repair_errors)
                        )
                        report_content = self.generate_local_report(
                            analysis_results,
                            user_requirements,
                            fallback_reason,
                            report_settings,
                        )
                        source = "local"
                    else:
                        report_content = repaired_content
                        source = "gemini_repaired"
                        report_validation_status = "passed"
                        kpi_fidelity_status = "passed"
                else:
                    source = "gemini"
                    report_validation_status = "passed"
                    kpi_fidelity_status = "passed"
            except Exception as error:
                provider_status = self.classify_provider_status(error)
                fallback_reason = str(error)
                fallback_used = True
                if validation_ran:
                    report_validation_status = "failed"
                    kpi_fidelity_status = (
                        "failed" if self.contains_kpi_fidelity_error(validation_errors) else "passed"
                    )
                report_content = self.generate_local_report(
                    analysis_results,
                    user_requirements,
                    fallback_reason,
                    report_settings,
                )
        else:
            report_content = self.generate_local_report(
                analysis_results,
                user_requirements,
                report_settings=report_settings,
            )

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "content": report_content,
            "source": source,
            "provider_status": provider_status,
            "report_validation_status": report_validation_status,
            "kpi_fidelity_status": kpi_fidelity_status,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "validation_errors": validation_errors,
            "repair_attempted": repair_attempted,
            "repair_errors": repair_errors,
            "report_settings": report_settings,
        }
