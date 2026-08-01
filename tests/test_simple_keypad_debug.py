import sys


def install_fake_evdev_for_debug():
    if "evdev" in sys.modules:
        return

    class FakeInputDevice:
        def __init__(self, path):
            self.path = path
            self.name = "Fake Device"

        def grab(self):
            pass

        def ungrab(self):
            pass

        def read(self):
            return []

    class FakeEcodes:
        EV_KEY = 1
        KEY = {}

    def fake_list_devices():
        return []

    fake = type(
        "Evdev",
        (),
        {
            "InputDevice": FakeInputDevice,
            "list_devices": fake_list_devices,
            "ecodes": FakeEcodes,
        },
    )

    sys.modules["evdev"] = fake


def test_simple_keypad_debug_no_devices(capsys):
    install_fake_evdev_for_debug()
    from app import simple_keypad_debug

    code = simple_keypad_debug.main()
    captured = capsys.readouterr()
    assert code == 1
    assert "No input devices found" in captured.out

