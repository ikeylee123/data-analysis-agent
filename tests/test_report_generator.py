from pathlib import Path

from agents.data_analyzer import DataAnalyzerAgent
from agents.report_generator import ReportGeneratorAgent


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "sample"
ENGLISH_DETAILED = {
    "language": "English",
    "tone": "Analyst Report",
    "length": "Detailed",
}


def analysis_for(filename: str) -> dict:
    analyzer = DataAnalyzerAgent()
    return analyzer.run(str(DATA_DIR / filename), "comprehensive business analysis")


def logistics_analysis() -> dict:
    return analysis_for("logistics_operations_sample.csv")


def local_logistics_report(generator: ReportGeneratorAgent, analysis: dict) -> tuple[dict, str]:
    schema = generator.build_report_schema(analysis, "")
    content = generator.generate_local_report(
        analysis,
        "",
        report_settings=ENGLISH_DETAILED,
    )
    return schema, content


def test_logistics_report_schema_uses_industry_specific_sections():
    generator = ReportGeneratorAgent()
    schema = generator.build_report_schema(logistics_analysis(), "")

    metrics = [item["metric"] for item in schema["KPI Snapshot"]]

    assert schema["Industry"] == "logistics"
    assert "delay_rate" in metrics
    assert "damage_rate" in metrics
    assert len(schema["Root Cause Hypotheses"]) == 1
    assert len(schema["Recommended Action Plan"]) == 3


def test_local_logistics_report_passes_generated_report_validation():
    generator = ReportGeneratorAgent()
    analysis = logistics_analysis()
    schema, content = local_logistics_report(generator, analysis)

    assert generator.validate_generated_report(content, schema, ENGLISH_DETAILED) == []


def test_markdown_validator_rejects_bad_kpi_table_separator():
    generator = ReportGeneratorAgent()
    bad_content = (
        "# Business Performance Insight Report\n\n"
        "1. Executive Summary\n\n"
        "Text.\n\n"
        "2. KPI Snapshot\n\n"
        "| Metric | Value | Business Interpretation |\n"
        "| --- | --- | " + "-" * 220 + " |\n"
        "| Delay Rate | 47.22% | Delay risk. |\n\n"
        "3. Key Insights with Evidence\n\n"
        "Text.\n\n"
        "4. Segment Deep Dive\n\n"
        "Text.\n\n"
        "5. Root Cause Hypotheses\n\n"
        "| Hypothesis | Evidence Level | Supporting Evidence | Data Needed for Validation |\n"
        "| --- | --- | --- | --- |\n"
        "| Carrier execution may contribute to delays. | Medium confidence | Delay data. | SLA data. |\n\n"
        "6. Recommended Action Plan\n\n"
        "| Priority | Action | Rationale | Owner | Timeframe | KPI to Track |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| High | Review delay exceptions. | Delay rate is high. | Ops | 2 weeks | delay rate |\n\n"
        "7. Data Limitations\n\n"
        "- Limited data."
    )

    errors = generator.validate_report_markdown(bad_content, ENGLISH_DETAILED)

    assert "KPI Snapshot table separator is suspiciously long." in errors


def test_schema_fidelity_rejects_extra_action_rows_and_unsupported_causes():
    generator = ReportGeneratorAgent()
    analysis = logistics_analysis()
    schema, content = local_logistics_report(generator, analysis)
    bad_content = content.replace(
        "| Medium | Add structured exception reason tracking for delayed and damaged shipments. |",
        "| Medium | Add structured exception reason tracking for delayed and damaged shipments. |\n"
        "| Low | Blame weather delays. | Weather is the root cause. | Ops | 1 week | delay rate |",
    ).replace(
        "Damage should be tracked",
        "Damage is caused by weather and should be tracked",
    )

    errors = generator.validate_generated_report(bad_content, schema, ENGLISH_DETAILED)

    assert any("Recommended Action Plan has" in error for error in errors)
    assert any("Unsupported deterministic causal claim" in error for error in errors)


def test_run_repairs_invalid_gemini_output(monkeypatch):
    generator = ReportGeneratorAgent()
    analysis = logistics_analysis()
    _, good_content = local_logistics_report(generator, analysis)
    bad_content = good_content.replace(
        "| Medium | Add structured exception reason tracking for delayed and damaged shipments. |",
        "| Medium | Add structured exception reason tracking for delayed and damaged shipments. |\n"
        "| Low | Blame weather delays. | Weather is the root cause. | Ops | 1 week | delay rate |",
    )

    monkeypatch.setattr(generator, "has_api_key", True)
    monkeypatch.setattr(generator, "generate_ai_report", lambda *args, **kwargs: bad_content)
    monkeypatch.setattr(generator, "repair_report_markdown", lambda *args, **kwargs: good_content)

    result = generator.run(analysis, "", ENGLISH_DETAILED)

    assert result["source"] == "gemini_repaired"
    assert result["repair_attempted"] is True
    assert result["repair_errors"] == []
    assert result["fallback_reason"] is None


def test_run_falls_back_when_repair_remains_invalid(monkeypatch):
    generator = ReportGeneratorAgent()
    analysis = logistics_analysis()
    _, good_content = local_logistics_report(generator, analysis)
    bad_content = good_content.replace(
        "| Medium | Add structured exception reason tracking for delayed and damaged shipments. |",
        "| Medium | Add structured exception reason tracking for delayed and damaged shipments. |\n"
        "| Low | Blame weather delays. | Weather is the root cause. | Ops | 1 week | delay rate |",
    )

    monkeypatch.setattr(generator, "has_api_key", True)
    monkeypatch.setattr(generator, "generate_ai_report", lambda *args, **kwargs: bad_content)
    monkeypatch.setattr(generator, "repair_report_markdown", lambda *args, **kwargs: bad_content)

    result = generator.run(analysis, "", ENGLISH_DETAILED)

    assert result["source"] == "local"
    assert result["repair_attempted"] is True
    assert result["fallback_reason"].startswith(
        "Gemini output failed markdown validation after repair:"
    )
    assert result["repair_errors"]
