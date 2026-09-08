from pathlib import Path

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
    assert kpis["total_mrr"] > 0
    assert kpis["total_arr"] > 0
    assert kpis["total_new_customers"] > 0
    assert kpis["average_churn_rate_percent"] > 0
    assert "plan_type" in industry["segments"]
    assert "customer_segment" in industry["segments"]


def test_logistics_sample_builds_industry_kpis_and_segments():
    result = run_sample("logistics_operations_sample.csv")

    industry = result["industry_analysis"]
    kpis = industry["kpis"]

    assert industry["industry"] == "logistics"
    assert kpis["total_shipments"] == result["overview"]["row_count"]
    assert kpis["delayed_shipments"] >= 0
    assert 0 <= kpis["delay_rate"] <= 1
    assert 0 <= kpis["damage_rate"] <= 1
    assert "carrier" in industry["segments"]
    assert "route" in industry["segments"]


def test_retail_sample_keeps_generic_sales_kpis():
    result = run_sample("retail_sales_sample.csv")

    assert result["industry_analysis"]["industry"] == "generic"
    assert result["kpis"]["record_count"] == result["overview"]["row_count"]
    assert result["kpis"]["total_sales"] > 0
    assert "profit_margin_percent" in result["kpis"]
    assert "loss_records" in result["risks"]
