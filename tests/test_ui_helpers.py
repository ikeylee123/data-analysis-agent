from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from agents.data_analyzer import DataAnalyzerAgent
from utils.ui_helpers import (
    format_business_value,
    format_kpi_card_value,
    format_segment_table,
    humanize_label,
    humanize_report_markdown_labels,
    plotly_key,
    prepare_chart_data,
    reliability_status_items,
    report_content_for_display,
    risk_cards,
    sanitize_technical_reason,
    time_aggregation_for,
    primary_kpi_cards,
    recommend_chart_type,
    relevant_field_mapping,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"


def analysis_for(filename: str) -> dict:
    return DataAnalyzerAgent().run(str(DATA_DIR / filename), "综合业务分析")


def card_values(result: dict) -> dict:
    return {card["label"]: card["value"] for card in primary_kpi_cards(result)}


def test_retail_primary_kpi_cards_are_management_focused():
    cards = primary_kpi_cards(analysis_for("retail_sales_sample.csv"))
    values = {card["label"]: card["value"] for card in cards}

    assert [card["label"] for card in cards] == [
        "Total Sales", "Total Profit", "Profit Margin", "Loss Records", "Average Discount"
    ]
    assert values["Total Sales"] == pytest.approx(33_130.00)
    assert values["Total Profit"] == pytest.approx(6_588.00)
    assert values["Profit Margin"] == pytest.approx(19.89)
    assert values["Loss Records"] == 6
    assert values["Average Discount"] == pytest.approx(13.50)


def test_saas_primary_kpi_cards_use_snapshot_semantics():
    values = card_values(analysis_for("saas_metrics_sample.csv"))

    assert values == {
        "Current MRR": pytest.approx(384_300.00),
        "Current ARR": pytest.approx(4_611_600.00),
        "Churn Rate": pytest.approx(2.41),
        "MRR Growth": pytest.approx(47.81),
        "Expansion Revenue": pytest.approx(405_900.00),
    }


def test_logistics_primary_kpi_cards_are_operational():
    values = card_values(analysis_for("logistics_operations_sample.csv"))

    assert values == {
        "Total Shipments": 36,
        "Delay Rate": pytest.approx(0.4722),
        "Damage Rate": pytest.approx(0.1389),
        "Avg Delivery Time": pytest.approx(3.92),
        "Shipping Cost Ratio": pytest.approx(0.1024),
    }


def test_kpi_card_formatting_uses_clear_units():
    assert format_kpi_card_value(384300, "currency") == "384,300.00"
    assert format_kpi_card_value(0.4722, "ratio_percent") == "47.22%"
    assert format_kpi_card_value(19.89, "percent_number") == "19.89%"
    assert format_kpi_card_value(3.92, "days") == "3.92 days"
    assert format_kpi_card_value(36, "count") == "36"


@pytest.mark.parametrize(
    ("x", "y", "expected"),
    [
        ("date", "value", "line"),
        ("category", "value", "bar"),
        ("value", "other_value", "scatter"),
    ],
)
def test_chart_recommendation_is_type_aware(x, y, expected):
    df = pd.DataFrame(
        {
            "date": ["2025-03", "2025-01", "2025-02"],
            "category": ["B", "A", "A"],
            "value": [3.0, 1.0, 2.0],
            "other_value": [30.0, 10.0, 20.0],
        }
    )

    chart_type, error = recommend_chart_type(df, x, y)

    assert chart_type == expected
    assert error is None


def test_same_axis_is_rejected():
    df = pd.DataFrame({"value": [1, 2]})

    chart_type, error = recommend_chart_type(df, "value", "value")

    assert chart_type is None
    assert error == "X and Y must use different columns."


def test_datetime_line_data_is_sorted():
    df = pd.DataFrame({"month": ["2025-03", "2025-01", "2025-02"], "mrr": [3, 1, 2]})

    prepared = prepare_chart_data(df, "month", "mrr", "line")

    assert prepared["mrr"].tolist() == [1, 2, 3]
    assert prepared["month"].is_monotonic_increasing


def test_retail_field_mapping_excludes_irrelevant_domain_roles():
    columns = ["date", "order_id", "sales", "profit", "region", "category", "notes"]
    roles = {
        "sales": "sales",
        "profit": "profit",
        "discount": None,
        "quantity": None,
        "region": "region",
        "category": "category",
        "segment": None,
        "product": None,
        "order": "order_id",
        "date": "date",
    }

    rows, other = relevant_field_mapping("retail", columns, roles)

    labels = [row["Business Role"] for row in rows]
    assert "MRR" not in labels
    assert "Carrier" not in labels
    assert {"Sales", "Profit", "Order ID", "Date"}.issubset(labels)
    assert "notes" in other


def test_saas_field_mapping_contains_only_relevant_roles():
    columns = ["month", "plan_type", "customer_segment", "mrr", "arr", "churn_rate", "notes"]

    rows, other = relevant_field_mapping("saas", columns, {})

    labels = [row["Business Role"] for row in rows]
    assert labels == [
        "Period / Date", "Plan", "Customer Segment", "MRR", "ARR", "Churn Rate",
        "New Customers", "Churned Customers", "Expansion Revenue",
        "Support Tickets", "CAC",
    ]
    assert "Profit" not in labels
    assert "notes" in other


def test_ui_helpers_do_not_mutate_analysis_or_workflow_state():
    analysis = analysis_for("retail_sales_sample.csv")
    state = {"analysis_result": analysis, "generated_report": {"content": "same"}}
    before = deepcopy(state)

    primary_kpi_cards(analysis)
    recommend_chart_type(pd.DataFrame({"x": [1], "y": [2]}), "x", "y")

    assert state == before


def test_saas_mapping_includes_support_tickets_and_cac():
    columns = ["month", "plan_type", "customer_segment", "mrr", "arr", "churn_rate", "new_customers", "churned_customers", "expansion_revenue", "support_tickets", "cac"]
    rows, other = relevant_field_mapping("saas", columns, {})
    mapping = {row["Business Role"]: row["Mapped Column"] for row in rows}
    assert mapping["Support Tickets"] == "support_tickets"
    assert mapping["CAC"] == "cac"
    assert "support_tickets" not in other
    assert "cac" not in other


def test_human_readable_formatting_helpers():
    assert humanize_label("new_customers") == "New Customers"
    assert humanize_label("average_delivery_time_days") == "Avg Delivery Time"
    assert format_business_value("churn_rate", 0.044) == "4.40%"
    assert format_business_value("shipment_count", 9) == "9"
    assert format_business_value("average_delivery_time_days", 3.92) == "3.92 days"
    table = format_segment_table([{"plan_type": "Starter", "mrr": 50500, "churn_rate": 0.044}], ["plan_type", "mrr", "churn_rate"])
    assert table.to_dict("records") == [{"Plan": "Starter", "Current MRR": "50,500.00", "Churn Rate": "4.40%"}]


def test_risk_cards_are_domain_aware():
    saas = analysis_for("saas_metrics_sample.csv")
    logistics = analysis_for("logistics_operations_sample.csv")
    saas_labels = {card["label"] for card in risk_cards(saas)}
    logistics_labels = {card["label"] for card in risk_cards(logistics)}
    assert "Loss Records" not in saas_labels
    assert "Loss Records" not in logistics_labels
    assert {"Highest-Churn Plan", "Support Tickets"}.issubset(saas_labels)
    assert {"Delayed Shipments", "Damaged Shipments"}.issubset(logistics_labels)


def test_time_series_aggregates_duplicate_periods_by_metric_semantics():
    df = pd.DataFrame({"date": ["2025-01", "2025-01", "2025-02"], "sales": [10, 20, 5], "delivery_time_days": [2, 4, 6]})
    sales = prepare_chart_data(df, "date", "sales", "line")
    delivery = prepare_chart_data(df, "date", "delivery_time_days", "line")
    assert sales["sales"].tolist() == [30, 5]
    assert delivery["delivery_time_days"].tolist() == [3, 6]
    assert time_aggregation_for("mrr") == "sum"
    assert time_aggregation_for("churn_rate") == "mean"



def test_report_markdown_labels_are_human_readable_without_changing_values():
    content = "| Metric | Value |\n| --- | --- |\n| current_mrr | 384,300.00 |\n| shipping_cost_ratio | 10.24% |"
    rendered = humanize_report_markdown_labels(content)
    assert "| Current MRR | 384,300.00 |" in rendered
    assert "| Shipping Cost Ratio | 10.24% |" in rendered



def test_plotly_keys_separate_main_and_trend_saas_mrr():
    assert plotly_key("saas", "main", "mrr_trend") != plotly_key("saas", "trends", "mrr")


def test_plotly_keys_do_not_collide_across_domains():
    keys = {plotly_key(domain, "correlations", "heatmap") for domain in ("retail", "saas", "logistics")}
    assert len(keys) == 3


def test_advanced_plotly_key_is_stable_and_reflects_chart_state():
    first = plotly_key("advanced", "saas", "month", "mrr", "line")
    assert first == plotly_key("advanced", "saas", "month", "mrr", "line")
    assert first != plotly_key("advanced", "saas", "month", "churn_rate", "line")
    assert first != plotly_key("advanced", "saas", "mrr", "arr", "scatter")



def test_reliability_status_for_rate_limit_does_not_claim_validation_failed():
    report = {"source": "local", "provider_status": "rate_limited", "report_validation_status": "not_run", "kpi_fidelity_status": "not_run", "fallback_used": True}
    assert dict(reliability_status_items(report)) == {
        "Report Source": "Local Fallback", "Provider Status": "Rate Limited",
        "Report Validation": "Not Run", "KPI Fidelity": "Not Run", "Fallback": "Activated",
    }


def test_sanitized_technical_details_hide_credential_like_content():
    fake_bearer = "abcdefghijklmnop"
    unsafe = "HTTP 429 Author" + "ization: Bear" + "er " + fake_bearer + " API_KEY=supersecret C:\\Users\\person\\project"
    sanitized = sanitize_technical_reason(unsafe)
    assert fake_bearer not in sanitized
    assert "supersecret" not in sanitized
    assert "C:\\Users\\person" not in sanitized
    displayed = report_content_for_display("> Error: " + unsafe + "\n# Safe report", hide_fallback_error=True)
    assert "HTTP 429" not in displayed
    assert "# Safe report" in displayed
