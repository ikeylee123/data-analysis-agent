from copy import deepcopy

from utils.session_state import (
    DEFAULT_STATE,
    init_session_state,
    reset_all_state,
    set_analysis_config,
    set_current_page,
    set_dataset_state,
    set_report_config,
    store_analysis_result,
    store_report_result,
    set_ui_language,
)


def populated_state() -> dict:
    state = {}
    init_session_state(state)
    set_dataset_state(
        state,
        signature="dataset-a",
        filename="a.csv",
        file_path="uploads/a.csv",
        dataframe={"rows": 3},
        detected_domain="generic",
        field_mapping={"sales": "sales"},
        data_overview={"row_count": 3},
    )
    store_analysis_result(state, {"kpis": {"total_sales": 10}}, "comprehensive")
    store_report_result(
        state,
        report={
            "content": "report-a",
            "source": "local",
            "provider_status": "rate_limited",
            "report_validation_status": "not_run",
            "kpi_fidelity_status": "not_run",
            "fallback_used": True,
            "validation_errors": [],
            "repair_errors": [],
            "repair_attempted": False,
            "fallback_reason": None,
        },
        report_schema={"KPI Snapshot": []},
        config={"language": "English"},
    )
    return state


def test_initial_state_initializes_all_workflow_groups():
    state = {}

    init_session_state(state)

    assert set(DEFAULT_STATE).issubset(state)
    assert state["uploaded_df"] is None
    assert state["analysis_completed"] is False
    assert state["report_completed"] is False
    assert state["current_page"] == "overview"



def test_navigation_selector_initializes_from_canonical_page_once():
    state = {"current_page": "report"}

    init_session_state(state)

    assert state["current_page"] == "report"
    assert state["current_page_selector"] == "report"


def test_set_current_page_does_not_mutate_widget_owned_selector_key():
    state = {}
    init_session_state(state)
    state["current_page_selector"] = "analytics"  # Simulate the widget update.

    set_current_page(state, "analytics")

    assert state["current_page"] == "analytics"
    assert state["current_page_selector"] == "analytics"

    set_current_page(state, "overview")
    assert state["current_page"] == "overview"
    assert state["current_page_selector"] == "analytics"


def test_set_current_page_rejects_unknown_internal_page():
    import pytest
    with pytest.raises(ValueError):
        set_current_page({}, "数据概览")

def test_same_dataset_does_not_invalidate_analysis_or_report():
    state = populated_state()
    analysis = state["analysis_result"]
    report = state["generated_report"]

    changed = set_dataset_state(
        state,
        signature="dataset-a",
        filename="a-renamed.csv",
        file_path="uploads/a-renamed.csv",
        dataframe={"rows": 999},
        detected_domain="saas",
        field_mapping={},
        data_overview={},
    )

    assert changed is False
    assert state["analysis_result"] is analysis
    assert state["generated_report"] is report
    assert state["uploaded_filename"] == "a.csv"



def test_dataset_upload_does_not_mutate_navigation_widget_state():
    state = {}
    init_session_state(state)
    state["current_page_selector"] = "overview"
    set_current_page(state, "overview")

    changed = set_dataset_state(
        state,
        signature="uploaded-retail",
        filename="retail.csv",
        file_path="uploads/retail.csv",
        dataframe={"rows": 2},
        detected_domain="retail",
        field_mapping={"sales": "sales"},
        data_overview={"row_count": 2},
    )

    assert changed is True
    assert state["current_page"] == "overview"
    assert state["current_page_selector"] == "overview"
    assert state["uploaded_df"] == {"rows": 2}

def test_new_dataset_invalidates_analysis_and_report():
    state = populated_state()

    changed = set_dataset_state(
        state,
        signature="dataset-b",
        filename="b.csv",
        file_path="uploads/b.csv",
        dataframe={"rows": 4},
        detected_domain="saas",
        field_mapping={"sales": None},
        data_overview={"row_count": 4},
    )

    assert changed is True
    assert state["uploaded_filename"] == "b.csv"
    assert state["analysis_result"] is None
    assert state["analysis_completed"] is False
    assert state["generated_report"] is None
    assert state["report_completed"] is False


def test_analysis_config_change_invalidates_analysis_and_report_only():
    state = populated_state()

    changed = set_analysis_config(state, "correlation")

    assert changed is True
    assert state["uploaded_file_signature"] == "dataset-a"
    assert state["uploaded_df"] == {"rows": 3}
    assert state["analysis_result"] is None
    assert state["generated_report"] is None
    assert state["analysis_config"] == "correlation"


def test_report_config_change_invalidates_only_report():
    state = populated_state()
    analysis = state["analysis_result"]

    changed = set_report_config(state, {"language": "Chinese"})

    assert changed is True
    assert state["analysis_result"] is analysis
    assert state["analysis_completed"] is True
    assert state["generated_report"] is None
    assert state["report_config"] == {"language": "Chinese"}


def test_navigation_initialization_preserves_existing_results_without_regeneration():
    state = populated_state()
    before = deepcopy(state)

    init_session_state(state)

    assert state == before
    assert state["generated_report"]["content"] == "report-a"


def test_reset_clears_workflow_state_and_rotates_uploader_key():
    state = populated_state()
    previous_version = state["upload_widget_version"]
    state["current_page"] = "AI ç®¡ç†æŠ¥å‘Š"

    reset_all_state(state)

    assert state["uploaded_df"] is None
    assert state["uploaded_file_signature"] is None
    assert state["analysis_result"] is None
    assert state["generated_report"] is None
    assert state["analysis_completed"] is False
    assert state["report_completed"] is False
    assert state["current_page"] == "overview"
    assert state["upload_widget_version"] == previous_version + 1


def test_report_reliability_metadata_persists_across_navigation_initialization():
    state = populated_state()
    init_session_state(state)
    assert state["report_metadata"]["provider_status"] == "rate_limited"
    assert state["report_metadata"]["fallback_used"] is True
    assert state["validation_status"]["report_validation_status"] == "not_run"
    assert state["validation_status"]["kpi_fidelity_status"] == "not_run"



def test_ui_language_defaults_to_english_and_survives_reset():
    state = {}
    init_session_state(state)
    assert state["ui_language"] == "en"

    state["ui_language_selector"] = "zh"  # Simulate the widget updating its own key.
    set_ui_language(state, "zh")
    state["uploaded_df"] = {"rows": 1}
    reset_all_state(state)

    assert state["ui_language"] == "zh"
    assert state["ui_language_selector"] == "zh"
    assert state["uploaded_df"] is None



def test_set_ui_language_does_not_mutate_widget_owned_selector_key():
    state = {}
    init_session_state(state)
    original_selector = state["ui_language_selector"]

    set_ui_language(state, "zh")

    assert state["ui_language"] == "zh"
    assert state["ui_language_selector"] == original_selector


def test_reset_all_state_does_not_rewrite_widget_owned_selector_key():
    state = populated_state()
    state["ui_language_selector"] = "zh"
    set_ui_language(state, "zh")

    reset_all_state(state)

    assert state["ui_language_selector"] == "zh"
    assert state["ui_language"] == "zh"

def test_ui_language_change_preserves_workflow_results():
    state = populated_state()
    analysis = state["analysis_result"]
    report = state["generated_report"]

    set_ui_language(state, "zh")

    assert state["analysis_result"] is analysis
    assert state["generated_report"] is report
    assert state["report_completed"] is True


def test_ui_language_rejects_unsupported_values():
    import pytest
    with pytest.raises(ValueError):
        set_ui_language({}, "fr")
