from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def radio_by_key(app: AppTest, key: str):
    return next(widget for widget in app.radio if widget.key == key)


def test_language_selection_survives_sidebar_navigation_reruns():
    app = AppTest.from_file(str(APP_PATH), default_timeout=10).run()
    assert not app.exception

    app = radio_by_key(app, "ui_language_selector").set_value("zh").run()
    assert not app.exception
    assert radio_by_key(app, "ui_language_selector").value == "zh"
    assert app.session_state["ui_language"] == "zh"

    for page in ("analytics", "overview", "report"):
        app = radio_by_key(app, "current_page_selector").set_value(page).run()
        assert not app.exception
        assert radio_by_key(app, "ui_language_selector").value == "zh"
        assert app.session_state["ui_language"] == "zh"
        assert app.session_state["current_page"] == page

    app = radio_by_key(app, "ui_language_selector").set_value("en").run()
    assert not app.exception
    for page in ("overview", "analytics", "report"):
        app = radio_by_key(app, "current_page_selector").set_value(page).run()
        assert not app.exception
        assert radio_by_key(app, "ui_language_selector").value == "en"
        assert app.session_state["ui_language"] == "en"
        assert app.session_state["current_page"] == page
