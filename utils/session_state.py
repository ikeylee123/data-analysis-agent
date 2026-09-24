from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any


INITIAL_PAGE = "overview"

DEFAULT_STATE = {
    "uploaded_df": None,
    "uploaded_filename": None,
    "uploaded_file_signature": None,
    "uploaded_file_path": None,
    "detected_domain": None,
    "field_mapping": None,
    "data_overview": None,
    "analysis_result": None,
    "analysis_config": None,
    "analysis_completed": False,
    "report_schema": None,
    "generated_report": None,
    "report_source": None,
    "validation_status": None,
    "report_metadata": None,
    "report_config": None,
    "report_completed": False,
    "current_page": INITIAL_PAGE,
    "current_page_selector": INITIAL_PAGE,
    "ui_language": "en",
    "ui_language_selector": "en",
    "upload_widget_version": 0,
}


def init_session_state(state: MutableMapping[str, Any]) -> None:
    for key, value in DEFAULT_STATE.items():
        if key != "current_page_selector":
            state.setdefault(key, value)
    legacy_pages = {
        "数据概览": "overview",
        "业务分析": "analytics",
        "AI 管理报告": "report",
    }
    state["current_page"] = legacy_pages.get(state["current_page"], state["current_page"])
    state.setdefault("current_page_selector", state["current_page"])


def set_current_page(state: MutableMapping[str, Any], page: str) -> None:
    if page not in {"overview", "analytics", "report"}:
        raise ValueError(f"Unsupported page: {page}")
    init_session_state(state)
    state["current_page"] = page


def set_ui_language(state: MutableMapping[str, Any], language: str) -> None:
    if language not in {"en", "zh"}:
        raise ValueError(f"Unsupported UI language: {language}")
    init_session_state(state)
    state["ui_language"] = language


def reset_report_state(state: MutableMapping[str, Any]) -> None:
    state["report_schema"] = None
    state["generated_report"] = None
    state["report_source"] = None
    state["validation_status"] = None
    state["report_metadata"] = None
    state["report_config"] = None
    state["report_completed"] = False


def reset_analysis_state(state: MutableMapping[str, Any]) -> None:
    state["analysis_result"] = None
    state["analysis_config"] = None
    state["analysis_completed"] = False
    reset_report_state(state)


def reset_all_state(state: MutableMapping[str, Any]) -> None:
    language = state.get("ui_language", "en")
    next_widget_version = int(state.get("upload_widget_version", 0)) + 1
    for key in list(state):
        if key != "ui_language_selector":
            del state[key]
    for key, value in DEFAULT_STATE.items():
        if key != "ui_language_selector":
            state[key] = value
    state["upload_widget_version"] = next_widget_version
    state["current_page"] = INITIAL_PAGE
    state["ui_language"] = language


def set_dataset_state(state: MutableMapping[str, Any], *, signature: str, filename: str, file_path: str, dataframe: Any, detected_domain: str, field_mapping: dict, data_overview: dict) -> bool:
    init_session_state(state)
    if state["uploaded_file_signature"] == signature:
        return False
    reset_analysis_state(state)
    state["uploaded_file_signature"] = signature
    state["uploaded_filename"] = filename
    state["uploaded_file_path"] = file_path
    state["uploaded_df"] = dataframe
    state["detected_domain"] = detected_domain
    state["field_mapping"] = field_mapping
    state["data_overview"] = data_overview
    return True


def set_analysis_config(state: MutableMapping[str, Any], config: str) -> bool:
    init_session_state(state)
    previous = state["analysis_config"]
    changed = previous is not None and previous != config
    if changed:
        reset_analysis_state(state)
    state["analysis_config"] = config
    return changed


def store_analysis_result(state: MutableMapping[str, Any], result: dict, config: str) -> None:
    reset_report_state(state)
    state["analysis_result"] = result
    state["analysis_config"] = config
    state["analysis_completed"] = True


def set_report_config(state: MutableMapping[str, Any], config: dict) -> bool:
    init_session_state(state)
    previous = state["report_config"]
    changed = previous is not None and previous != config
    if changed:
        reset_report_state(state)
    state["report_config"] = dict(config)
    return changed


def store_report_result(state: MutableMapping[str, Any], *, report: dict, report_schema: dict, config: dict) -> None:
    state["report_schema"] = report_schema
    state["generated_report"] = report
    state["report_source"] = report.get("source")
    state["validation_status"] = {
        "report_validation_status": report.get("report_validation_status", "not_run"),
        "kpi_fidelity_status": report.get("kpi_fidelity_status", "not_run"),
        "validation_errors": list(report.get("validation_errors") or []),
        "repair_errors": list(report.get("repair_errors") or []),
    }
    state["report_metadata"] = {
        "provider_status": report.get("provider_status", "not_applicable"),
        "fallback_used": bool(report.get("fallback_used")),
        "fallback_reason": report.get("fallback_reason"),
        "repair_attempted": bool(report.get("repair_attempted")),
    }
    state["report_config"] = dict(config)
    state["report_completed"] = True
