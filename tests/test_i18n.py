import pytest

from utils.i18n import TRANSLATIONS, display_label, domain_label, resolve_report_language, t
from utils.ui_helpers import plotly_key, primary_kpi_cards, reliability_status_items


def test_translation_catalogs_have_identical_complete_keys():
    assert TRANSLATIONS["en"]
    assert set(TRANSLATIONS["en"]) == set(TRANSLATIONS["zh"])


def test_translation_lookup_and_missing_key_behavior():
    assert t("nav.analytics", "en") == "Business Analytics"
    assert t("nav.analytics", "zh") == "业务分析"
    with pytest.raises(KeyError):
        t("missing.key", "en")


def test_domain_and_display_labels_are_bilingual():
    assert domain_label("retail", "zh") == "零售"
    assert display_label("total_sales", "en") == "Total Sales"
    assert display_label("total_sales", "zh") == "总销售额"


def test_report_language_choice_is_resolved_independently():
    assert resolve_report_language("follow_ui", "en") == "English"
    assert resolve_report_language("follow_ui", "zh") == "Chinese"
    assert resolve_report_language("en", "zh") == "English"
    assert resolve_report_language("zh", "en") == "Chinese"


def test_chinese_kpi_and_reliability_labels_are_localized():
    retail = {"industry_analysis": {"industry": "retail", "kpis": {}}, "kpis": {}, "risks": {}}
    assert primary_kpi_cards(retail, "zh")[0]["label"] == "总销售额"
    report = {"source": "local", "provider_status": "rate_limited", "report_validation_status": "not_run", "kpi_fidelity_status": "not_run", "fallback_used": True}
    statuses = dict(reliability_status_items(report, "zh"))
    assert statuses["报告来源"] == "本地回退"
    assert statuses["服务状态"] == "配额受限"


def test_plotly_keys_do_not_depend_on_presentation_language():
    english = plotly_key("retail", "main", "sales_profit_category")
    chinese = plotly_key("retail", "main", "sales_profit_category")
    assert english == chinese
from pathlib import Path


def test_saas_and_chart_labels_are_bilingual():
    assert domain_label("saas", "en") == "SaaS"
    assert domain_label("saas", "zh") == "SaaS"
    assert t("chart.saas_plan_mrr", "en") == "Current MRR by Plan"
    assert t("chart.saas_plan_mrr", "zh") == "按套餐查看当前 MRR"
    assert display_label("churn_rate_percent", "zh") == "流失率 (%)"


def test_widget_keys_are_language_independent_literals():
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    for key in (
        "ui_language_selector", "start_new_analysis_button", "current_page_selector",
        "run_analysis_button", "report_language_selector", "generate_report_button",
    ):
        assert f'key="{key}"' in app_source
    assert "key=t(" not in app_source


def test_sidebar_radio_identity_labels_are_constant():
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert '"UI language", ["en", "zh"]' in app_source
    assert '"Application page", ["overview", "analytics", "report"]' in app_source
    assert 'key="ui_language_selector", label_visibility="collapsed"' in app_source
    assert 'key="current_page_selector", label_visibility="collapsed"' in app_source
    assert 'key="current_page"' not in app_source
