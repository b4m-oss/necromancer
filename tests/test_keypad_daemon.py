import sys


def install_fake_evdev_for_daemon():
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

        def capabilities(self):
            return {1: [1, 2, 3]}

        def read(self):
            return []

    class FakeEvent:
        def __init__(self, code):
            self.type = 1  # EV_KEY
            self.value = 1  # key down
            self.code = code

    fake_ecodes = type(
        "Ecodes",
        (),
        {
            "EV_KEY": 1,
            "KEY": {1: "KEY_KP1", 2: "KEY_KPENTER"},
            "KEY_KP1": 1,
            "KEY_KP2": 2,
        },
    )

    def fake_list_devices():
        return ["/dev/input/fake0"]

    fake = type(
        "Evdev",
        (),
        {
            "InputDevice": FakeInputDevice,
            "list_devices": fake_list_devices,
            "ecodes": fake_ecodes,
        },
    )

    sys.modules["evdev"] = fake


def test_keypad_daemon_handle_digit_and_enter(monkeypatch):
    install_fake_evdev_for_daemon()
    from app import keypad_daemon

    # Avoid touching /var/log/scanner in setup_logging
    monkeypatch.setattr(keypad_daemon.KeypadDaemon, "setup_logging", lambda self: None)

    daemon = keypad_daemon.KeypadDaemon(device_path="/dev/input/fake0")

    # Simulate that device is already set (skip find_keypad complexity)
    daemon.device = sys.modules["evdev"].InputDevice("/dev/input/fake0")

    called = {}

    def fake_execute_scan(key):
        called["key"] = key

    monkeypatch.setattr(daemon, "_execute_scan", fake_execute_scan)

    # Press digit and then Enter
    daemon._handle_key_press(1)  # KEY_KP1
    assert daemon.current_input == "1"

    daemon._handle_key_press(2)  # KEY_KPENTER
    # _execute_scan should have been called in a thread; emulate synchronous call
    assert called["key"] == "1"
