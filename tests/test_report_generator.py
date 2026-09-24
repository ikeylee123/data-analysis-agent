from pathlib import Path

import pytest

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
    assert result["provider_status"] == "available"
    assert result["report_validation_status"] == "passed"
    assert result["kpi_fidelity_status"] == "passed"
    assert result["fallback_used"] is False


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


def test_markdown_validator_rejects_empty_and_unstructured_output():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)

    assert generator.validate_report_markdown("", ENGLISH_DETAILED) == ["Report content is empty."]
    errors = generator.validate_report_markdown("plain text without report sections", ENGLISH_DETAILED)
    assert "Missing section 1." in errors
    assert "KPI Snapshot section is missing or not isolated." in errors


def test_missing_api_key_uses_deterministic_local_report():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    generator.has_api_key = False
    generator.llm = None

    result = generator.run(logistics_analysis(), "", ENGLISH_DETAILED)

    assert result["source"] == "local"
    assert result["repair_attempted"] is False
    assert result["fallback_reason"] is None
    assert result["provider_status"] == "configuration_error"
    assert result["report_validation_status"] == "not_run"
    assert result["kpi_fidelity_status"] == "not_run"
    assert result["fallback_used"] is True
    assert "## 5. Root Cause Hypotheses" in result["content"]


def test_provider_exception_uses_deterministic_fallback(monkeypatch):
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    generator.has_api_key = True
    generator.llm = None

    def raise_provider_error(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(generator, "generate_ai_report", raise_provider_error)
    result = generator.run(logistics_analysis(), "", ENGLISH_DETAILED)

    assert result["source"] == "local"
    assert result["fallback_reason"] == "provider unavailable"
    assert "## 7. Data Limitations" in result["content"]


def test_report_schema_separates_evidence_hypotheses_and_actions():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    schema = generator.build_report_schema(logistics_analysis(), "")
    content = generator.render_schema_markdown(schema, report_settings=ENGLISH_DETAILED)

    assert schema["Key Insights with Evidence"]
    assert schema["Root Cause Hypotheses"]
    assert schema["Recommended Action Plan"]
    assert all("Supporting Evidence" in item for item in schema["Root Cause Hypotheses"])
    assert all("Data Needed for Validation" in item for item in schema["Root Cause Hypotheses"])
    assert "## 3. Key Insights with Evidence" in content
    assert "## 5. Root Cause Hypotheses" in content
    assert "## 6. Recommended Action Plan" in content


def test_numeric_fidelity_rejects_changed_critical_kpi():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    analysis = logistics_analysis()
    schema, content = local_logistics_report(generator, analysis)
    changed = content.replace("| Delay Rate | 47.22% |", "| Delay Rate | 99.99% |", 1)

    errors = generator.validate_generated_report(changed, schema, ENGLISH_DETAILED)

    assert "Critical KPI value does not match deterministic schema: delay_rate." in errors


def test_numeric_fidelity_failure_uses_existing_repair_path(monkeypatch):
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    generator.has_api_key = True
    generator.llm = None
    analysis = logistics_analysis()
    _, good_content = local_logistics_report(generator, analysis)
    changed = good_content.replace("| Delay Rate | 47.22% |", "| Delay Rate | 99.99% |", 1)

    monkeypatch.setattr(generator, "generate_ai_report", lambda *args, **kwargs: changed)
    monkeypatch.setattr(generator, "repair_report_markdown", lambda *args, **kwargs: good_content)

    result = generator.run(analysis, "", ENGLISH_DETAILED)

    assert result["source"] == "gemini_repaired"
    assert result["repair_attempted"] is True
    assert any("delay_rate" in error for error in result["validation_errors"])
    assert result["repair_errors"] == []



def test_logistics_percentage_equivalent_ratio_notation_passes_kpi_fidelity():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    schema, content = local_logistics_report(generator, logistics_analysis())
    equivalent = content.replace("| Shipping Cost Ratio | 10.24% |", "| Shipping Cost Ratio | 0.1024 |")
    equivalent = equivalent.replace("| Delay Rate | 47.22% |", "| Delay Rate | 0.4722 |")
    equivalent = equivalent.replace("| Damage Rate | 13.89% |", "| Damage Rate | 0.1389 |")
    assert generator.validate_critical_kpi_fidelity(equivalent, schema, ENGLISH_DETAILED) == []


def test_logistics_percentage_genuine_drift_still_fails():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    schema, content = local_logistics_report(generator, logistics_analysis())
    changed = content.replace("| Delay Rate | 47.22% |", "| Delay Rate | 48.22% |")
    errors = generator.validate_critical_kpi_fidelity(changed, schema, ENGLISH_DETAILED)
    assert "Critical KPI value does not match deterministic schema: delay_rate." in errors


def test_supported_kpi_label_alias_passes_fidelity():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    schema, content = local_logistics_report(generator, logistics_analysis())
    aliased = content.replace("| Average Delivery Time |", "| Avg Delivery Time |")
    assert generator.validate_critical_kpi_fidelity(aliased, schema, ENGLISH_DETAILED) == []


def test_retail_record_count_is_not_management_critical():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    analysis = DataAnalyzerAgent().run(str(DATA_DIR / "retail_sales_sample.csv"), "audit")
    schema = generator.build_report_schema(analysis, "")
    content = generator.render_schema_markdown(schema, report_settings=ENGLISH_DETAILED)
    without_record_count = "\n".join(line for line in content.splitlines() if not line.startswith("| Record Count |"))
    errors = generator.validate_critical_kpi_fidelity(without_record_count, schema, ENGLISH_DETAILED)
    assert not any("record_count" in error for error in errors)
    assert schema["Industry"] == "retail"



def retail_schema_and_report():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    analysis = analysis_for("retail_sales_sample.csv")
    schema = generator.build_report_schema(analysis, "")
    content = generator.render_schema_markdown(schema, report_settings=ENGLISH_DETAILED)
    return generator, schema, content


@pytest.mark.parametrize(
    ("label", "canonical", "formatted"),
    [
        ("Total Sales", "33,130.00", "33130"),
        ("Total Sales", "33,130.00", "33130.00"),
        ("Total Sales", "33,130.00", "33,130"),
        ("Total Sales", "33,130.00", "33,130.00"),
        ("Total Sales", "33,130.00", "$33,130.00"),
        ("Total Profit", "6,588.00", "6588"),
        ("Total Profit", "6,588.00", "6,588.00"),
        ("Total Profit", "6,588.00", "$6,588.00"),
        ("Profit Margin", "19.89%", "19.89"),
        ("Profit Margin", "19.89%", "19.89%"),
        ("Profit Margin", "19.89%", "0.1989"),
    ],
)
def test_retail_equivalent_kpi_formats_pass_fidelity(label, canonical, formatted):
    generator, schema, content = retail_schema_and_report()
    changed = content.replace(f"| {label} | {canonical} |", f"| {label} | {formatted} |")
    assert generator.validate_critical_kpi_fidelity(changed, schema, ENGLISH_DETAILED) == []


@pytest.mark.parametrize(
    ("label", "canonical", "drifted", "metric"),
    [
        ("Total Sales", "33,130.00", "34,130.00", "total_sales"),
        ("Total Profit", "6,588.00", "7,588.00", "total_profit"),
        ("Profit Margin", "19.89%", "20.89%", "profit_margin_percent"),
    ],
)
def test_retail_genuine_kpi_drift_fails(label, canonical, drifted, metric):
    generator, schema, content = retail_schema_and_report()
    changed = content.replace(f"| {label} | {canonical} |", f"| {label} | {drifted} |")
    errors = generator.validate_critical_kpi_fidelity(changed, schema, ENGLISH_DETAILED)
    assert f"Critical KPI value does not match deterministic schema: {metric}." in errors



def test_chinese_retail_kpi_labels_remain_distinct_and_pass_fidelity():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    analysis = analysis_for("retail_sales_sample.csv")
    schema = generator.build_report_schema(analysis, "")
    chinese_settings = {"language": "Chinese", "tone": "Executive Summary", "length": "Brief"}
    content = generator.render_schema_markdown(schema, report_settings=chinese_settings)
    assert generator.normalized_kpi_label("总销售额") == "总销售额"
    assert generator.normalized_kpi_label("总利润") == "总利润"
    assert generator.normalized_kpi_label("利润率（%）") == "利润率"
    assert generator.validate_critical_kpi_fidelity(content, schema, chinese_settings) == []


def test_chinese_retail_genuine_kpi_drift_still_fails():
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    analysis = analysis_for("retail_sales_sample.csv")
    schema = generator.build_report_schema(analysis, "")
    chinese_settings = {"language": "Chinese", "tone": "Executive Summary", "length": "Brief"}
    content = generator.render_schema_markdown(schema, report_settings=chinese_settings)
    changed = content.replace("| 总销售额 | 33,130.00 |", "| 总销售额 | 34,130.00 |")
    errors = generator.validate_critical_kpi_fidelity(changed, schema, chinese_settings)
    assert "Critical KPI value does not match deterministic schema: total_sales." in errors



def test_direct_gemini_success_has_available_passed_metadata(monkeypatch):
    generator = ReportGeneratorAgent()
    analysis = logistics_analysis()
    _, good_content = local_logistics_report(generator, analysis)
    monkeypatch.setattr(generator, "has_api_key", True)
    monkeypatch.setattr(generator, "generate_ai_report", lambda *args, **kwargs: good_content)
    result = generator.run(analysis, "", ENGLISH_DETAILED)
    assert result["source"] == "gemini"
    assert result["provider_status"] == "available"
    assert result["report_validation_status"] == "passed"
    assert result["kpi_fidelity_status"] == "passed"
    assert result["fallback_used"] is False


@pytest.mark.parametrize(
    ("message", "expected_status"),
    [
        ("HTTP 429 quota exceeded for Gemini 2.5 Flash", "rate_limited"),
        ("HTTP 503 service unavailable", "unavailable"),
    ],
)
def test_provider_failure_skips_validation_and_activates_fallback(monkeypatch, message, expected_status):
    generator = ReportGeneratorAgent.__new__(ReportGeneratorAgent)
    generator.has_api_key = True
    generator.llm = None
    monkeypatch.setattr(generator, "generate_ai_report", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError(message)))
    result = generator.run(logistics_analysis(), "", ENGLISH_DETAILED)
    assert result["source"] == "local"
    assert result["provider_status"] == expected_status
    assert result["report_validation_status"] == "not_run"
    assert result["kpi_fidelity_status"] == "not_run"
    assert result["fallback_used"] is True


def test_content_validation_failure_keeps_provider_available(monkeypatch):
    generator = ReportGeneratorAgent()
    analysis = logistics_analysis()
    _, good_content = local_logistics_report(generator, analysis)
    bad_content = good_content.replace("| Delay Rate | 47.22% |", "| Delay Rate | 99.00% |")
    monkeypatch.setattr(generator, "has_api_key", True)
    monkeypatch.setattr(generator, "generate_ai_report", lambda *args, **kwargs: bad_content)
    monkeypatch.setattr(generator, "repair_report_markdown", lambda *args, **kwargs: bad_content)
    result = generator.run(analysis, "", ENGLISH_DETAILED)
    assert result["source"] == "local"
    assert result["provider_status"] == "available"
    assert result["report_validation_status"] == "failed"
    assert result["kpi_fidelity_status"] == "failed"
    assert result["fallback_used"] is True
