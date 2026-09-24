from pathlib import Path

import pandas as pd
import pytest

from agents.data_analyzer import DataAnalyzerAgent


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"


def run_sample(filename: str) -> dict:
    analyzer = DataAnalyzerAgent()
    return analyzer.run(str(DATA_DIR / filename), "comprehensive business analysis")


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (["month", "mrr", "arr", "churn_rate"], "saas"),
        (["shipping_cost", "delivery_time_days", "delay_flag"], "logistics"),
        (["sales", "profit", "region"], "generic"),
    ],
)
def test_detect_industry(columns, expected):
    assert DataAnalyzerAgent.detect_industry({"columns": columns}) == expected


def test_saas_sample_builds_industry_kpis_and_segments():
    result = run_sample("saas_metrics_sample.csv")

    industry = result["industry_analysis"]
    kpis = industry["kpis"]

    assert industry["industry"] == "saas"
    assert kpis["snapshot_period"] == "2025-12"
    assert kpis["current_mrr"] == pytest.approx(384_300.00)
    assert kpis["current_arr"] == pytest.approx(4_611_600.00)
    assert kpis["mrr_growth_percent"] == pytest.approx(47.81)
    assert kpis["total_new_customers"] == 993
    assert kpis["total_churned_customers"] == 343
    assert kpis["average_churn_rate_percent"] == pytest.approx(2.41)
    assert kpis["total_expansion_revenue"] == pytest.approx(405_900.00)
    assert industry["segments"]["plan_type"]["best_by_mrr"]["plan_type"] == "Enterprise"
    assert industry["segments"]["plan_type"]["best_by_mrr"]["mrr"] == pytest.approx(219_000.00)
    assert "plan_type" in industry["segments"]
    assert "customer_segment" in industry["segments"]


def test_logistics_sample_builds_industry_kpis_and_segments():
    result = run_sample("logistics_operations_sample.csv")

    industry = result["industry_analysis"]
    kpis = industry["kpis"]

    assert industry["industry"] == "logistics"
    assert kpis["total_shipments"] == 36
    assert kpis["delayed_shipments"] == 17
    assert kpis["delay_rate"] == pytest.approx(0.4722)
    assert kpis["damage_rate"] == pytest.approx(0.1389)
    assert kpis["average_delivery_time_days"] == pytest.approx(3.92)
    assert kpis["shipping_cost_ratio"] == pytest.approx(0.1024)
    assert "carrier" in industry["segments"]
    assert "route" in industry["segments"]
    assert result["field_roles"]["order"] is None
    assert "order_count" not in result["kpis"]


def test_retail_sample_keeps_generic_sales_kpis():
    result = run_sample("retail_sales_sample.csv")

    assert result["industry_analysis"]["industry"] == "generic"
    assert result["overview"]["row_count"] == 36
    assert result["kpis"]["total_sales"] == pytest.approx(33_130.00)
    assert result["kpis"]["total_profit"] == pytest.approx(6_588.00)
    assert result["kpis"]["profit_margin_percent"] == pytest.approx(19.89)
    assert result["risks"]["loss_records"]["count"] == 6
    assert result["risks"]["high_discount_loss_records"]["count"] == 4
    assert result["field_roles"]["order"] == "order_id"
    assert result["kpis"]["order_count"] == 36


def test_expansion_revenue_is_not_inferred_as_generic_sales():
    analyzer = DataAnalyzerAgent()
    analyzer.df = pd.DataFrame({"expansion_revenue": [100.0], "mrr": [500.0]})
    schema = analyzer.infer_schema()

    assert analyzer.infer_field_roles(schema)["sales"] is None


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (["order_value", "shipping_cost"], None),
        (["order_value", "order_id"], "order_id"),
        (["shipment_id", "order_value"], "shipment_id"),
    ],
)
def test_order_identifier_inference_rejects_values(columns, expected):
    assert DataAnalyzerAgent.find_order_identifier(columns) == expected


def test_saas_snapshot_metrics_follow_latest_period_not_history_sum():
    analyzer = DataAnalyzerAgent()
    analyzer.df = pd.DataFrame(
        {
            "month": ["2025-01", "2025-01", "2025-02", "2025-02"],
            "plan_type": ["Starter", "Enterprise", "Starter", "Enterprise"],
            "mrr": [10.0, 30.0, 20.0, 50.0],
            "arr": [120.0, 360.0, 240.0, 600.0],
            "churn_rate": [0.04, 0.01, 0.03, 0.01],
        }
    )

    analysis = analyzer.build_saas_analysis()

    assert analysis["kpis"]["snapshot_period"] == "2025-02"
    assert analysis["kpis"]["current_mrr"] == pytest.approx(70.0)
    assert analysis["kpis"]["current_arr"] == pytest.approx(840.0)
    assert analysis["kpis"]["mrr_growth_percent"] == pytest.approx(75.0)
    assert analysis["segments"]["plan_type"]["best_by_mrr"]["mrr"] == pytest.approx(50.0)



def test_retail_customer_name_precedes_customer_segment():
    analyzer = DataAnalyzerAgent()
    analyzer.load_data(str(DATA_DIR / "retail_sales_sample.csv"))
    schema = analyzer.infer_schema()
    roles = analyzer.infer_field_roles(schema)
    assert roles["customer"] == "customer_name"
    assert roles["segment"] == "customer_segment"


def test_binary_flags_are_not_generic_numeric_outliers_but_still_power_logistics_kpis():
    result = run_sample("logistics_operations_sample.csv")
    outlier_columns = {item["column"] for item in result["risks"]["numeric_outliers"]}
    assert "delay_flag" not in outlier_columns
    assert "damage_flag" not in outlier_columns
    kpis = result["industry_analysis"]["kpis"]
    assert kpis["delayed_shipments"] == 17
    assert kpis["damage_shipments"] == 5
    assert kpis["delay_rate"] == pytest.approx(0.4722)
    assert kpis["damage_rate"] == pytest.approx(0.1389)
