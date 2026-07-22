import os
import ctypes
import ctypes.wintypes
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSize, Qt, QThread, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from core.database import Database
from ui.finger_wizard import FingerWizard, HotkeyEdit
from ui.i18n import tr
from ui.main_window import MainWindow
from ui.theme import THEME
from ui.tray import FingerprintTray


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_wizard_picker_and_registry_data_integrate_without_resizing(tmp_path):
    app = _app()
    with Database(tmp_path / "ui.sqlite3") as db:
        wizard = FingerWizard(db, lang="uk")
        wizard.stack.setCurrentIndex(1)
        wizard._sync_window_size()
        original_size = wizard.size()

        wizard.action_type.show_popup()
        app.processEvents()
        assert wizard.size() == original_size
        wizard.action_type.popup.hide()

        wizard.action_type.setCurrentIndex(wizard.action_type.findData("sleep"))
        wizard._add_action()

        assert wizard.actions[0]["command_type"] == "sleep"
        assert wizard.actions[0]["command_data"] == {
            "schema_version": 1,
        }


def test_data_free_action_uses_compact_layout_after_value_action(tmp_path):
    app = _app()
    with Database(tmp_path / "compact.sqlite3") as db:
        wizard = FingerWizard(db, lang="uk")
        wizard.stack.setCurrentIndex(1)
        wizard.action_type.setCurrentIndex(wizard.action_type.findData("open_url"))
        wizard.action_value.setText("https://example.com")
        wizard._add_action()
        assert wizard.height() == 643

        wizard.action_type.setCurrentIndex(wizard.action_type.findData("sleep"))
        app.processEvents()

        assert wizard.height() == 560


def test_wizard_builds_delay_and_normalizes_quick_timer_units(tmp_path):
    app = _app()
    with Database(tmp_path / "timer-wizard.sqlite3") as db:
        wizard = FingerWizard(db, lang="en")
        wizard.stack.setCurrentIndex(1)

        wizard.action_type.setCurrentIndex(wizard.action_type.findData("delay"))
        wizard.delay_value.setText("1500")
        wizard.delay_unit.setCurrentIndex(wizard.delay_unit.findData("milliseconds"))
        wizard._add_action()
        assert wizard.actions[0]["command_data"]["duration_ms"] == 1_500

        wizard.action_type.setCurrentIndex(wizard.action_type.findData("quick_timer"))
        wizard.timer_value.setText("120")
        wizard.timer_unit.setCurrentIndex(wizard.timer_unit.findData("minutes"))
        wizard.timer_message.setText("Tea")
        wizard._add_action()

        timer_data = wizard.actions[1]["command_data"]
        assert timer_data["duration_ms"] == 7_200_000
        assert timer_data["message"] == "Tea"
        assert wizard.timer_value.text() == "2"
        assert wizard.timer_unit.currentData() == "hours"

        wizard.show()
        app.processEvents()
        card_bottom = (
            wizard.action_card.geometry().y()
            + wizard.action_card.geometry().height()
        )
        title_bottom = (
            wizard.actions_title.geometry().y()
            + wizard.actions_title.geometry().height()
        )
        assert wizard.actions_title.geometry().top() - card_bottom >= 8
        assert wizard.actions_scroll.geometry().top() - title_bottom >= 8
        assert "background: transparent" in wizard.timer_editor.styleSheet()
        sound_bottom = (
            wizard.timer_sound.geometry().y()
            + wizard.timer_sound.geometry().height()
        )
        assert sound_bottom <= wizard.timer_editor.height()
        wizard.deleteLater()
        app.processEvents()


def test_duration_editor_limits_follow_selected_units(tmp_path):
    app = _app()
    with Database(tmp_path / "duration-limits.sqlite3") as db:
        wizard = FingerWizard(db, lang="en")
        wizard.delay_unit.setCurrentIndex(wizard.delay_unit.findData("hours"))
        assert wizard.delay_value.validator().top() == 24
        wizard.timer_unit.setCurrentIndex(wizard.timer_unit.findData("hours"))
        assert wizard.timer_value.validator().top() == 720
        wizard.deleteLater()
        app.processEvents()


