import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QWidget

from ui.action_picker import HEADER_ROLE, ActionPicker, _ActionPickerDelegate
from ui.i18n import LANGUAGES


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_picker_contains_all_actions_and_searches_keywords():
    app = _app()
    picker = ActionPicker("uk")

    assert len(picker.filtered_action_ids()) == 8
    picker.set_search_text("powershell")
    assert picker.filtered_action_ids() == ["shell"]
    picker.set_search_text("буфер")
    assert picker.filtered_action_ids() == ["paste_text"]
    assert app is not None


def test_picker_keeps_selected_action_when_language_changes():
    app = _app()
    picker = ActionPicker("uk")
    picker.setCurrentIndex(picker.findData("shutdown"))

    for lang in LANGUAGES:
        picker.set_language(lang)
        assert picker.currentData() == "shutdown"
        assert picker.display.text()
    assert app is not None


def test_picker_searches_keywords_from_every_supported_language():
    app = _app()
    picker = ActionPicker("en")
    queries = {
        "відкрити": "launch_app",
        "открыть": "launch_app",
        "fichier": "launch_app",
        "archivo": "launch_app",
        "raccourci": "hotkey",
        "teclado": "hotkey",
        "portapapeles": "paste_text",
    }

    for query, expected in queries.items():
        picker.set_search_text(query)
        assert expected in picker.filtered_action_ids()
    assert app is not None


def test_popup_does_not_change_parent_geometry():
    app = _app()
    parent = QWidget()
    parent.resize(540, 560)
    picker = ActionPicker("en", parent)
    picker.setGeometry(20, 20, 476, 42)
    original_geometry = parent.geometry()

    picker.show_popup()
    app.processEvents()

    assert parent.geometry() == original_geometry
    assert picker.popup.height() <= 360
    picker.popup.hide()


def test_category_headers_use_centered_separator_delegate():
    app = _app()
    picker = ActionPicker("en")

    assert isinstance(picker.list_view.itemDelegate(), _ActionPickerDelegate)
    headers = [
        picker.model.item(row)
        for row in range(picker.model.rowCount())
        if bool(picker.model.item(row).data(HEADER_ROLE))
    ]
    assert [header.text() for header in headers] == [
        "BASIC",
        "KEYBOARD AND MACROS",
        "WINDOWS SYSTEM",
    ]
    assert all(header.flags() == Qt.ItemFlag.NoItemFlags for header in headers)
    assert app is not None
