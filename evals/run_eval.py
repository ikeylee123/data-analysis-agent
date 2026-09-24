from __future__ import annotations

from pathlib import Path
import math
import sys

from agents.data_analyzer import DataAnalyzerAgent
from agents.report_generator import ReportGeneratorAgent


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "sample"
REPORT_SETTINGS = {
    "language": "English",
    "tone": "Analyst Report",
    "length": "Detailed",
}

CASES = {
    "Retail": {
        "fixture": "retail_sales_sample.csv",
        "expected": {
            "row_count": 36,
            "total_sales": 33_130.00,
            "total_profit": 6_588.00,
            "profit_margin_percent": 19.89,
            "loss_records": 6,
            "high_discount_loss_records": 4,
        },
    },
    "SaaS": {
        "fixture": "saas_metrics_sample.csv",
        "expected": {
            "snapshot_period": "2025-12",
            "current_mrr": 384_300.00,
            "current_arr": 4_611_600.00,
            "average_churn_rate_percent": 2.41,
            "mrr_growth_percent": 47.81,
        },
    },
    "Logistics": {
        "fixture": "logistics_operations_sample.csv",
        "expected": {
            "total_shipments": 36,
            "delay_rate": 0.4722,
            "damage_rate": 0.1389,
            "average_delivery_time_days": 3.92,
            "shipping_cost_ratio": 0.1024,
        },
    },
}


def offline_generator() -> ReportGeneratorAgent:
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    generator.has_api_key = False
    generator.llm = None
    return generator


def values_match(actual, expected) -> bool:
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and math.isclose(
            float(actual), expected, rel_tol=1e-6, abs_tol=1e-4
        )
    return actual == expected


def metric_values(domain: str, analysis: dict) -> dict:
    if domain == "Retail":
        return {
            "row_count": analysis["overview"]["row_count"],
            "total_sales": analysis["kpis"].get("total_sales"),
            "total_profit": analysis["kpis"].get("total_profit"),
            "profit_margin_percent": analysis["kpis"].get("profit_margin_percent"),
            "loss_records": analysis["risks"].get("loss_records", {}).get("count"),
            "high_discount_loss_records": analysis["risks"].get(
                "high_discount_loss_records", {}
            ).get("count"),
        }
    return analysis["industry_analysis"]["kpis"]


def evaluate_case(domain: str, case: dict) -> dict[str, bool]:
    analyzer = DataAnalyzerAgent()
    analysis = analyzer.run(
        str(DATA_DIR / case["fixture"]),
        "comprehensive business analysis",
    )
    actual = metric_values(domain, analysis)
    kpi_ok = all(values_match(actual.get(key), value) for key, value in case["expected"].items())

    generator = offline_generator()
    schema = generator.build_report_schema(analysis, "")
    content = generator.generate_local_report(
        analysis,
        "",
        report_settings=REPORT_SETTINGS,
    )
    structure_ok = generator.validate_generated_report(
        content,
        schema,
        REPORT_SETTINGS,
    ) == []

    fallback_result = generator.run(analysis, "", REPORT_SETTINGS)
    fallback_ok = (
        fallback_result["source"] == "local"
        and fallback_result["repair_attempted"] is False
        and fallback_result["fallback_reason"] is None
    )

    separation_ok = (
        bool(schema.get("Key Insights with Evidence"))
        and bool(schema.get("Root Cause Hypotheses"))
        and bool(schema.get("Recommended Action Plan"))
        and all(
            "Supporting Evidence" in item and "Data Needed for Validation" in item
            for item in schema.get("Root Cause Hypotheses", [])
        )
        and "## 3. Key Insights with Evidence" in content
        and "## 5. Root Cause Hypotheses" in content
        and "## 6. Recommended Action Plan" in content
    )

    return {
        "KPI correctness": kpi_ok,
        "Report structure": structure_ok,
        "Reliability/fallback": fallback_ok,
        "Evidence separation": separation_ok,
    }


def main() -> int:
    results = {domain: evaluate_case(domain, case) for domain, case in CASES.items()}
    dimensions = next(iter(results.values())).keys()
    print("| Domain | " + " | ".join(dimensions) + " |")
    print("| --- | " + " | ".join("---" for _ in dimensions) + " |")
    for domain, checks in results.items():
        values = ["PASS" if passed else "FAIL" for passed in checks.values()]
        print(f"| {domain} | " + " | ".join(values) + " |")
    return 0 if all(all(checks.values()) for checks in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())