def test_wizard_builds_and_edits_volume_change_without_resizing(tmp_path):
    app = _app()
    with Database(tmp_path / "volume-wizard.sqlite3") as db:
        wizard = FingerWizard(db, lang="en")
        wizard.stack.setCurrentIndex(1)
        wizard.action_type.setCurrentIndex(
            wizard.action_type.findData("change_volume")
        )
        wizard.volume_amount.setText("25")
        wizard.volume_direction.setCurrentIndex(
            wizard.volume_direction.findData("decrease")
        )
        wizard._add_action()

        assert wizard.actions == [{
            "command_type": "change_volume",
            "command_data": {
                "schema_version": 1,
                "direction": "decrease",
                "amount_percent": 25,
            },
        }]
        assert wizard.height() == 643

        wizard._edit_action(0)
        assert wizard.volume_amount.text() == "25"
        assert wizard.volume_direction.currentData() == "decrease"
        wizard.deleteLater()
        app.processEvents()


def test_hotkey_edit_accepts_single_and_modifier_keys():
    app = _app()
    hotkey = HotkeyEdit(capture_only=True)
    hotkey.show()

    QTest.keyClick(hotkey, Qt.Key.Key_F8)
    assert hotkey.text() == "f8"

    QTest.keyClick(hotkey, Qt.Key.Key_A)
    assert hotkey.text() == "a"

    QTest.keyPress(hotkey, Qt.Key.Key_Control)
    assert hotkey.text() == "ctrl"
    QTest.keyRelease(hotkey, Qt.Key.Key_Control)

    QTest.keyClick(hotkey, Qt.Key.Key_Plus)
    assert hotkey.text() == "plus"

    hotkey.deleteLater()
    app.processEvents()


def test_edit_launch_app_keeps_file_picker_and_stable_controls_width(tmp_path):
    app = _app()
    with Database(tmp_path / "edit-launch-app.sqlite3") as db:
        wizard = FingerWizard(db, lang="en")
        wizard.stack.setCurrentIndex(1)
        wizard.actions = [
            {
                "command_type": "launch_app",
                "command_data": {
                    "schema_version": 1,
                    "path": "C:/Windows/System32/calc.exe",
                    "args": "",
                },
            }
        ]

        wizard._edit_action(0)

        assert not wizard.browse.isHidden()
        assert wizard.browse.text() == "Choose file"
        assert wizard.add_action_btn.text() == "Update action"
        assert wizard.browse.width() + wizard.controls_row.spacing() + wizard.add_action_btn.width() == 476

        with patch(
            "ui.finger_wizard.QFileDialog.getOpenFileName",
            return_value=("C:/Program Files/App/app.exe", ""),
        ):
            wizard.browse.click()
        assert wizard.action_value.text() == "C:/Program Files/App/app.exe"
        wizard.deleteLater()
        app.processEvents()


def test_main_window_formats_registry_actions(tmp_path):
    app = _app()
    with Database(tmp_path / "main.sqlite3") as db:
        finger_id = db.save_finger("guid", 3, "Finger")
        db.save_command(finger_id, "open_url", {"url": "https://example.com"})
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.fingers_table.item(0, 2).text()
        assert window.fingers_table.item(0, 3).text() == "https://example.com"
        assert not window.autostart.isChecked()
        assert window._current_autostart_mode() == "disabled"
        for index in range(12):
            window._append_activity(f"Action {index}")
        assert len(window._activity_entries) == 10
        assert window._activity_entries[0][1] == "Action 11"
        assert window._activity_entries[-1][1] == "Action 2"
        assert window.activity_log_card.minimumHeight() == 406
        assert window._theme_buttons[0].toolTip() == "Світла"
        window.lang = "en"
        window.retranslate()
        assert window._theme_buttons[0].toolTip() == "Light"
        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_timer_countdown_replaces_only_the_running_timer_summary(tmp_path):
    app = _app()
    with Database(tmp_path / "countdown.sqlite3") as db:
        finger_id = db.save_finger("guid", 3, "Finger")
        timer_id = db.save_command(
            finger_id,
            "quick_timer",
            {"duration_ms": 60_000, "message": "Tea", "sound_path": ""},
        )
        db.save_command(finger_id, "lock_screen", {})
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        window.timer_manager._schedule({
            "duration_ms": 60_000,
            "message": "Tea",
            "command_id": timer_id,
            "finger_id": finger_id,
        })
        app.processEvents()
        command_text = window.fingers_table.item(0, 3).text()
        assert "01:00" in command_text
        assert tr(window.lang, "lock_screen") in command_text

        window.timer_manager.cancel_all()
        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_activity_toggle_disables_the_complete_finger_sequence(tmp_path):
    app = _app()
    with Database(tmp_path / "sequence-toggle.sqlite3") as db:
        finger_id = db.save_finger("guid", 3, "Finger")
        db.save_command(finger_id, "delay", {"duration_ms": 1_000})
        db.save_command(finger_id, "open_url", {"url": "https://example.com"})
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        window._on_fingers_cell_clicked(0, 4)

        assert db.get_commands("guid", 3) == []
        assert [
            command["enabled"]
            for command in db.get_commands_by_finger_id(finger_id)
        ] == [False, False]
        assert window.fingers_table.item(0, 4).data(
            Qt.ItemDataRole.UserRole + 1
        ) is False

        window._on_fingers_cell_clicked(0, 4)

        assert len(db.get_commands("guid", 3)) == 2
        assert all(
            command["enabled"]
            for command in db.get_commands_by_finger_id(finger_id)
        )

        window.scan_prompt.hide()
        window.timer_notification.hide()
        window.deleteLater()
        app.processEvents()


