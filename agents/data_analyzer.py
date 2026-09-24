from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from utils.file_handler import FileHandler


class DataAnalyzerAgent:
    ROLE_KEYWORDS = {
        "sales": ["sales", "sale", "revenue", "amount", "gmv", "turnover", "销售", "收入", "金额"],
        "profit": ["profit", "margin", "earnings", "income", "利润", "毛利"],
        "discount": ["discount", "rebate", "折扣", "优惠"],
        "quantity": ["quantity", "qty", "units", "volume", "数量", "销量"],
        "region": ["region", "country", "state", "city", "area", "market", "地区", "区域", "国家", "城市"],
        "category": ["category", "subcategory", "type", "class", "品类", "类别", "分类"],
        "segment": ["segment", "group", "tier", "客群", "细分", "分层"],
        "product": ["product", "sku", "item", "goods", "category", "subcategory", "产品", "商品", "品类"],
        "customer": ["customer", "client", "account", "segment", "buyer", "用户", "客户", "客群"],
        "date": ["date", "time", "month", "year", "日期", "时间", "月份", "年度"],
        "order": ["order", "invoice", "transaction", "订单", "交易", "发票"],
    }

    def __init__(self):
        self.df: pd.DataFrame | None = None

    def load_data(self, file_path: str):
        self.df = FileHandler.read_file(file_path)

    @staticmethod
    def clean_value(value: Any) -> Any:
        if pd.isna(value):
            return None
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return round(float(value), 4)
        if isinstance(value, (pd.Timestamp,)):
            return value.isoformat()
        return value

    @classmethod
    def clean_record(cls, record: dict) -> dict:
        return {key: cls.clean_value(value) for key, value in record.items()}

    @staticmethod
    def find_first(
        columns: list[str],
        keywords: list[str],
        excluded_keywords: list[str] | None = None,
    ) -> str | None:
        excluded_keywords = [keyword.lower() for keyword in (excluded_keywords or [])]
        normalized = [(column, column.lower().replace("_", " ").replace("-", " ")) for column in columns]
        for keyword in keywords:
            keyword = keyword.lower()
            for original, lowered in normalized:
                if any(excluded in lowered for excluded in excluded_keywords):
                    continue
                if keyword in lowered:
                    return original
        return None

    @staticmethod
    def find_best(columns: list[str], keywords: list[str], prefer: list[str] | None = None) -> str | None:
        prefer = prefer or []
        best_column = None
        best_score = -1
        for column in columns:
            lowered = column.lower().replace("_", " ").replace("-", " ")
            score = 0
            for keyword in keywords:
                if keyword.lower() in lowered:
                    score += 10
            for keyword in prefer:
                if keyword.lower() in lowered:
                    score += 5
            if "id" in lowered and not any(keyword.lower() in lowered for keyword in prefer):
                score -= 3
            if score > best_score:
                best_column = column
                best_score = score
        return best_column if best_score > 0 else None

    @staticmethod
    def find_order_identifier(columns: list[str]) -> str | None:
        normalized = [
            (column, column.lower().replace("-", "_").replace(" ", "_"))
            for column in columns
        ]
        preferred_names = [
            "order_id",
            "order_number",
            "order_no",
            "shipment_id",
            "invoice_id",
            "transaction_id",
        ]
        for preferred in preferred_names:
            for original, lowered in normalized:
                if lowered == preferred:
                    return original
        return None

    def infer_schema(self) -> dict:
        assert self.df is not None
        df = self.df
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        date_cols = [
            column
            for column in df.columns
            if pd.api.types.is_datetime64_any_dtype(df[column])
        ]

        for column in df.columns:
            if column in date_cols:
                continue
            if any(keyword in column.lower() for keyword in self.ROLE_KEYWORDS["date"]):
                parsed = pd.to_datetime(df[column], errors="coerce")
                if parsed.notna().mean() >= 0.75:
                    date_cols.append(column)

        categorical_cols = [
            column
            for column in df.columns
            if column not in numeric_cols and column not in date_cols
        ]
        text_cols = [
            column
            for column in categorical_cols
            if df[column].astype(str).str.len().median() > 40
        ]

        return {
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "columns": df.columns.tolist(),
            "dtypes": {column: str(dtype) for column, dtype in df.dtypes.items()},
            "numeric_columns": numeric_cols,
            "date_columns": date_cols,
            "categorical_columns": categorical_cols,
            "text_columns": text_cols,
        }

    def infer_field_roles(self, schema: dict) -> dict:
        columns = schema["columns"]
        numeric_cols = schema["numeric_columns"]
        date_cols = schema["date_columns"]
        categorical_cols = schema["categorical_columns"]

        roles = {
            "sales": self.find_first(
                numeric_cols,
                self.ROLE_KEYWORDS["sales"],
                excluded_keywords=["expansion"],
            ),
            "profit": self.find_first(numeric_cols, self.ROLE_KEYWORDS["profit"]),
            "discount": self.find_first(numeric_cols, self.ROLE_KEYWORDS["discount"]),
            "quantity": self.find_first(numeric_cols, self.ROLE_KEYWORDS["quantity"]),
            "region": self.find_first(categorical_cols, self.ROLE_KEYWORDS["region"]),
            "category": self.find_first(categorical_cols, self.ROLE_KEYWORDS["category"]),
            "segment": self.find_first(categorical_cols, self.ROLE_KEYWORDS["segment"]),
            "product": self.find_best(categorical_cols, self.ROLE_KEYWORDS["product"], prefer=["name"]),
            "customer": self.find_best(
                [column for column in categorical_cols if "segment" not in column.lower()]
                or categorical_cols,
                self.ROLE_KEYWORDS["customer"],
                prefer=["name"],
            ),
            "date": self.find_first(date_cols or columns, self.ROLE_KEYWORDS["date"]),
            "order": self.find_order_identifier(columns),
        }
        return roles

    def build_overview(self) -> dict:
        assert self.df is not None
        df = self.df
        missing = df.isna().sum()
        missing_ratio = (missing / len(df) * 100).replace([np.inf, -np.inf], 0)
        return {
            "row_count": int(len(df)),
            "column_count": int(len(df.columns)),
            "duplicate_rows": int(df.duplicated().sum()),
            "missing_values": {column: int(value) for column, value in missing.items() if int(value) > 0},
            "missing_ratio_percent": {
                column: round(float(value), 2)
                for column, value in missing_ratio.items()
                if float(value) > 0
            },
        }

    def build_numeric_analysis(self, numeric_cols: list[str]) -> dict:
        assert self.df is not None
        df = self.df
        analysis = {}
        for column in numeric_cols:
            series = df[column].dropna()
            if series.empty:
                continue
            unique_values = set(series.unique().tolist())
            is_binary_indicator = (
                pd.api.types.is_bool_dtype(series)
                or unique_values.issubset({0, 1})
                or column.lower().endswith("_flag")
            )
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            outliers = (
                series.iloc[0:0]
                if is_binary_indicator
                else series[(series < q1 - 1.5 * iqr) | (series > q3 + 1.5 * iqr)]
            )
            analysis[column] = {
                "sum": round(float(series.sum()), 4),
                "mean": round(float(series.mean()), 4),
                "median": round(float(series.median()), 4),
                "min": round(float(series.min()), 4),
                "max": round(float(series.max()), 4),
                "std": round(float(series.std()), 4) if len(series) > 1 else 0,
                "outlier_count": int(len(outliers)),
            }
        return analysis

    def build_kpis(self, roles: dict) -> dict:
        assert self.df is not None
        df = self.df
        kpis = {"record_count": int(len(df))}

        sales_col = roles.get("sales")
        profit_col = roles.get("profit")
        quantity_col = roles.get("quantity")
        discount_col = roles.get("discount")
        order_col = roles.get("order")

        if sales_col:
            total_sales = float(df[sales_col].sum())
            kpis["total_sales"] = round(total_sales, 2)
            kpis["average_sales"] = round(float(df[sales_col].mean()), 2)
        if profit_col:
            total_profit = float(df[profit_col].sum())
            kpis["total_profit"] = round(total_profit, 2)
        if sales_col and profit_col and df[sales_col].sum() != 0:
            kpis["profit_margin_percent"] = round(float(df[profit_col].sum() / df[sales_col].sum() * 100), 2)
        if quantity_col:
            kpis["total_quantity"] = round(float(df[quantity_col].sum()), 2)
        if discount_col:
            kpis["average_discount_percent"] = round(float(df[discount_col].mean() * 100), 2)
        if order_col:
            kpis["order_count"] = int(df[order_col].nunique())
        if sales_col and order_col and df[order_col].nunique() > 0:
            kpis["average_order_value"] = round(float(df[sales_col].sum() / df[order_col].nunique()), 2)

        return kpis

    def build_category_analysis(self, roles: dict, schema: dict) -> dict:
        assert self.df is not None
        df = self.df
        sales_col = roles.get("sales")
        profit_col = roles.get("profit")
        dimensions = [
            column
            for column in [
                roles.get("region"),
                roles.get("category"),
                roles.get("segment"),
                roles.get("product"),
                roles.get("customer"),
            ]
            if column
        ]
        if not dimensions:
            dimensions = schema["categorical_columns"][:3]

        results = {}
        agg_map = {}
        if sales_col:
            agg_map[sales_col] = "sum"
        if profit_col:
            agg_map[profit_col] = "sum"

        for dimension in dimensions:
            value_counts = df[dimension].astype(str).value_counts().head(10)
            item = {
                "top_values": [
                    {"value": str(index), "count": int(count)}
                    for index, count in value_counts.items()
                ]
            }
            if agg_map:
                grouped = df.groupby(dimension, dropna=False).agg(agg_map).reset_index()
                sort_col = sales_col or profit_col
                grouped = grouped.sort_values(sort_col, ascending=False).head(10)
                item["top_by_metric"] = [
                    self.clean_record(record)
                    for record in grouped.to_dict(orient="records")
                ]
            results[dimension] = item
        return results

    def build_time_trends(self, roles: dict) -> dict:
        assert self.df is not None
        date_col = roles.get("date")
        if not date_col:
            return {}

        df = self.df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col])
        if df.empty:
            return {}

        metric_cols = [
            column
            for column in [roles.get("sales"), roles.get("profit"), roles.get("quantity")]
            if column
        ]
        df["_period"] = df[date_col].dt.to_period("M").astype(str)
        agg_map = {column: "sum" for column in metric_cols}
        agg_map["_record_count"] = "sum"
        df["_record_count"] = 1
        trend = df.groupby("_period").agg(agg_map).reset_index().tail(24)
        return {
            "date_column": date_col,
            "period": "month",
            "rows": [self.clean_record(record) for record in trend.to_dict(orient="records")],
        }

    def build_top_bottom(self, roles: dict) -> dict:
        assert self.df is not None
        df = self.df
        results = {}
        dimensions = [
            column
            for column in [
                roles.get("product"),
                roles.get("category"),
                roles.get("segment"),
                roles.get("region"),
                roles.get("customer"),
            ]
            if column
        ]

        for metric in [roles.get("sales"), roles.get("profit")]:
            if not metric:
                continue
            metric_results = {}
            for dimension in dimensions:
                grouped = df.groupby(dimension, dropna=False)[metric].sum().reset_index()
                top = grouped.sort_values(metric, ascending=False).head(10)
                bottom = grouped.sort_values(metric, ascending=True).head(10)
                metric_results[dimension] = {
                    "top": [self.clean_record(record) for record in top.to_dict(orient="records")],
                    "bottom": [self.clean_record(record) for record in bottom.to_dict(orient="records")],
                }
            results[metric] = metric_results
        return results

    def build_risks(self, roles: dict, overview: dict, numeric_analysis: dict) -> dict:
        assert self.df is not None
        df = self.df
        risks = {
            "high_missing_columns": [
                {"column": column, "missing_percent": percent}
                for column, percent in overview["missing_ratio_percent"].items()
                if percent >= 20
            ],
            "numeric_outliers": [
                {"column": column, "outlier_count": details["outlier_count"]}
                for column, details in numeric_analysis.items()
                if details["outlier_count"] > 0
            ],
        }

        profit_col = roles.get("profit")
        discount_col = roles.get("discount")
        sales_col = roles.get("sales")

        if profit_col:
            loss_df = df[df[profit_col] < 0]
            risks["loss_records"] = {
                "count": int(len(loss_df)),
                "total_loss": round(float(loss_df[profit_col].sum()), 2) if not loss_df.empty else 0,
            }

        if discount_col and profit_col:
            high_discount_threshold = df[discount_col].quantile(0.9)
            high_discount_loss = df[(df[discount_col] >= high_discount_threshold) & (df[profit_col] < 0)]
            risks["high_discount_loss_records"] = {
                "count": int(len(high_discount_loss)),
                "discount_threshold": round(float(high_discount_threshold), 4),
            }

        if sales_col:
            series = df[sales_col].dropna()
            if not series.empty:
                risks["extreme_sales_threshold"] = round(float(series.quantile(0.99)), 2)

        return risks

    @staticmethod
    def detect_industry(schema: dict) -> str:
        columns = {column.lower() for column in schema.get("columns", [])}
        if {"mrr", "arr", "churn_rate"}.issubset(columns):
            return "saas"
        if {"shipping_cost", "delivery_time_days", "delay_flag"}.issubset(columns):
            return "logistics"
        return "generic"

    def build_saas_analysis(self) -> dict:
        assert self.df is not None
        df = self.df.copy()
        month_col = "month" if "month" in df.columns else None
        plan_col = "plan_type" if "plan_type" in df.columns else None
        segment_col = "customer_segment" if "customer_segment" in df.columns else None
        latest_df = df
        latest_period = None
        if month_col:
            parsed_periods = pd.to_datetime(df[month_col], errors="coerce")
            if parsed_periods.notna().any():
                latest_period = parsed_periods.max()
                latest_df = df.loc[parsed_periods.eq(latest_period)].copy()

        kpis = {
            "snapshot_period": latest_period.strftime("%Y-%m") if latest_period is not None else None,
            "current_mrr": round(float(latest_df["mrr"].sum()), 2) if "mrr" in latest_df.columns else None,
            "current_arr": round(float(latest_df["arr"].sum()), 2) if "arr" in latest_df.columns else None,
            "total_new_customers": int(df["new_customers"].sum()) if "new_customers" in df.columns else None,
            "total_churned_customers": int(df["churned_customers"].sum()) if "churned_customers" in df.columns else None,
            "average_churn_rate_percent": round(float(df["churn_rate"].mean() * 100), 2) if "churn_rate" in df.columns else None,
            "total_expansion_revenue": round(float(df["expansion_revenue"].sum()), 2) if "expansion_revenue" in df.columns else None,
            "total_support_tickets": int(df["support_tickets"].sum()) if "support_tickets" in df.columns else None,
            "average_cac": round(float(df["cac"].mean()), 2) if "cac" in df.columns else None,
        }
        if month_col and "mrr" in df.columns:
            monthly_mrr = df.groupby(month_col)["mrr"].sum().sort_index()
            if len(monthly_mrr) >= 2 and monthly_mrr.iloc[0] != 0:
                kpis["mrr_growth_percent"] = round(float((monthly_mrr.iloc[-1] - monthly_mrr.iloc[0]) / monthly_mrr.iloc[0] * 100), 2)

        def segment_summary(column: str) -> dict:
            flow_agg = {
                "new_customers": "sum",
                "churned_customers": "sum",
                "churn_rate": "mean",
                "expansion_revenue": "sum",
                "support_tickets": "sum",
                "cac": "mean",
            }
            available_flow_agg = {key: value for key, value in flow_agg.items() if key in df.columns}
            grouped = (
                df.groupby(column, dropna=False).agg(available_flow_agg).reset_index()
                if available_flow_agg
                else df[[column]].drop_duplicates().reset_index(drop=True)
            )
            snapshot_agg = {
                key: "sum"
                for key in ["mrr", "arr"]
                if key in latest_df.columns
            }
            if snapshot_agg:
                snapshot_grouped = latest_df.groupby(column, dropna=False).agg(snapshot_agg).reset_index()
                grouped = grouped.merge(snapshot_grouped, on=column, how="left")
            rows = [self.clean_record(record) for record in grouped.to_dict(orient="records")]
            best = grouped.sort_values("mrr", ascending=False).iloc[0].to_dict() if "mrr" in grouped else {}
            risk = grouped.sort_values("churn_rate", ascending=False).iloc[0].to_dict() if "churn_rate" in grouped else {}
            return {
                "dimension": column,
                "snapshot_period": latest_period.strftime("%Y-%m") if latest_period is not None else None,
                "rows": rows,
                "best_by_mrr": self.clean_record(best) if best else {},
                "risk_by_churn": self.clean_record(risk) if risk else {},
            }

        segments = {}
        for column in [plan_col, segment_col]:
            if column:
                segments[column] = segment_summary(column)

        return {"industry": "saas", "kpis": kpis, "segments": segments}

    def build_logistics_analysis(self) -> dict:
        assert self.df is not None
        df = self.df.copy()
        total_shipments = len(df)
        total_order_value = float(df["order_value"].sum()) if "order_value" in df.columns else None
        total_shipping_cost = float(df["shipping_cost"].sum()) if "shipping_cost" in df.columns else None
        delay_count = int(df["delay_flag"].sum()) if "delay_flag" in df.columns else None
        damage_count = int(df["damage_flag"].sum()) if "damage_flag" in df.columns else None
        kpis = {
            "total_shipments": total_shipments,
            "total_order_value": round(total_order_value, 2) if total_order_value is not None else None,
            "total_shipping_cost": round(total_shipping_cost, 2) if total_shipping_cost is not None else None,
            "shipping_cost_ratio": round(total_shipping_cost / total_order_value, 4) if total_order_value else None,
            "average_delivery_time_days": round(float(df["delivery_time_days"].mean()), 2) if "delivery_time_days" in df.columns else None,
            "delayed_shipments": delay_count,
            "delay_rate": round(delay_count / total_shipments, 4) if delay_count is not None and total_shipments else None,
            "damage_shipments": damage_count,
            "damage_rate": round(damage_count / total_shipments, 4) if damage_count is not None and total_shipments else None,
        }

        def segment_summary(column: str) -> dict:
            grouped = df.groupby(column, dropna=False).agg(
                shipment_count=("delay_flag", "count"),
                delay_count=("delay_flag", "sum"),
                damage_count=("damage_flag", "sum"),
                average_delivery_time_days=("delivery_time_days", "mean"),
                total_shipping_cost=("shipping_cost", "sum"),
                average_shipping_cost=("shipping_cost", "mean"),
            ).reset_index()
            grouped["delay_rate"] = grouped["delay_count"] / grouped["shipment_count"]
            grouped["damage_rate"] = grouped["damage_count"] / grouped["shipment_count"]
            best = grouped.sort_values(["delay_rate", "average_delivery_time_days"], ascending=[True, True]).iloc[0].to_dict()
            risk = grouped.sort_values(["delay_rate", "average_delivery_time_days", "total_shipping_cost"], ascending=[False, False, False]).iloc[0].to_dict()
            return {
                "dimension": column,
                "rows": [self.clean_record(record) for record in grouped.to_dict(orient="records")],
                "best_by_delivery": self.clean_record(best),
                "risk_by_delay": self.clean_record(risk),
            }

        segments = {}
        for column in ["region", "carrier", "route", "warehouse"]:
            if column in df.columns:
                segments[column] = segment_summary(column)

        return {"industry": "logistics", "kpis": kpis, "segments": segments}

    def build_industry_analysis(self, schema: dict) -> dict:
        industry = self.detect_industry(schema)
        if industry == "saas":
            return self.build_saas_analysis()
        if industry == "logistics":
            return self.build_logistics_analysis()
        return {"industry": "generic", "kpis": {}, "segments": {}}

    def build_summary_text(self, result: str, roles: dict, kpis: dict, risks: dict) -> str:
        lines = [result]
        detected_roles = {role: column for role, column in roles.items() if column}
        if detected_roles:
            lines.append(f"识别到的业务字段: {detected_roles}")
        if kpis:
            lines.append(f"核心 KPI: {kpis}")
        if risks:
            lines.append(f"风险提示: {risks}")
        return "\n\n".join(lines)

    def get_task_result(self, analysis_task: str, numeric_analysis: dict, schema: dict) -> str:
        if "相关" in analysis_task:
            numeric_cols = schema["numeric_columns"]
            if len(numeric_cols) < 2:
                return "没有足够的数值列用于相关性分析"
            corr = self.df[numeric_cols].corr().round(4).to_string()
            return f"相关性分析:\n{corr}"
        if "异常" in analysis_task:
            outliers = {
                column: details["outlier_count"]
                for column, details in numeric_analysis.items()
                if details["outlier_count"] > 0
            }
            return f"异常值检测: {outliers or '未发现明显数值异常'}"
        if "趋势" in analysis_task or "分布" in analysis_task:
            return "已完成数据分布、字段结构和可用时间趋势分析"
        return "已完成基础统计、字段识别和业务指标分析"

    def run(self, file_path: str, analysis_task: str) -> dict:
        self.load_data(file_path)
        assert self.df is not None

        schema = self.infer_schema()
        roles = self.infer_field_roles(schema)
        overview = self.build_overview()
        numeric_analysis = self.build_numeric_analysis(schema["numeric_columns"])
        kpis = self.build_kpis(roles)
        category_analysis = self.build_category_analysis(roles, schema)
        time_trends = self.build_time_trends(roles)
        top_bottom = self.build_top_bottom(roles)
        risks = self.build_risks(roles, overview, numeric_analysis)
        industry_analysis = self.build_industry_analysis(schema)
        result = self.get_task_result(analysis_task, numeric_analysis, schema)

        return {
            "status": "success",
            "analysis_task": analysis_task,
            "result": result,
            "summary_text": self.build_summary_text(result, roles, kpis, risks),
            "schema": schema,
            "field_roles": roles,
            "overview": overview,
            "kpis": kpis,
            "numeric_analysis": numeric_analysis,
            "category_analysis": category_analysis,
            "time_trends": time_trends,
            "top_bottom": top_bottom,
            "risks": risks,
            "industry_analysis": industry_analysis,
            "sample_rows": [
                self.clean_record(record)
                for record in self.df.head(5).to_dict(orient="records")
            ],
        }
