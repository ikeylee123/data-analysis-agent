from __future__ import annotations

from typing import Any
import re

import pandas as pd

from utils.i18n import display_label, t


DOMAIN_ROLE_SPECS = {
    "retail": [
        ("Sales", "sales"), ("Profit", "profit"), ("Discount", "discount"),
        ("Quantity", "quantity"), ("Region", "region"), ("Category", "category"),
        ("Customer Segment", "segment"), ("Customer", "customer"),
        ("Product", "product"), ("Order ID", "order"), ("Date", "date"),
    ],
    "saas": [
        ("Period / Date", "month"), ("Plan", "plan_type"),
        ("Customer Segment", "customer_segment"), ("MRR", "mrr"), ("ARR", "arr"),
        ("Churn Rate", "churn_rate"), ("New Customers", "new_customers"),
        ("Churned Customers", "churned_customers"),
        ("Expansion Revenue", "expansion_revenue"),
        ("Support Tickets", "support_tickets"), ("CAC", "cac"),
    ],
    "logistics": [
        ("Date", "date"), ("Region", "region"), ("Route", "route"),
        ("Carrier", "carrier"), ("Warehouse", "warehouse"),
        ("Order Value", "order_value"), ("Shipping Cost", "shipping_cost"),
        ("Delivery Time", "delivery_time_days"), ("Delay Flag", "delay_flag"),
        ("Damage Flag", "damage_flag"),
    ],
}

LABELS = {
    "plan_type": "Plan", "customer_segment": "Customer Segment", "mrr": "Current MRR",
    "current_mrr": "Current MRR", "current_arr": "Current ARR",
    "arr": "Current ARR", "churn_rate": "Churn Rate", "new_customers": "New Customers",
    "churned_customers": "Churned Customers", "expansion_revenue": "Expansion Revenue",
    "support_tickets": "Support Tickets", "cac": "CAC", "shipment_count": "Shipments",
    "delay_count": "Delayed Shipments", "damage_count": "Damaged Shipments",
    "delay_rate": "Delay Rate", "damage_rate": "Damage Rate",
    "average_delivery_time_days": "Avg Delivery Time",
    "average_shipping_cost": "Avg Shipping Cost", "carrier": "Carrier", "region": "Region",
    "sales": "Sales", "profit": "Profit", "discount": "Discount", "quantity": "Quantity",
}

PERCENT_FIELDS = {"churn_rate", "delay_rate", "damage_rate", "shipping_cost_ratio"}
CURRENCY_FIELDS = {
    "sales", "profit", "mrr", "arr", "expansion_revenue", "cac", "shipping_cost",
    "average_shipping_cost", "order_value", "total_shipping_cost",
}
COUNT_FIELDS = {
    "new_customers", "churned_customers", "support_tickets", "shipment_count",
    "delay_count", "damage_count", "total_shipments", "record_count",
}
MEAN_TIME_METRICS = {
    "delivery_time_days", "average_delivery_time_days", "churn_rate", "delay_rate",
    "damage_rate", "discount", "cac",
}




def sanitize_technical_reason(value: str) -> str:
    text = str(value)
    text = re.sub(r"[A-Za-z]:\\[^\n\r]+", "<local-path>", text)
    text = re.sub(r"(?i)authorization\s*:\s*[^,}\n\r]+", "Authorization: <redacted>", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+\-/=]+", "Bearer <redacted>", text)
    text = re.sub(r"(?i)(api[_ -]?key|token|secret)\s*[=:]\s*[^,}\s]+", r"\1=<redacted>", text)
    text = re.sub(r"(?i)https?://[^\s/:]+:[^\s/@]+@", "https://<redacted>@", text)
    return text



def report_content_for_display(content: str, hide_fallback_error: bool = False) -> str:
    sanitized = sanitize_technical_reason(content)
    if not hide_fallback_error:
        return sanitized
    return "\n".join(
        line for line in sanitized.splitlines()
        if not line.lstrip().startswith(("> Error:", "> 错误信息："))
    )

def reliability_status_items(report: dict, language: str = "en") -> list[tuple[str, str]]:
    source_keys = {"gemini": "reliability.gemini", "gemini_repaired": "reliability.repaired", "local": "reliability.local"}
    provider_keys = {"available": "reliability.available", "rate_limited": "reliability.rate_limited", "unavailable": "reliability.unavailable", "configuration_error": "reliability.configuration_error", "not_applicable": "reliability.not_applicable"}
    stage_keys = {"passed": "reliability.passed", "failed": "reliability.failed", "not_run": "reliability.not_run"}
    source = source_keys.get(report.get("source"), "reliability.not_applicable")
    provider = provider_keys.get(report.get("provider_status"), "reliability.not_applicable")
    validation = stage_keys.get(report.get("report_validation_status"), "reliability.not_run")
    fidelity = stage_keys.get(report.get("kpi_fidelity_status"), "reliability.not_run")
    return [
        (t("reliability.source", language), t(source, language)),
        (t("reliability.provider", language), t(provider, language)),
        (t("reliability.validation", language), t(validation, language)),
        (t("reliability.kpi", language), t(fidelity, language)),
        (t("reliability.fallback", language), t("reliability.activated" if report.get("fallback_used") else "reliability.not_used", language)),
    ]

