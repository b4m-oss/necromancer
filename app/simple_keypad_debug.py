#!/usr/bin/env python3
import evdev
import time
import select
import sys

def main():  # pragma: no cover
    """Main program for debugging numeric keypad input."""
    print("=== Keypad Debug Tool ===")
    print("This tool monitors input from a numeric keypad and prints key events.")
    print("Press Ctrl+C to exit.")
    
    # List available devices
    devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
    
    if not devices:
        print("No input devices found. Please check your connections.")
        return 1
    
    print("\nAvailable input devices:")
    for i, device in enumerate(devices):
        print(f"{i+1}. {device.name} ({device.path})")
    
    # Device selection
    choice = input("\nEnter device number: ")
    try:
        index = int(choice) - 1
        if 0 <= index < len(devices):
            device = devices[index]
        else:
            print("Invalid selection")
            return 1
    except ValueError:
        print("Please enter a number")
        return 1
    
    print(f"\nSelected device: {device.name}")
    print("Monitoring key input...")
    print("Press any key. Pressing '5' (or keypad 5) will print a special message.")
    
    try:
        # Grab device exclusively
        device.grab()
        
        # Main key monitoring loop
        while True:
            r, w, x = select.select([device.fd], [], [], 0.1)
            if r:
                for event in device.read():
                    if event.type == evdev.ecodes.EV_KEY and event.value == 1:  # key down
                        key_code = event.code
                        
                        try:
                            key_name = evdev.ecodes.KEY[key_code]
                            key_char = key_name.replace('KEY_', '')
                            
                            # Make keypad key names more readable
                            if key_name.startswith('KEY_KP'):
                                key_char = key_name.replace('KEY_KP', 'Keypad')
                            
                            print(f"Key pressed: code={key_code}, name={key_name}, char={key_char}")
                            
                            # Special debug handling for key 5
                            if key_name == 'KEY_KP5' or key_name == 'KEY_5':
                                print("\n" + "*" * 40)
                                print("*           Key 5 pressed!           *")
                                print("*" * 40 + "\n")
                        except Exception as e:
                            print(f"Key decode error: {e} (code={key_code})")
    
    except KeyboardInterrupt:
        print("\nExiting program...")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Release device
        try:
            device.ungrab()
        except:
            pass
    
    return 0

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main()) 