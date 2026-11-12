import clipboard_utils


def test_powershell_path_quotes_are_escaped(monkeypatch):
    captured = {}

    class Result:
        returncode = 0

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return Result()

    monkeypatch.setattr(clipboard_utils.subprocess, "run", fake_run)
    monkeypatch.setattr(clipboard_utils.os.path, "exists", lambda p: True)

    ok, _ = clipboard_utils.copy_file_to_clipboard(r"C:\Users\O'Brien\x.wav")
    assert ok
    assert captured["cmd"][-1] == r"Set-Clipboard -LiteralPath 'C:\Users\O''Brien\x.wav'"


def test_injection_payload_stays_inside_the_string(monkeypatch):
    captured = {}

    class Result:
        returncode = 0

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return Result()

    monkeypatch.setattr(clipboard_utils.subprocess, "run", fake_run)
    monkeypatch.setattr(clipboard_utils.os.path, "exists", lambda p: True)

    payload = r"C:\x'; Start-Process calc; '.wav"
    ok, _ = clipboard_utils.copy_file_to_clipboard(payload)
    assert ok
    assert captured["cmd"][-1] == "Set-Clipboard -LiteralPath '" + payload.replace("'", "''") + "'"