def test_main_window_delete_removes_selected_finger_and_its_actions(tmp_path):
    app = _app()
    with Database(tmp_path / "main-delete.sqlite3") as db:
        deleted_id = db.save_finger("guid-1", 3, "Delete me")
        retained_id = db.save_finger("guid-2", 4, "Keep me")
        db.save_command(deleted_id, "minimize_all", {})
        db.save_command(deleted_id, "open_url", {"url": "https://example.com"})
        db.save_command(retained_id, "lock_screen", {})
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        window.fingers_table.selectRow(0)
        window.delete_selected_finger()

        assert db.get_commands_by_finger_id(deleted_id) == []
        assert [finger["id"] for finger in db.list_fingers()] == [retained_id]
        assert window.fingers_table.rowCount() == 1
        assert window.fingers_table.item(0, 1).data(
            Qt.ItemDataRole.UserRole
        ) == retained_id

        window.scan_prompt.hide()
        window.timer_notification.hide()
        window.deleteLater()
        app.processEvents()


def test_timer_completion_shows_a_separate_localized_notification(tmp_path):
    app = _app()
    with Database(tmp_path / "timer-notification.sqlite3") as db, \
            patch("keyboard.add_hotkey", return_value=object()):
        window = MainWindow(db)
        timer = {"message": "Tea", "duration_ms": 1_000}

        window._on_timer_finished(timer)
        app.processEvents()

        assert window.timer_notification.isVisible()
        assert window.timer_notification.title.text() == tr(window.lang, "timer_finished")
        assert window.timer_notification.message.text() == "Tea"
        assert window.timer_notification.progress.isHidden()

        window.timer_notification.hide()
        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_scan_match_completes_prompt_before_action_sequence_finishes(tmp_path):
    app = _app()
    with Database(tmp_path / "scan-match.sqlite3") as db, \
            patch("keyboard.add_hotkey", return_value=object()):
        window = MainWindow(db)
        window.scan_prompt.show_prompt(window.lang)
        window.scan_prompt.progress.setValue(360)

        window.on_scan_matched("Finger")
        app.processEvents()

        assert window.scan_prompt.progress.value() == 360
        assert window.scan_prompt.message.text() == tr(window.lang, "scan_recognized")
        assert window.scan_prompt._close_timer.isActive()

        window.scan_prompt.hide()
        window.timer_notification.hide()
        window.deleteLater()
        app.processEvents()


