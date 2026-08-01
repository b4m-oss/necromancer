#!/usr/bin/env python3
import evdev
import time
import threading
import subprocess
import os
import sys
import select
import logging
import signal
from pathlib import Path
from datetime import datetime
import json

# Logging
LOG_DIR = Path('/var/log/scanner')
LOG_FILE = LOG_DIR / 'scanner.log'

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
        logging.error(f"Error while reading mode.json: {e}")
        return default_modes


# Mode mapping (loaded at startup)
SCAN_MODES = load_scan_modes()

# Substrings used to auto-detect keypad devices
KEYPAD_NAMES = ['keypad', 'numpad', 'numeric', '10key']


class KeypadDaemon:
    """Daemon that monitors numeric keypad input and triggers scans."""
    
    def __init__(self, device_path=None):
        self.device_path = device_path
        self.device = None
        self.current_input = ""
        self.last_input_time = 0
        self.input_timeout = 5  # input timeout in seconds
        self.running = False
        self.timer = None
        self.setup_logging()
    
    def setup_logging(self):
        """Configure logging."""
        # Ensure log directory exists
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # Log format
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format=log_format
        )
        
        # Also log to console
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(console)
        
        logging.info("Keypad daemon initialized")
    
    def find_keypad(self):
        """Auto-detect keypad device."""
        logging.info("Searching for numeric keypad...")
        
        # If a specific device path is given, try to use it
        if self.device_path:
            try:
                device = evdev.InputDevice(self.device_path)
                logging.info(f"Using specified device '{device.name}'")
                self.device = device
                return True
            except Exception as e:
                logging.error(f"Failed to open specified device '{self.device_path}': {e}")
                return False
        
        # Enumerate all available input devices
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        
        # Log the list of devices
        logging.info("Available input devices:")
        for device in devices:
            logging.info(f" - {device.path}: {device.name}")
        
        # Look for something that looks like a numeric keypad
        for device in devices:
            device_name = device.name.lower()
            
            # Check name substrings first
            if any(keyword in device_name for keyword in KEYPAD_NAMES):
                logging.info(f"Auto-detected numeric keypad: '{device.name}'")
                self.device = device
                return True
            
            # Fallback: inspect capabilities
            if evdev.ecodes.EV_KEY in device.capabilities():
                key_caps = device.capabilities()[evdev.ecodes.EV_KEY]
                
                # Look for presence of common keypad number keys
                keypad_keys = [evdev.ecodes.KEY_KP0, evdev.ecodes.KEY_KP1, evdev.ecodes.KEY_KP2]
                if all(key in key_caps for key in keypad_keys):
                    logging.info(f"Detected device with keypad capabilities: '{device.name}'")
                    self.device = device
                    return True
        
        logging.error("No numeric keypad device found")
        return False
    
    def start(self):
        """Start the daemon."""
        if not self.device and not self.find_keypad():
            logging.error("Cannot start daemon: no numeric keypad found")
            return False
        
        self.running = True
        logging.info(f"Start monitoring keypad '{self.device.name}'")
        logging.info("Press the following keys to start a scan:")
        for key, mode in SCAN_MODES.items():
            logging.info(f" - {key}: {mode} mode")
        
        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self._monitor_loop)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        return True
    
    def _handle_signal(self, signum, frame):
        """Signal handler."""
        logging.info(f"Received signal {signum}. Shutting down.")
        self.stop()
        sys.exit(0)
    
    def _monitor_loop(self):
        """Main input monitoring loop (runs in a background thread)."""
        try:
            # Grab device so that other processes do not receive events
            self.device.grab()
            
            while self.running:
                r, w, x = select.select([self.device.fd], [], [], 0.1)
                if r:
                    for event in self.device.read():
                        if event.type == evdev.ecodes.EV_KEY and event.value == 1:  # key down
                            self._handle_key_press(event.code)
                
                # Check for input timeout
                if self.current_input and time.time() - self.last_input_time > self.input_timeout:
                    logging.info(f"Input timeout; clearing buffer: {self.current_input}")
                    self.current_input = ""
        
        except Exception as e:
            logging.error(f"Error while monitoring keypad: {e}")
            import traceback
            logging.error(traceback.format_exc())
        finally:
            if self.device and self.running:
                try:
                    self.device.ungrab()
                except:
                    pass
    
    def _handle_key_press(self, key_code):
        """Handle a key press event."""
        try:
            key_name = evdev.ecodes.KEY[key_code]
            
            # Numeric keypad keys
            if key_name.startswith('KEY_KP') and key_name[6:].isdigit():
                digit = key_name[6:]  # KEY_KP1 -> "1"
                
                # Treat as new input if last key was pressed more than input_timeout ago
                if not self.current_input or (time.time() - self.last_input_time > self.input_timeout):
                    self.current_input = digit
                else:
                    # Overwrite existing input
                    self.current_input = digit
                
                self.last_input_time = time.time()
                logging.info(f"Buffered input: {self.current_input}")
                
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
                    # Start scan in a separate thread
                    scan_thread = threading.Thread(target=self._execute_scan, args=(self.current_input,))
                    scan_thread.daemon = True
                    scan_thread.start()
                    
                    self.current_input = ""
                    if self.timer:
                        self.timer.cancel()
        except Exception as e:
                logging.error(f"Error while handling key press: {e}")
    
    def _clear_input(self):
        """Clear input buffer on timeout."""
        if self.current_input:
            logging.info(f"Input timeout; clearing buffer: {self.current_input}")
            self.current_input = ""
    
    def _execute_scan(self, input_key):
        """Execute scan based on the given keypad input."""
        if input_key in SCAN_MODES:
            mode = SCAN_MODES[input_key]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"====== [{timestamp}] Starting scan in '{mode}' mode ======")
            
            # Run scanner as a module so package-relative imports in lib/ work
            try:
                scan_cmd = [sys.executable, "-m", "lib.scan", mode]
                scan_env = os.environ.copy()
                # Belt-and-suspenders: ensure app root is on sys.path under systemd / odd cwd
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
                logging.info("Scan in progress...")
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        logging.info(f"SCAN: {output.strip()}")
                
                # Check stderr
                stderr = process.stderr.read()
                if stderr:
                    logging.error("Error output from scan:")
                    for line in stderr.splitlines():
                        logging.error(f"SCAN-ERR: {line}")
                
                # Check exit code
                exit_code = process.poll()
                if exit_code == 0:
                    logging.info(f"====== Scan in mode '{mode}' completed successfully ======")
                else:
                    logging.error(f"====== Scan process exited with error code {exit_code} ======")
                
            except Exception as e:
                logging.error(f"Error while executing scan: {e}")
                import traceback
                logging.error(traceback.format_exc())
        else:
            logging.warning(f"Invalid keypad input: {input_key}")
    
    def stop(self):
        """Stop monitoring."""
        logging.info("Stopping keypad monitoring...")
        self.running = False
        if self.timer:
            self.timer.cancel()
        if self.device:
            try:
                self.device.ungrab()
            except:
                pass
        logging.info("Keypad monitoring stopped")


def main():  # pragma: no cover
    """Main entry point."""
    # Parse CLI arguments
    import argparse
    parser = argparse.ArgumentParser(description='Daemon that triggers scans from a numeric keypad')
    parser.add_argument('--device', help='Path to keypad input device (e.g. /dev/input/event0)')
    args = parser.parse_args()
    
    # Check that the scanner script exists
    if not os.path.exists(SCANNER_SCRIPT):
        logging.error(f"Error: scanner script '{SCANNER_SCRIPT}' not found")
        return 1
    
    # Initialize daemon
    daemon = KeypadDaemon(device_path=args.device)
    
    try:
        # Start daemon
        if not daemon.start():
            return 1
        
        # Keep main thread alive
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received; exiting program")
    except Exception as e:
        logging.error(f"Unexpected error occurred: {e}")
        import traceback
        logging.error(traceback.format_exc())
    finally:
        # Stop daemon
        daemon.stop()
    
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main()) 