def plotly_key(*parts: str) -> str:
    normalized = []
    for part in parts:
        value = "".join(character.lower() if character.isalnum() else "_" for character in str(part))
        normalized.append("_".join(value.split("_")))
    return "_".join(normalized)

def normalized_domain(analysis_result: dict | None, detected_domain: str | None = None) -> str:
    industry = (analysis_result or {}).get("industry_analysis", {}).get("industry")
    domain = industry or detected_domain or "generic"
    return "retail" if domain == "generic" else domain


def primary_kpi_cards(analysis_result: dict, language: str = "en") -> list[dict[str, Any]]:
    domain = normalized_domain(analysis_result)
    generic = analysis_result.get("kpis", {})
    industry = analysis_result.get("industry_analysis", {}).get("kpis", {})
    risks = analysis_result.get("risks", {})
    if domain == "saas":
        return [
            {"label": display_label("current_mrr", language), "value": industry.get("current_mrr"), "format": "currency"},
            {"label": display_label("current_arr", language), "value": industry.get("current_arr"), "format": "currency"},
            {"label": display_label("churn_rate", language), "value": industry.get("average_churn_rate_percent"), "format": "percent_number"},
            {"label": display_label("mrr_growth_percent", language), "value": industry.get("mrr_growth_percent"), "format": "percent_number"},
            {"label": display_label("total_expansion_revenue", language), "value": industry.get("total_expansion_revenue"), "format": "currency"},
        ]
    if domain == "logistics":
        return [
            {"label": display_label("total_shipments", language), "value": industry.get("total_shipments"), "format": "count"},
            {"label": display_label("delay_rate", language), "value": industry.get("delay_rate"), "format": "ratio_percent"},
            {"label": display_label("damage_rate", language), "value": industry.get("damage_rate"), "format": "ratio_percent"},
            {"label": display_label("average_delivery_time_days", language), "value": industry.get("average_delivery_time_days"), "format": "days"},
            {"label": display_label("shipping_cost_ratio", language), "value": industry.get("shipping_cost_ratio"), "format": "ratio_percent"},
        ]
    return [
        {"label": display_label("total_sales", language), "value": generic.get("total_sales"), "format": "currency"},
        {"label": display_label("total_profit", language), "value": generic.get("total_profit"), "format": "currency"},
        {"label": display_label("profit_margin_percent", language), "value": generic.get("profit_margin_percent"), "format": "percent_number"},
        {"label": display_label("loss_records", language), "value": risks.get("loss_records", {}).get("count", 0), "format": "count"},
        {"label": display_label("average_discount_percent", language), "value": generic.get("average_discount_percent"), "format": "percent_number"},
    ]


def format_kpi_card_value(value: Any, value_format: str) -> str:
    if value is None:
        return "N/A"
    if value_format == "currency": return f"{float(value):,.2f}"
    if value_format == "count": return f"{int(value):,}"
    if value_format == "ratio_percent": return f"{float(value):.2%}"
    if value_format == "percent_number": return f"{float(value):.2f}%"
    if value_format == "days": return f"{float(value):.2f} days"
    return str(value)


def humanize_label(name: str, language: str = "en") -> str:
    if language == "en":
        return LABELS.get(name, display_label(name, language))
    return display_label(name, language)


def format_business_value(field: str, value: Any) -> str:
    if value is None: return "N/A"
    if field in PERCENT_FIELDS: return f"{float(value):.2%}"
    if field in CURRENCY_FIELDS: return f"{float(value):,.2f}"
    if field in COUNT_FIELDS: return f"{int(value):,}"
    if "delivery_time" in field: return f"{float(value):.2f} days"
    if isinstance(value, float): return f"{value:,.2f}"
    return str(value)


def format_segment_table(rows: list[dict], columns: list[str], language: str = "en") -> pd.DataFrame:
    formatted = []
    for row in rows:
        formatted.append({humanize_label(c, language): format_business_value(c, row.get(c)) for c in columns})
    return pd.DataFrame(formatted)



def humanize_report_markdown_labels(content: str) -> str:
    lines = []
    for line in content.splitlines():
        if line.lstrip().startswith("|"):
            cells = line.split("|")
            if len(cells) > 2:
                metric = cells[1].strip()
                if metric in LABELS or "_" in metric:
                    cells[1] = f" {humanize_label(metric)} "
                    line = "|".join(cells)
        lines.append(line)
    return "\n".join(lines)