def test_pause_and_taskbar_toggle_are_reversible(tmp_path):
    app = _app()
    with Database(tmp_path / "pause-toggle.sqlite3") as db, \
            patch("keyboard.add_hotkey", return_value="handle") as add_hotkey, \
            patch("keyboard.remove_hotkey") as remove_hotkey:
        window = MainWindow(db)
        window.set_hotkey_paused(True)
        assert window.hotkey_paused
        assert window.hotkey_handle is None
        assert window.monitor_status.text() == tr(window.lang, "hotkey_paused")
        remove_hotkey.assert_called_with("handle")

        window.set_hotkey_paused(False)
        assert not window.hotkey_paused
        assert window.hotkey_handle == "handle"
        assert add_hotkey.call_count >= 2

        assert window._is_valid_activation_hotkey("a")
        assert window._is_valid_activation_hotkey("f8")
        assert window._is_valid_activation_hotkey("ctrl")
        assert window._is_valid_activation_hotkey("ctrl+\\")
        assert not window._is_valid_activation_hotkey("")

        add_hotkey.reset_mock()
        window.activation_hotkey_input.setText("f8")
        window.save_activation_hotkey()
        add_hotkey.assert_called_once()
        assert add_hotkey.call_args.args[0] == "f8"
        assert db.get_setting("activation_hotkey") == "f8"

        window.show()
        app.processEvents()
        window.toggle_taskbar_visibility()
        assert window.isMinimized()
        window.toggle_taskbar_visibility()
        assert not window.isMinimized()

        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_native_windows_message_passthrough_is_safe(tmp_path):
    app = _app()
    with Database(tmp_path / "native-event.sqlite3") as db, \
            patch("keyboard.add_hotkey", return_value=object()):
        window = MainWindow(db)
        message = ctypes.wintypes.MSG()
        message.message = 0

        assert window.nativeEvent(
            b"windows_generic_MSG",
            ctypes.addressof(message),
        ) == (False, 0)

        flags = window.windowFlags()
        assert flags & Qt.WindowType.WindowMinimizeButtonHint
        assert flags & Qt.WindowType.WindowSystemMenuHint

        message.message = 0x0112  # WM_SYSCOMMAND
        message.wParam = 0xF020  # SC_MINIMIZE
        with patch.object(QTimer, "singleShot") as single_shot:
            assert window.nativeEvent(
                b"windows_generic_MSG",
                ctypes.addressof(message),
            ) == (True, 0)
        single_shot.assert_called_once()
        assert single_shot.call_args.args[1] == window.animate_minimize

        window._native_minimize_passthrough = True
        assert window.nativeEvent(
            b"windows_generic_MSG",
            ctypes.addressof(message),
        ) == (False, 0)

        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_prepare_for_exit_stops_an_active_scan_thread(tmp_path):
    app = _app()
    with Database(tmp_path / "thread-cleanup.sqlite3") as db, \
            patch("keyboard.add_hotkey", return_value=object()), \
            patch("keyboard.remove_hotkey"):
        window = MainWindow(db)
        worker = Mock()
        thread = QThread(window)
        window.scan_worker = worker
        window.scan_thread = thread
        thread.start()
        app.processEvents()

        window.prepare_for_exit()

        worker.cancel.assert_called_once_with()
        assert not thread.isRunning()
        assert window.scan_thread is None
        assert window.scan_worker is None

        window.deleteLater()
        app.processEvents()


def test_tray_exposes_localized_pause_and_live_timer_menu():
    app = _app()
    tray = FingerprintTray(QIcon(), lang="en")
    from services.timer_manager import TimerManager

    manager = TimerManager()
    tray.bind_timer_manager(manager)
    tray.set_paused(True)
    assert tray.pause_action.isChecked()
    assert tray.pause_action.text() == tr("en", "resume_hotkey")

    manager._schedule({"duration_ms": 60_000, "message": "Tea"})
    app.processEvents()
    assert len(tray._timer_actions) == 1
    assert "Tea" in next(iter(tray._timer_actions.values())).text()
    assert "01:00" in next(iter(tray._timer_actions.values())).text()

    manager.cancel_all()
    tray.deleteLater()
    manager.deleteLater()
    app.processEvents()


