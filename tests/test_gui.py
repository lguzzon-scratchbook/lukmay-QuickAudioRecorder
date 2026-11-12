import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import gui


@pytest.fixture
def tray(fake_sc, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gui, "data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(gui, "CONFIG_FILE", str(tmp_path / "settings.json"))
    monkeypatch.setattr(gui, "sc", fake_sc)
    monkeypatch.setattr(gui, "get_devices", lambda include_loopback=False: [{"id": "Fake Mic", "name": "Fake Mic"}])
    app = QApplication.instance() or QApplication([])
    t = gui.TrayApplication(app)
    t.settings_window.lbl_folder.setText(str(tmp_path / "out"))
    t.settings_window.combo_fmt.setCurrentText("WAV")
    yield t
    if t.recorder:
        t.recorder.stop()
        t.recorder.join(10)


def wait_for(cond, timeout=15):
    app = QApplication.instance()
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_record_and_stop_from_tray(tray, tmp_path):
    tray.start_recording("mic")
    assert tray.action_stop.isEnabled()
    time.sleep(0.3)
    tray.stop_recording()
    assert wait_for(lambda: tray.recorder is None)
    assert not tray.action_stop.isEnabled()
    assert len(os.listdir(tmp_path / "out")) == 1


def test_stop_twice_is_harmless(tray):
    tray.start_recording("mic")
    time.sleep(0.2)
    tray.stop_recording()
    tray.stop_recording()
    assert wait_for(lambda: tray.recorder is None)


def test_hotkey_from_other_thread_toggles_recording(tray):
    import threading
    # keyboard fires hotkeys on its own thread
    threading.Thread(target=lambda: tray.signals.hotkey.emit("mic")).start()
    assert wait_for(lambda: tray.recorder is not None and tray.recorder.is_alive())
    time.sleep(0.2)
    threading.Thread(target=lambda: tray.signals.hotkey.emit("mic")).start()
    assert wait_for(lambda: tray.recorder is None)


def test_hotkey_field_captures_alt_shift_letter(tray):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    edit = tray.settings_window.hk_mic
    tray.settings_window.show()
    edit.setFocus()
    QTest.keyClick(edit, Qt.Key.Key_R, Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier)
    assert edit.text() == "shift+alt+r"


def test_notifications_can_be_turned_off_but_errors_still_show(tray, monkeypatch):
    shown = []
    monkeypatch.setattr(tray.tray_icon, "showMessage", lambda title, *a: shown.append(title))
    tray.settings_window.chk_notifications.setChecked(False)
    tray.start_recording("mic")
    time.sleep(0.2)
    tray.stop_recording()
    assert wait_for(lambda: tray.recorder is None)
    tray.on_recording_finished("", "boom")
    assert shown == ["Error"]


def test_tooltip_shows_elapsed_time(tray):
    tray.start_recording("mic")
    tray.rec_started -= 75
    tray.on_recording_tick()
    assert tray.tray_icon.toolTip() == "Recording (mic) 01:15"


def test_auto_stop(tray):
    tray.settings_window.spin_auto_stop.setValue(1)
    tray.start_recording("mic")
    time.sleep(0.2)
    tray.rec_started -= 59
    tray.on_recording_tick()
    assert tray.recorder.is_alive()
    tray.rec_started -= 1
    tray.on_recording_tick()
    assert wait_for(lambda: tray.recorder is None)


def test_tray_shows_saving_progress(tray):
    tray.start_recording("mic")
    time.sleep(0.2)
    tray.stop_recording()
    QApplication.instance().processEvents()
    assert tray.tray_icon.toolTip().startswith("Saving recording...")
    assert wait_for(lambda: tray.recorder is None)
    assert tray.tray_icon.toolTip() == "Simple Audio Recorder (Idle)"
    assert tray.action_stop.text() == "Stop Recording"


def test_saving_progress_updates_tooltip_and_menu(tray):
    tray.on_save_progress(0.42)
    assert tray.tray_icon.toolTip() == "Saving recording... 42%"
    assert tray.action_stop.text() == "Saving... 42%"


def test_hotkey_field_rejects_bare_letter(tray):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    edit = tray.settings_window.hk_mic
    tray.settings_window.show()
    edit.setFocus()
    QTest.keyClick(edit, Qt.Key.Key_A)
    assert edit.text() == ""
    QTest.keyClick(edit, Qt.Key.Key_F5)
    assert edit.text() == "f5"


@pytest.mark.parametrize("seq,ok", [
    ("a", False), ("space", False), ("f5", True),
    ("ctrl+alt+r", True), ("shift+f1", True),
])
def test_hotkey_validation(seq, ok):
    assert gui.hotkey_ok(seq) is ok


def test_exit_waits_for_recording_to_save(tray, tmp_path, monkeypatch):
    quits = []
    monkeypatch.setattr(tray.app, "quit", lambda: quits.append(1))
    tray.start_recording("mic")
    time.sleep(0.3)
    tray.exit_app()
    assert quits == [], "exit must not quit before the recording is saved"
    assert wait_for(lambda: tray.recorder is None)
    assert len(os.listdir(tmp_path / "out")) == 1
    assert quits == [1]


def test_settings_migrate_from_old_cwd_location(tray, tmp_path, monkeypatch):
    import json
    (tmp_path / "new").mkdir()
    new_config = tmp_path / "new" / "settings.json"
    monkeypatch.setattr(gui, "CONFIG_FILE", str(new_config))
    (tmp_path / "settings.json").write_text(json.dumps({"format": "FLAC"}))
    tray.settings_window.load_settings()
    assert tray.settings_window.combo_fmt.currentText() == "FLAC"
    assert new_config.exists(), "migration must write the new location"
    assert not (tmp_path / "settings.json").exists(), "legacy file must not be trusted twice"
