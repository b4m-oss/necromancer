import json
import os
import subprocess
import shutil
from pathlib import Path


def load_nextcloud_config(config_path: str = str(Path(__file__).resolve().parent.parent / 'config' / 'upload.json')):
    """
    Load Nextcloud configuration from upload.json.
    Expected upload.json structure:
    {
      "provider": "nextcloud",
      "nextcloud": {
        "endpoint": "...",
        "username": "...",
        ...
      }
    }
    This function returns the \"nextcloud\" section as a flat dict.
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    provider = raw.get("provider", "nextcloud")
    if provider != "nextcloud":
        print(f"Warning: currently only provider='nextcloud' is supported (provider={provider})")

    nc_cfg = raw.get("nextcloud")
    if not isinstance(nc_cfg, dict):
        raise ValueError("Invalid 'nextcloud' section in upload.json")

    return nc_cfg


def test_nextcloud_connection() -> bool:
    """
    Lightweight connectivity test to the configured Nextcloud endpoint.
    This does not upload or modify any remote resources; it only issues
    a simple HTTP request (HEAD) and inspects the HTTP status line.
    """
    try:
        config = load_nextcloud_config()

        endpoint = config.get("endpoint")
        if not endpoint:
            print("Nextcloud endpoint is not configured.")
            return False

        # Use HEAD (-I) to avoid downloading content.
        curl_cmd = (
            f"curl -i -I "
            f"-u '{config['username']}:{config['password']}' "
            f"-k '{endpoint}'"
        )
        safe_cmd = curl_cmd.replace(
            f"{config['username']}:{config['password']}",
            "USERNAME:PASSWORD",
        )
        print(f"Testing Nextcloud connectivity with command: {safe_cmd}")

        result = subprocess.run(
            curl_cmd,
            shell=True,
            capture_output=True,
            text=True,
        )

        print("\n===== Nextcloud connectivity check output =====")
        print("stdout:")
        print(result.stdout)
        print("\nstderr:")
        print(result.stderr)
        print("===== end of output =====\n")

        # Extract first HTTP status line from stdout
        response_lines = result.stdout.strip().split("\n")
        status_line = next((line for line in response_lines if line.startswith("HTTP/")), None)

        if not status_line:
            print("Could not find HTTP status line for connectivity check")
            return False

        print(f"Connectivity response: {status_line}")
        parts = status_line.split()
        if len(parts) < 2:
            print(f"Invalid HTTP status line: {status_line}")
            return False

        try:
            status_code = int(parts[1])
        except ValueError:
            print(f"Failed to parse HTTP status code: {status_line}")
            return False

        if 200 <= status_code < 400:
            print(f"Nextcloud connectivity OK (status={status_code})")
            return True

        print(f"Nextcloud connectivity NG (status={status_code})")
        return False
    except Exception as e:
        print(f"Error while testing Nextcloud connectivity: {e}")
        return False


def create_remote_directory(remote_dir: str) -> bool:
    """
    Create a directory on Nextcloud (treat already-exists as success).
    :param remote_dir: Nextcloud directory path (e.g. 'Scans/20260303144904/')
    :return: True on success, False otherwise
    """
    try:
        config = load_nextcloud_config()

        # Build URL (ensure trailing slash)
        remote_url = f"{config['endpoint']}{remote_dir.rstrip('/')}/"

        curl_cmd = (
            f"curl -v -i "
            f"-X MKCOL "
            f"-u '{config['username']}:{config['password']}' "
            f"-k '{remote_url}'"
        )

        safe_cmd = curl_cmd.replace(
            f"{config['username']}:{config['password']}",
            "USERNAME:PASSWORD"
        )
        print(f"Create remote directory command: {safe_cmd}")

        result = subprocess.run(curl_cmd, shell=True, capture_output=True, text=True)

        print("\n===== MKCOL output =====")
        print("stdout:")
        print(result.stdout)
        print("\nstderr:")
        print(result.stderr)
        print("===== end of output =====\n")

        # Extract status code from HTTP response header
        response_lines = result.stdout.strip().split('\n')
        status_line = next((line for line in response_lines if line.startswith('HTTP/')), None)

        if not status_line:
            print("Could not find HTTP status line for MKCOL")
            return False

        print(f"MKCOL response: {status_line}")
        parts = status_line.split()
        if len(parts) < 2:
            print(f"Invalid MKCOL status line: {status_line}")
            return False

        try:
            status_code = int(parts[1])
        except ValueError:
            print(f"Failed to parse MKCOL status code: {status_line}")
            return False

        if status_code == 201:
            print(f"Successfully created remote directory: {remote_dir}")
            return True
        if status_code == 405:
            # 405 usually means \"already exists\"; treat as success.
            print(f"Remote directory already exists (treated as success): {remote_dir}")
            return True

        print(f"MKCOL failed (status code: {status_code})")
        return False

    except Exception as e:
        print(f"Error while creating remote directory: {e}")
        return False


def upload_file_to_nextcloud(file_path: str, remote_path: str = None):
    """
    Upload a single file to Nextcloud.
    :param file_path: local file path
    :param remote_path: remote path on Nextcloud (if None, upload_folder + filename)
    :return: True on success, False otherwise
    """
    try:
        config = load_nextcloud_config()
        
        # Ensure file exists
        if not os.path.exists(file_path):
            print(f"Error: file '{file_path}' not found")
            return False
        
        # Build remote path if not explicitly given
        if remote_path is None:
            # Use just the filename under the configured upload folder
            filename = os.path.basename(file_path)
            remote_path = f"{config['upload_folder']}{filename}"
        
        # Build remote URL
        remote_url = f"{config['endpoint']}{remote_path}"
        
        print("Uploading to Nextcloud:")
        print(f"- local file: {file_path}")
        print(f"- remote URL: {remote_url}")
        print(f"- remote folder: {config['upload_folder']}")
        
        # Execute curl via shell
        curl_cmd = (
            f"curl -v -i "
            f"-X PUT "
            f"-u '{config['username']}:{config['password']}' "
            f"--upload-file '{file_path}' "
            f"-k '{remote_url}'"
        )
        
        # Log a safe version without credentials
        safe_cmd = curl_cmd.replace(f"{config['username']}:{config['password']}", "USERNAME:PASSWORD")
        print(f"Executing command: {safe_cmd}")
        
        # Run curl
        result = subprocess.run(curl_cmd, shell=True, capture_output=True, text=True)
        
        # Dump stdout/stderr for debugging
        print("\n===== CURL output =====")
        print("stdout:")
        print(result.stdout)
        
        print("\nstderr:")
        print(result.stderr)
        print("===== end of output =====\n")
        
        # Try to extract HTTP status code from stdout
        response_lines = result.stdout.strip().split('\n')
        status_line = next((line for line in response_lines if line.startswith('HTTP/')), None)
        
        if status_line:
            print(f"Server response: {status_line}")
            
            # Check status code
            status_parts = status_line.split()
            if len(status_parts) >= 2:
                try:
                    status_code = int(status_parts[1])
                    if 200 <= status_code < 300:
                        print(f"Upload succeeded: {remote_path} (status={status_code})")
                        return True
                    else:
                        print(f"Upload failed: server returned error (status={status_code})")
                        return False
                except ValueError:
                    print(f"Failed to parse HTTP status code: {status_line}")
                    return False
            else:
                print(f"Invalid HTTP status line format: {status_line}")
                return False
        else:
            # Fall back to return code and stderr content
            if result.returncode == 0:
                if "100.0%" in result.stderr:
                    print("Upload succeeded (status unknown, but transfer completed).")
                    return True
                else:
                    print("Upload result unknown (no status and transfer not confirmed).")
                    return False
            else:
                print(f"curl command failed (return code: {result.returncode})")
                return False
    
    except Exception as e:
        print(f"Error while uploading to Nextcloud: {e}")
        import traceback
        traceback.print_exc()
        return False


def upload_directory_to_nextcloud(dir_path: str, delete_after_upload: bool = None):
    """
    Upload all files in a directory to Nextcloud.
    :param dir_path: local directory path
    :param delete_after_upload: whether to delete files after upload (None uses config)
    :return: True on success, False otherwise
    """
    try:
        config = load_nextcloud_config()
        
        # Ensure directory exists
        if not os.path.isdir(dir_path):
            print(f"Error: directory '{dir_path}' not found")
            return False
        
        # Use config value if caller did not specify
        if delete_after_upload is None:
            delete_after_upload = config.get('delete_after_upload', False)
        
        # Use the directory name (e.g. timestamp) as the subdirectory on Nextcloud
        dir_name = os.path.basename(os.path.normpath(dir_path))
        remote_dir = f"{config['upload_folder']}{dir_name}/"

        print(f"Remote directory: {remote_dir}")

        # Ensure remote directory exists
        if not create_remote_directory(remote_dir):
            print(f"Error: failed to create remote directory '{remote_dir}'")
            return False

        # Collect local files
        files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        
        if not files:
            print(f"Warning: directory '{dir_path}' has no files")
            return False
        
        # Upload all files
        upload_success = True
        uploaded_files = []
        
        for filename in files:
            file_path = os.path.join(dir_path, filename)
            remote_path = f"{remote_dir}{filename}"
            
            success = upload_file_to_nextcloud(file_path, remote_path)
            
            if success:
                uploaded_files.append(file_path)
            else:
                upload_success = False
        
        # Optionally delete successfully uploaded files and directory
        if upload_success and delete_after_upload and uploaded_files:
            print("Deleting successfully uploaded files...")
            for file_path in uploaded_files:
                try:
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
                except Exception as e:
                    print(f"Error while deleting file: {e}")
            
            # Remove directory if it is empty now
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                    print(f"Deleted empty directory: {dir_path}")
                except Exception as e:
                    print(f"Error while deleting directory: {e}")
        
        return upload_success
    
    except Exception as e:
        print(f"Error while uploading directory to Nextcloud: {e}")
        return False


def upload_pdf_to_nextcloud(pdf_path: str, delete_after_upload: bool = None):
    """
    Upload a single PDF file to Nextcloud.
    :param pdf_path: local PDF path
    :param delete_after_upload: whether to delete local file after upload (None uses config)
    :return: True on success, False otherwise
    """
    try:
        config = load_nextcloud_config()
        
        # Ensure file exists
        if not os.path.isfile(pdf_path):
            print(f"Error: PDF file '{pdf_path}' not found")
            return False
        
        # Use config if caller did not specify
        if delete_after_upload is None:
            delete_after_upload = config.get('delete_after_upload', False)
        
        # Use only the filename on the remote side
        pdf_filename = os.path.basename(pdf_path)
        
        # Upload
        remote_path = f"{config['upload_folder']}{pdf_filename}"
        success = upload_file_to_nextcloud(pdf_path, remote_path)
        
        # Optionally delete local file after successful upload
        if success and delete_after_upload:
            try:
                os.remove(pdf_path)
                print(f"Deleted local PDF: {pdf_path}")
            except Exception as e:
                print(f"Error while deleting local PDF: {e}")
        
        return success
    
    except Exception as e:
        print(f"Error while uploading PDF to Nextcloud: {e}")
        return False 