def test_main_window_applies_and_switches_dark_theme(tmp_path):
    app = _app()
    with Database(tmp_path / "dark-main.sqlite3") as db:
        db.set_setting("theme", "dark")
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.theme_key == "dark"
        assert THEME.key == "dark"
        assert window._theme_buttons[3].diameter() == 38
        assert "#243044" in window.styleSheet()

        window.change_theme_key("light")
        assert THEME.key == "light"
        assert db.get_setting("theme") == "light"
        assert "#F5F5F7" in window.styleSheet()

        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_main_window_applies_onyx_theme_and_wizard_controls(tmp_path):
    app = _app()
    with Database(tmp_path / "onyx-main.sqlite3") as db:
        db.set_setting("theme", "onyx")
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.theme_key == "onyx"
        assert THEME.key == "onyx"
        assert window._theme_buttons[1].diameter() == 38
        assert "#1A1A1D" in window.styleSheet()
        assert THEME.settings_surface == "#1E1E22"
        assert window.autostart_mode_combo.property("role") == "settingsInput"
        assert window.activity_log_card.property("role") == "statusLog"
        assert window._theme_buttons[0]._outline_color().name() == "#111113"
        assert window._theme_buttons[1]._outline_color().name() == THEME.primary.lower()
        assert window._theme_buttons[2]._outline_color() is None

        wizard = FingerWizard(db, window, lang="en")
        wizard.stack.setCurrentIndex(1)
        wizard.action_type.setCurrentIndex(wizard.action_type.findData("sleep"))
        wizard._add_action()
        action_row = wizard.actions_layout.itemAt(0).widget()
        action_buttons = action_row.findChildren(type(wizard.add_action_btn))
        assert {button.property("kind") for button in action_buttons} == {"actionSecondary"}
        wizard.stack.setCurrentIndex(0)
        wizard.scanned = False
        wizard._sync_nav()
        assert wizard.next_btn.property("iconName") == "inactive_next"

        wizard.deleteLater()
        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_main_window_applies_graphite_theme_and_wizard_surfaces(tmp_path):
    app = _app()
    with Database(tmp_path / "graphite-main.sqlite3") as db:
        db.set_setting("theme", "graphite")
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.theme_key == "graphite"
        assert THEME.key == "graphite"
        assert window._theme_buttons[2].diameter() == 38
        assert "#323339" in window.styleSheet()
        assert window.appearance_card.property("role") == "settingsCard"

        wizard = FingerWizard(db, window, lang="en")
        assert wizard.capture_icon.parent().property("role") == "captureCard"
        assert wizard.done_card.property("role") == "doneCard"
        assert "#28292F" in wizard.styleSheet()
        assert "#3C3D46" in wizard.styleSheet()

        wizard.deleteLater()
        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_main_window_applies_blue_gradient_theme_and_wizard_canvas(tmp_path):
    app = _app()
    with Database(tmp_path / "blue-gradient-main.sqlite3") as db:
        db.set_setting("theme", "blue_gradient")
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.theme_key == "blue_gradient"
        assert THEME.key == "blue_gradient"
        assert window._theme_buttons[5].diameter() == 38
        assert window.centralWidget().property("role") == "canvas"
        assert window.stack.property("role") == "canvasStack"
        window.show()
        app.processEvents()
        assert window.stack.y() == window.tab_bar.height()
        assert window.tab_bar.layout().contentsMargins().left() == 0
        assert window.fingers_table.columnWidth(1) == 160
        assert window.fingers_table.columnWidth(2) == 180
        assert "qlineargradient" in window.styleSheet()
        assert "#1E3A8A" in window.styleSheet()
        assert "rgba(255,255,255,20)" in window.styleSheet()

        wizard = FingerWizard(db, window, lang="en")
        assert wizard.body_layout.parentWidget().property("role") == "canvas"
        assert wizard.stack.property("role") == "canvasStack"
        assert "#2563EB" in wizard.styleSheet()
        assert "#1E40AF" in wizard.styleSheet()
        assert wizard.next_btn.layoutDirection() == Qt.LayoutDirection.RightToLeft

        wizard.stack.setCurrentIndex(wizard.stack.count() - 1)
        wizard._sync_nav()
        assert wizard.next_btn.layoutDirection() == Qt.LayoutDirection.LeftToRight
        assert window.support_icon.size() == QSize(28, 28)
        assert THEME.canvas_brush in window.scan_prompt.styleSheet()

        wizard.deleteLater()
        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_language_change_retranslates_dynamic_text_and_fits_buttons(tmp_path):
    app = _app()
    with Database(tmp_path / "translations.sqlite3") as db:
        db.set_setting("language", "fr")
        db.set_setting("theme", "dark")
        with patch("keyboard.add_hotkey", return_value=object()):
            window = MainWindow(db)

        assert window.support_text.text().startswith("Si l’application")
        assert window.monitor_status.text().startswith("En attente")
        window._show_update_status("update_no_releases", 100_000)
        assert window.update_status.text() == "Aucune version n’est encore publiée sur GitHub."

        window.lang = "es"
        window.copy_status.setText("Copied")
        window.retranslate()
        assert window.support_text.text().startswith("Si la aplicación")
        assert window.monitor_status.text().startswith("Esperando")
        assert window.update_status.text() == "Todavía no hay versiones publicadas en GitHub."
        assert window.copy_status.text() == "Copiado"

        window.lang = "ru"
        window.retranslate()
        window._activity_entries.clear()
        window.on_scan_action_result({
            "command_type": "open_url",
            "status": "success",
            "message": "https://example.com",
        })
        assert window._activity_entries[0][1].startswith("Выполнено:")
        for button in (
            window.add_btn,
            window.edit_btn,
            window.delete_btn,
            window.activation_hotkey_save,
            window.check_updates_btn,
            window.copy_trc20_btn,
        ):
            assert button.width() >= button.sizeHint().width()

        window.show()
        app.processEvents()
        assert 0 < window.stack.y() < window.tab_bar.height()
        assert window.tab_bar.height() - window.stack.y() == window.tabbed_content.OVERLAP

        window.scan_prompt.progress.setValue(400)
        window.scan_prompt.set_result("success")
        assert window.scan_prompt.progress.value() == 400
        short_prompt_height = window.scan_prompt.height()
        window.scan_prompt.set_result(tr("ru", "unknown_hello"))
        assert window.scan_prompt.message.height() > 40
        assert window.scan_prompt.height() > short_prompt_height
        window.scan_prompt.set_result("Very long diagnostic message " * 200)
        assert window.scan_prompt.height() <= window.scan_prompt.MAX_HEIGHT
        assert window.scan_prompt.layout().minimumSize().height() <= window.scan_prompt.MAX_HEIGHT
        with patch("ui.scan_prompt.monotonic", side_effect=(100.0, 107.5)):
            window.scan_prompt._start_progress()
            window.scan_prompt._progress_timer.stop()
            window.scan_prompt._advance_progress()
        assert window.scan_prompt.progress.value() == window.scan_prompt.PROGRESS_MAX // 2
        window.scan_prompt.set_result("timeout", complete=True)
        QTest.qWait(300)
        assert window.scan_prompt.progress.value() == window.scan_prompt.PROGRESS_MAX

        window.scan_prompt.hide()
        window.deleteLater()
        app.processEvents()