def relevant_field_mapping(domain: str, columns: list[str], field_roles: dict[str, str | None], language: str = "en") -> tuple[list[dict[str, str]], list[str]]:
    domain = "retail" if domain == "generic" else domain
    specs = DOMAIN_ROLE_SPECS.get(domain, DOMAIN_ROLE_SPECS["retail"])
    column_lookup = {column.lower(): column for column in columns}
    rows, mapped_columns = [], set()
    for label, role_or_column in specs:
        mapped = field_roles.get(role_or_column) if domain == "retail" else column_lookup.get(role_or_column.lower())
        rows.append({t("mapping.role", language): display_label(role_or_column, language) if language == "zh" else label, t("mapping.column", language): mapped or t("mapping.not_mapped", language)})
        if mapped: mapped_columns.add(mapped)
    return rows, [column for column in columns if column not in mapped_columns]


def infer_column_kind(series: pd.Series, column_name: str = "") -> str:
    if pd.api.types.is_datetime64_any_dtype(series): return "datetime"
    if pd.api.types.is_numeric_dtype(series): return "numeric"
    if any(token in column_name.lower() for token in ("date", "time", "month", "year")):
        parsed = pd.to_datetime(series, errors="coerce")
        if len(series) and parsed.notna().mean() >= 0.75: return "datetime"
    return "categorical"


def recommend_chart_type(df: pd.DataFrame, x_column: str, y_column: str) -> tuple[str | None, str | None]:
    if x_column == y_column: return None, "X and Y must use different columns."
    x_kind, y_kind = infer_column_kind(df[x_column], x_column), infer_column_kind(df[y_column], y_column)
    if x_kind == "datetime" and y_kind == "numeric": return "line", None
    if x_kind == "categorical" and y_kind == "numeric": return "bar", None
    if x_kind == "numeric" and y_kind == "numeric": return "scatter", None
    return None, "Select a numeric Y column and a date, category, or numeric X column."


def time_aggregation_for(metric: str) -> str:
    return "mean" if metric.lower() in MEAN_TIME_METRICS or "rate" in metric.lower() else "sum"


def prepare_chart_data(df: pd.DataFrame, x_column: str, y_column: str, chart_type: str) -> pd.DataFrame:
    data = df[[x_column, y_column]].dropna().copy()
    if chart_type == "line":
        data[x_column] = pd.to_datetime(data[x_column], errors="coerce")
        data = data.dropna(subset=[x_column])
        aggregation = time_aggregation_for(y_column)
        return data.groupby(x_column, as_index=False)[y_column].agg(aggregation).sort_values(x_column)
    if chart_type == "bar": return data.groupby(x_column, dropna=False)[y_column].mean().reset_index()
    return data


def risk_cards(analysis_result: dict, language: str = "en") -> list[dict[str, Any]]:
    domain = normalized_domain(analysis_result)
    risks = analysis_result.get("risks", {})
    industry = analysis_result.get("industry_analysis", {})
    kpis = industry.get("kpis", {})
    segments = industry.get("segments", {})
    anomaly_count = len(risks.get("numeric_outliers", []))
    if domain == "saas":
        plan = segments.get("plan_type", {}).get("risk_by_churn", {})
        segment = segments.get("customer_segment", {}).get("risk_by_churn", {})
        return [
            {"label": t("risk.highest_churn_plan", language), "value": plan.get("plan_type", "N/A")},
            {"label": t("risk.highest_churn_segment", language), "value": segment.get("customer_segment", "N/A")},
            {"label": display_label("support_tickets", language), "value": format_business_value("support_tickets", kpis.get("total_support_tickets"))},
            {"label": t("risk.numeric_anomalies", language), "value": str(anomaly_count)},
        ]
    if domain == "logistics":
        carrier = segments.get("carrier", {}).get("risk_by_delay", {})
        region_rows = segments.get("region", {}).get("rows", [])
        damage_region = max(region_rows, key=lambda row: row.get("damage_rate", 0), default={})
        return [
            {"label": t("risk.delayed_shipments", language), "value": format_business_value("delay_count", kpis.get("delayed_shipments"))},
            {"label": t("risk.damaged_shipments", language), "value": format_business_value("damage_count", kpis.get("damage_shipments"))},
            {"label": t("risk.highest_delay_carrier", language), "value": carrier.get("carrier", "N/A")},
            {"label": t("risk.highest_damage_region", language), "value": damage_region.get("region", "N/A")},
            {"label": t("risk.operational_anomalies", language), "value": str(anomaly_count)},
        ]
    return [
        {"label": display_label("loss_records", language), "value": format_business_value("record_count", risks.get("loss_records", {}).get("count", 0))},
        {"label": t("risk.loss_amount", language), "value": f"{abs(float(risks.get('loss_records', {}).get('total_loss', 0))):,.2f}"},
        {"label": t("risk.high_discount_loss", language), "value": format_business_value("record_count", risks.get("high_discount_loss_records", {}).get("count", 0))},
        {"label": t("risk.numeric_anomalies", language), "value": str(anomaly_count)},
    ]
