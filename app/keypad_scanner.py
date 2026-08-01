#!/usr/bin/env python3
import evdev
import time
import threading
import subprocess
import os
import sys
import select
from pathlib import Path
import json

APP_DIR = Path(__file__).resolve().parent

# Path to the scanner script
SCANNER_SCRIPT = str(APP_DIR / 'lib' / 'scan.py')


def load_scan_modes():
    """
    Load keypad→mode mapping from mode.json.
    If missing, fall back to 1:diary, 2:receipt, 3:flyer.
    """
    default_modes = {
        '1': 'diary',
        '2': 'receipt',
        '3': 'flyer',
    }
    mode_path = APP_DIR / 'config' / 'mode.json'
    try:
        if not mode_path.is_file():
            return default_modes
        with mode_path.open('r', encoding='utf-8') as f:
            data = json.load(f)
        keybindings = data.get('keybindings')
        if isinstance(keybindings, dict) and keybindings:
            return keybindings
        return default_modes
    except Exception as e:
        print(f"Error while reading mode.json: {e}")
        return default_modes


# Mode mapping (loaded at startup)
SCAN_MODES = load_scan_modes()

# Debug flag
DEBUG_MODE = True

class KeypadMonitor:
    """Monitor keypad input and trigger scans (interactive/debug)."""
    
    def __init__(self):
        self.device = None
        self.current_input = ""
        self.last_input_time = 0
        self.input_timeout = 5  # input timeout in seconds
        self.running = False
        self.timer = None
    
    def find_keypad(self):
        """Let the user choose a keypad device interactively."""
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        print("Available input devices:")
        for device in devices:
            print(f" - {device.path}: {device.name}")
        
        # Simple selection menu
        print("\nSelect the numeric keypad device:")
        for i, device in enumerate(devices):
            print(f"{i+1}. {device.name}")
        
        choice = input("Enter device number: ")
        try:
            index = int(choice) - 1
            if 0 <= index < len(devices):
                self.device = devices[index]
                print(f"Selected keypad: '{self.device.name}'")
                return True
            else:
                print("Invalid selection")
                return False
        except ValueError:
            print("Please enter a number")
            return False
    
    def start_monitoring(self):
        """Start monitoring keypad input."""
        if not self.device:
            if not self.find_keypad():
                print("No numeric keypad found. Exiting.")
                return False
        
        self.running = True
        print(f"Start monitoring keypad '{self.device.name}'...")
        print("Press the following keys to start a scan:")
        for key, mode in SCAN_MODES.items():
            print(f" - {key}: {mode} mode")
        print("Press Enter to confirm the selected digit.")
        if DEBUG_MODE:
            print("● Debug mode: pressing 5 will print a special message.")
        
        # Start monitoring loop
        self._monitor_loop()
        return True
    
    def _monitor_loop(self):
        """Main input monitoring loop (blocking)."""
        try:
            # Grab device exclusively so other processes don't receive key events
            self.device.grab()
            
            while self.running:
                r, w, x = select.select([self.device.fd], [], [], 0.1)
                if r:
                    for event in self.device.read():
                        if event.type == evdev.ecodes.EV_KEY and event.value == 1:  # key down
                            self._handle_key_press(event.code)
                
                # Check for input timeout
                if self.current_input and time.time() - self.last_input_time > self.input_timeout:
                    print(f"Input timeout; clearing buffer: {self.current_input}")
                    self.current_input = ""
        
        except Exception as e:
            print(f"Error while monitoring keypad: {e}")
        finally:
            if self.device:
                # Release device
                try:
                    self.device.ungrab()
                except:
                    pass
    
    def _handle_key_press(self, key_code):
        """Handle a key press event."""
        key_name = evdev.ecodes.KEY[key_code]
        
        # Special debug handling for key 5 (both keypad and main keyboard)
        if DEBUG_MODE and (key_name == 'KEY_KP5' or key_name == 'KEY_5'):
            print("\n" + "*" * 40)
            print("*           Key 5 pressed!           *")
            print("*" * 40 + "\n")
            # Dump some debug information
            print(f"Key event: code={key_code}, name={key_name}")
            print(f"Device: {self.device.name}, path={self.device.path}")
            print(f"Current state: input={self.current_input}, running={self.running}")
            return
        
        # Numeric keypad keys
        if key_name.startswith('KEY_KP') and key_name[6:].isdigit():
            digit = key_name[6:]  # KEY_KP1 -> "1"
            
            # Treat as new input if last press was more than input_timeout seconds ago
            if not self.current_input or (time.time() - self.last_input_time > self.input_timeout):
                self.current_input = digit
            else:
                # Overwrite
                self.current_input = digit
            
            self.last_input_time = time.time()
            print(f"Buffered input: {self.current_input}")
            
            # Reset timeout timer
            if self.timer:
                self.timer.cancel()
            
            # Schedule buffer clear after timeout seconds
            self.timer = threading.Timer(self.input_timeout, self._clear_input)
            self.timer.daemon = True
            self.timer.start()
        
        # Enter key
        elif key_name == 'KEY_KPENTER' or key_name == 'KEY_ENTER':
            if self.current_input:
                self._execute_scan(self.current_input)
                self.current_input = ""
                if self.timer:
                    self.timer.cancel()
    
    def _clear_input(self):
        """Clear buffer on timeout."""
        if self.current_input:
            print(f"Input timeout; clearing buffer: {self.current_input}")
            self.current_input = ""
    
    def _execute_scan(self, input_key):
        """Execute scan based on the buffered keypad input."""
        if input_key in SCAN_MODES:
            mode = SCAN_MODES[input_key]
            print(f"\nStarting scan in '{mode}' mode...")
            
            # Run scanner as a module so package-relative imports in lib/ work
            try:
                scan_cmd = [sys.executable, "-m", "lib.scan", mode]
                scan_env = os.environ.copy()
                scan_env["PYTHONPATH"] = str(APP_DIR)

                process = subprocess.Popen(
                    scan_cmd,
                    cwd=str(APP_DIR),
                    env=scan_env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                
                # Stream output in real time
                print("Scan in progress...")
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        print(output.strip())
                
                # Print stderr, if any
                stderr = process.stderr.read()
                if stderr:
                    print("Error output from scan:")
                    print(stderr)
                
                # Check exit code
                exit_code = process.poll()
                if exit_code == 0:
                    print(f"Scan in mode '{mode}' finished successfully")
                else:
                    print(f"Scan process exited with error code {exit_code}")
                
            except Exception as e:
                print(f"Error while executing scan: {e}")
            
            print("\nWaiting for keypad input again...")
        else:
            print(f"Invalid keypad input: {input_key}")
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.timer:
            self.timer.cancel()
        if self.device:
            try:
                self.device.ungrab()
            except:
                pass
        print("Stopped monitoring keypad")


def main():  # pragma: no cover
    """Main entry point (interactive keypad scanner)."""
    print("Keypad scanner - startup")
    print(f"Debug mode: {'ON' if DEBUG_MODE else 'OFF'}")
    
    # Check that the scanner script exists
    if not os.path.exists(SCANNER_SCRIPT):
        print(f"Error: scanner script '{SCANNER_SCRIPT}' not found")
        return 1
    
    # Initialize monitor
    monitor = KeypadMonitor()
    
    try:
        # Start monitoring
        if not monitor.start_monitoring():
            return 1
        
        # Main loop (Ctrl+C to exit)
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nExiting program...")
    finally:
        # Stop monitoring
        monitor.stop()
    
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main()) 