def test_done_step_keeps_icon_title_and_message_separate(tmp_path):
    app = _app()
    with Database(tmp_path / "done-layout.sqlite3") as db:
        wizard = FingerWizard(db, lang="ru")
        wizard.stack.setCurrentIndex(2)
        wizard.done_label.setText(
            "Для пальца <b>Неуказанный палец 2</b> назначено действие: "
            "<span style='color:#1D74F7'>Заблокировать экран</span>"
        )
        wizard.show()
        app.processEvents()

        assert wizard.done_card.height() == 208
        assert wizard.done_icon.geometry().bottom() < wizard.done_title.geometry().top()
        assert wizard.done_title.geometry().bottom() < wizard.done_label.geometry().top()

        wizard.deleteLater()
        app.processEvents()


def test_failed_capture_keeps_scan_icon_size(tmp_path):
    app = _app()
    with Database(tmp_path / "capture-icon.sqlite3") as db:
        wizard = FingerWizard(db, lang="en")
        wizard.show()
        app.processEvents()

        original_size = wizard.capture_icon.size()
        original_pixmap_size = wizard.capture_icon.pixmap().size()
        wizard._on_capture_failed(
            "unknown_finger",
            "This finger is not enrolled in Windows Hello. Open Windows Settings, "
            "add this finger, then return here.",
        )
        app.processEvents()

        assert wizard.capture_icon.size() == original_size
        assert wizard.capture_icon.size().width() == 72
        assert wizard.capture_icon.size().height() == 72
        assert wizard.capture_icon.pixmap().size() == original_pixmap_size

        wizard.deleteLater()
        app.processEvents()
