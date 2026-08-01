import sys
import types


def install_fake_evdev():
    """
    Provide a minimal fake evdev module so that keypad modules can be imported
    without real Linux input headers / devices.
    """
    if "evdev" in sys.modules:
        return

    class FakeInputDevice:
        def __init__(self, path):
            self.path = path
            self.name = "Fake Keypad"

        def grab(self):
            pass

        def ungrab(self):
            pass

        def read(self):
            return []

    fake_ecodes = types.SimpleNamespace(
        EV_KEY=1,
        KEY={},
        KEY_KP1=1,
        KEY_KPENTER=2,
    )

    fake = types.SimpleNamespace(
        InputDevice=FakeInputDevice,
        list_devices=lambda: [],
        ecodes=fake_ecodes,
    )
    sys.modules["evdev"] = fake


def test_load_scan_modes_default(monkeypatch, tmp_path):
    install_fake_evdev()
    from app import keypad_scanner, keypad_daemon
    # Point APP_DIR to a temporary directory without mode.json
    fake_app_dir = tmp_path
    monkeypatch.setattr(keypad_scanner, "APP_DIR", fake_app_dir)
    monkeypatch.setattr(keypad_daemon, "APP_DIR", fake_app_dir)

    modes_scanner = keypad_scanner.load_scan_modes()
    modes_daemon = keypad_daemon.load_scan_modes()

    assert modes_scanner == {"1": "diary", "2": "receipt", "3": "flyer"}
    assert modes_daemon == modes_scanner


def test_keypad_scanner_handle_digit_and_enter(monkeypatch, tmp_path):
    install_fake_evdev()
    from app import keypad_scanner

    # Fake mapping for evdev.ecodes.KEY
    fake_evdev = sys.modules["evdev"]
    fake_evdev.ecodes.KEY = {
        1: "KEY_KP1",
        2: "KEY_KPENTER",
    }

    monitor = keypad_scanner.KeypadMonitor()

    # Stub _execute_scan to avoid spawning real subprocess
    called = {}

    def fake_execute_scan(key):
        called["key"] = key

    monkeypatch.setattr(monitor, "_execute_scan", fake_execute_scan)

    # Simulate pressing "1"
    monitor._handle_key_press(1)
    assert monitor.current_input == "1"

    # Then Enter, which should trigger _execute_scan and clear buffer
    monitor._handle_key_press(2)
    assert called["key"] == "1"
    assert monitor.current_input == ""

