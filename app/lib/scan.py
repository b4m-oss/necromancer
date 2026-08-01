import json
import os
import subprocess
import datetime
import time
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageStat
import threading

try:
    from .upload_adapter import get_uploader_from_config
    from .nextcloud import load_nextcloud_config
    from .upload_adapter import _load_upload_config_raw
except ImportError:
    # Deploy as `python -m lib.scan` with only ~/app on path; tolerate odd package resolution.
    _app_root = Path(__file__).resolve().parent.parent
    if str(_app_root) not in sys.path:
        sys.path.insert(0, str(_app_root))
    from lib.upload_adapter import get_uploader_from_config
    from lib.nextcloud import load_nextcloud_config
    from lib.upload_adapter import _load_upload_config_raw

A4_PAGE_WIDTH_MM = 210
A4_PAGE_HEIGHT_MM = 297

def is_blank_page(image_path, white_threshold=187, white_ratio_threshold=0.995):
    """
    Helper to decide whether the page is almost blank (mostly white).
    - white_threshold: pixels at or above this value are treated as \"white\"
    - white_ratio_threshold: if the ratio of white pixels is above this value, treat as blank
    """
    try:
        img = Image.open(image_path).convert("L")
        # Downscale for performance if needed
        max_size = 512
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size))

        hist = img.histogram()
        total_pixels = sum(hist)
        if total_pixels == 0:
            return False

        # Count pixels above the white_threshold
        start_index = int(white_threshold)
        white_pixels = sum(hist[start_index:])
        white_ratio = white_pixels / total_pixels

        print(
            f"Blank page check: {os.path.basename(image_path)} "
            f"pixels={total_pixels}, white_pixels={white_pixels}, "
            f"white_ratio={white_ratio:.4f}"
        )

        return white_ratio >= white_ratio_threshold
    except Exception as e:
        print(f"Error while checking blank page: {e} (file={image_path})")
        return False

def create_timestamp_dir():
    """Create a temporary directory named with a timestamp and return its path."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    tmp_dir = Path(__file__).resolve().parent.parent / 'tmp' / timestamp
    os.makedirs(tmp_dir, exist_ok=True)
    return tmp_dir, timestamp


def build_batch_scan_command(config_name: str):
    """
    Build the batch scan command and related metadata for the given mode.
    This does not execute any external command and is safe for use in
    diagnostic utilities such as --dump-config or future self-checks.
    """
    configs = load_scan_configs()
    if config_name not in configs:
        raise ValueError(f"configuration '{config_name}' is not defined in mode.json")

    cfg = configs[config_name]

    # Scan settings
    scanner_cfg = load_scanner_config()
    device_name = scanner_cfg["device_name"]
    resolution = cfg.get('resolution', 200)
    mode = cfg.get('mode', 'Color')
    if isinstance(mode, str) and mode:
        mode_normalized = mode[0].upper() + mode[1:].lower()
    else:
        mode_normalized = "Color"

    source = cfg.get('source', scanner_cfg.get('default_source', 'ADF Duplex'))

    # scanimage batch always uses JPEG as intermediate format
    img_format = 'jpeg'

    # Output pattern (use a placeholder timestamp so that the pattern
    # matches the real runtime layout but is deterministic for display)
    placeholder_ts = "{timestamp}"
    tmp_base = Path(__file__).resolve().parent.parent / 'tmp' / placeholder_ts
    output_pattern = str(tmp_base / f"{config_name}-%d.jpg")

    # Extra options from mode.json (keep in sync with batch_scan_with_scanimage)
    extra_opts = []
    if cfg.get('swdeskew'):
        extra_opts.append('--swdeskew=yes')
    if cfg.get('swcrop'):
        extra_opts.append('--swcrop=yes')
    if cfg.get('ald'):
        extra_opts.append('--ald=yes')

    page_width_mm = cfg.get('page_width_mm')
    page_height_mm = cfg.get('page_height_mm')
    max_page_height_mm = cfg.get('max_page_height_mm')
    if page_width_mm:
        extra_opts.append(f'--page-width={page_width_mm}')
    if page_height_mm:
        extra_opts.append(f'--page-height={page_height_mm}')
    elif max_page_height_mm:
        extra_opts.append(f'--page-height={max_page_height_mm}')

    extra_str = ""
    if extra_opts:
        extra_str = " " + " ".join(extra_opts)

    batch_cmd = (
        f'scanimage --device="{device_name}" '
        f'--resolution={resolution} '
        f'--mode={mode_normalized} '
        f'--format={img_format} '
        f'--source="{source}" '
        f'--batch={output_pattern} '
        f'--batch-count=-1 '
        f'--batch-start=1 '
        f'--progress'
        f'{extra_str} '
    )

    effective_params = {
        "device_name": device_name,
        "resolution": resolution,
        "mode": mode_normalized,
        "source": source,
        "format": img_format,
        "output_pattern": output_pattern,
        "extra_options": extra_opts,
    }

    return {
        "type": "batch",
        "mode": config_name,
        "command": batch_cmd,
        "output_pattern": output_pattern,
        "effective_params": effective_params,
    }


def build_upload_target_info(config_name: str):
    """
    Build information about the upload target for the given mode.
    Currently assumes Nextcloud as the provider but returns a generic
    structure so that future providers can be added.
    """
    # Mode is validated here to mirror build_batch_scan_command behaviour
    configs = load_scan_configs()
    if config_name not in configs:
        raise ValueError(f"configuration '{config_name}' is not defined in mode.json")

    cfg = configs[config_name]
    file_format = str(cfg.get("file_format", "")).upper()

    try:
        nc_cfg = load_nextcloud_config()
    except Exception:
        # If upload configuration is not available, still return a
        # minimal structure so that dump-config can report something.
        nc_cfg = {}

    provider = "nextcloud"
    endpoint = nc_cfg.get("endpoint", "<missing-endpoint>")
    upload_folder = nc_cfg.get("upload_folder", "Scans/")
    delete_after_upload = nc_cfg.get("delete_after_upload", False)

    # For PDF modes, batch_scan_with_scanimage() creates
    # {config_name}-{timestamp}.pdf under tmp/ and upload_pdf_to_nextcloud()
    # sends it as upload_folder + filename. For non-PDF modes, a directory
    # named by timestamp is uploaded.
    if file_format == "PDF":
        remote_path_pattern = f"{upload_folder}{config_name}-" + "{timestamp}.pdf"
        strategy = "pdf"
    else:
        remote_path_pattern = upload_folder + "{timestamp}/"
        strategy = "directory"

    return {
        "provider": provider,
        "mode": config_name,
        "endpoint": endpoint,
        "upload_folder": upload_folder,
        "delete_after_upload": delete_after_upload,
        "strategy": strategy,
        "remote_path_pattern": remote_path_pattern,
    }


def dump_config(mode_name: str) -> str:
    """
    Build a human-readable dump of the effective scan and upload
    configuration for the given mode.
    """
    batch = build_batch_scan_command(mode_name)
    upload = build_upload_target_info(mode_name)

    lines = []
    lines.append(f"Mode: {mode_name}")
    lines.append("")
    lines.append("=== scanimage command (batch) ===")
    lines.append(batch["command"])
    lines.append("")
    lines.append("Parameters:")
    params = batch.get("effective_params", {})
    for key in sorted(params.keys()):
        lines.append(f"- {key}: {params[key]}")

    lines.append("")
    lines.append("=== upload target ===")
    lines.append(f"provider          : {upload.get('provider')}")
    lines.append(f"endpoint          : {upload.get('endpoint')}")
    lines.append(f"upload_folder     : {upload.get('upload_folder')}")
    lines.append(f"strategy          : {upload.get('strategy')}")
    lines.append(f"remote_path       : {upload.get('remote_path_pattern')}")
    lines.append(f"delete_after_upload: {upload.get('delete_after_upload')}")

    return "\n".join(lines)

def convert_images_to_pdf(image_dir, output_pdf):
    """Convert all images in the given directory into a single PDF."""
    # Only take image files directly under the directory (no subdirectories)
    image_files = []
    for f in os.listdir(image_dir):
        if f.lower().endswith(('.jpg', '.jpeg', '.png')) and os.path.isfile(os.path.join(image_dir, f)):
            image_files.append(f)
    
    image_files = sorted(image_files)  # sort by filename
    
    if not image_files:
        print("No image files found to convert into PDF")
        return False
    
    print(f"PDF conversion target: {len(image_files)} images")
    print(f"Image file list: {image_files}")
    
    try:
        if len(image_files) == 1:
            # Single-page case
            print(f"Creating single-page PDF from: {image_files[0]}")
            img = Image.open(os.path.join(image_dir, image_files[0]))
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output_pdf)
            print(f"Single-page PDF created successfully: {output_pdf}")
            return True
        
        # Multi-page case
        print(f"Creating multi-page PDF ({len(image_files)} pages)")
        images = []
        first_image = Image.open(os.path.join(image_dir, image_files[0]))
        print(f"Loading first image: {image_files[0]}")
        
        for img_file in image_files[1:]:
            img_path = os.path.join(image_dir, img_file)
            print(f"Loading additional image: {img_file}")
            img = Image.open(img_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)
        
        if first_image.mode != 'RGB':
            first_image = first_image.convert('RGB')
        
        first_image.save(output_pdf, save_all=True, append_images=images)
        print(f"PDF created successfully: {output_pdf} (pages: {len(image_files)})")
        
        # Sanity check for the PDF file
        if os.path.exists(output_pdf):
            pdf_size = os.path.getsize(output_pdf)
            print(f"PDF file size: {pdf_size / 1024:.1f} KB")
            if pdf_size == 0:
                print("Warning: PDF file size is 0 bytes")
                return False
        else:
            print(f"Error: PDF file {output_pdf} does not exist")
            return False
            
        return True
    except Exception as e:
        print(f"Error while converting images to PDF: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_scan_configs(config_path: str = str(Path(__file__).resolve().parent.parent / 'config' / 'mode.json')):
    """Load scan configuration from mode.json."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_scanner_config(config_path: str = str(Path(__file__).resolve().parent.parent / 'config' / 'scanner.json')):
    """
    Load scanner configuration from scanner.json.
    If the file is missing or invalid, return defaults (iX500 example).
    """
    default_cfg = {
        # Full SANE device name example. Users should override this to match their environment.
        "device_name": "fujitsu:ScanSnap iX500:17872",
        # Keywords used when searching scanimage -L output.
        # These are lowercased and compared against the device name and description.
        "vendor_keyword": "fujitsu",
        "model_keyword": "ix500",
        "backend": "fujitsu",
        "default_source": "ADF Duplex",
        "test_timeout_sec": 10,
    }
    try:
        if not os.path.isfile(config_path):
            return default_cfg
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults (fill missing keys)
        merged = {**default_cfg, **data}
        return merged
    except Exception as e:
        print(f"Error while reading scanner.json: {e}")
        return default_cfg

def get_scanner_list():
    """Get a list of available scanners via scanimage -L."""
    try:
        result = subprocess.run(['scanimage', '-L'], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error while listing scanners: {e}")
        return ""

def scanimage_scan(output_path, device_name, resolution=300, mode='Color', source='ADF Duplex', format='jpeg'):
    """
    Run a scan using scanimage.
    :param output_path: output file path
    :param device_name: scanner device name
    :param resolution: resolution
    :param mode: scan mode (Color, Gray, Lineart)
    :param source: scan source (Flatbed, ADF Duplex)
    :param format: output format (jpeg, png, tiff, pnm)
    :return: True on success, False otherwise
    """
    try:
        # Build scanimage command
        cmd = [
            'scanimage',
            f'--device-name="{device_name}" ',
            f'--resolution={resolution}',
            f'--mode={mode}',
            f'--source={source}',
            f'--format={format}',
            '-o', output_path
        ]
        
        print(f"Executing command: {' '.join(cmd)}")
        
        # Run command
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Scan error: {result.stderr}")
            return False
        
        print(f"Scan succeeded: {output_path}")
        return True
    
    except Exception as e:
        print(f"Exception while running scan: {e}")
        return False

def process_scanned_image(image_path):
    """Placeholder for post-processing the scanned image."""
    print(f"Post-processing image: {image_path}")

def monitor_scan_directory(directory, callback):
    """Monitor a scan directory and call the callback when new files appear."""
    processed_files = set()
    last_check_time = time.time()
    last_new_file_time = time.time()
    start_time = time.time()
    max_idle_time = 20  # maximum idle time (seconds) before we consider the scan finished
    min_monitoring_time = 10  # minimum monitoring time from start
    check_interval = 0.5  # polling interval (seconds)
    
    print(f"Start monitoring scan directory: {directory}")
    print(f"Monitor settings: max_idle={max_idle_time}s, min_time={min_monitoring_time}s")
    
    while True:
        current_time = time.time()
        elapsed_time = current_time - start_time
        
        # Get all JPG files currently in the directory
        try:
            current_files = set([f for f in os.listdir(directory) 
                              if f.lower().endswith('.jpg') and 
                              os.path.isfile(os.path.join(directory, f))])
        except Exception as e:
            print(f"Directory read error: {e}")
            current_files = set()
        
        new_files = current_files - processed_files
        
        if new_files:
            print(f"Detected new files: {len(new_files)} ({', '.join(sorted(new_files))})")
            last_new_file_time = current_time  # reset when new files appear
            
            for file_name in sorted(new_files):
                file_path = os.path.join(directory, file_name)
                try:
                    # Check file size (to ensure writing has finished)
                    file_size = os.path.getsize(file_path)
                    print(f"Found file: {file_name} ({file_size / 1024:.1f} KB)")
                    
                    # Call the callback
                    callback(file_path)
                except Exception as e:
                    print(f"Error while processing file: {e}")
                processed_files.add(file_name)
        
        # Periodically print status
        if len(processed_files) > 0 and (current_time - last_check_time > 2):
            last_check_time = current_time
            idle_time = current_time - last_new_file_time
            print(f"Monitor status: processed={len(processed_files)}, idle={idle_time:.1f}s, elapsed={elapsed_time:.1f}s")
        
        # Exit conditions:
        # 1. No new files for a while
        # 2. At least one file has been processed
        # 3. Minimum monitoring time has passed
        if (current_time - last_new_file_time > max_idle_time and 
            len(processed_files) > 0 and 
            elapsed_time > min_monitoring_time):
            
            print(f"Scan-finished candidate: idle={current_time - last_new_file_time:.1f}s > {max_idle_time}s")
            
            # Final check (ensure no new files appeared)
            time.sleep(3)
            try:
                final_files = set([f for f in os.listdir(directory) 
                                 if f.lower().endswith('.jpg') and 
                                 os.path.isfile(os.path.join(directory, f))])
            except Exception as e:
                print(f"Error during final directory check: {e}")
                final_files = current_files
                
            if final_files == processed_files:
                print(f"Stopping scan directory monitor: processed {len(processed_files)} files")
                file_list_str = ", ".join(sorted(list(processed_files)))
                print(f"Processed files: {file_list_str}")
                return len(processed_files)
            else:
                # There are still new files
                new_count = len(final_files - processed_files)
                new_files_list = sorted(list(final_files - processed_files))
                print(f"Additional files detected ({new_count}): {', '.join(new_files_list)}")
                print("Continue monitoring")
                last_new_file_time = current_time
        
        # Short sleep before the next poll
        time.sleep(check_interval)

def batch_scan_with_scanimage(config_name: str, upload_to_nextcloud=True):
    """
    Run a batch scan with scanimage based on mode.json configuration.
    :param config_name: profile name defined in mode.json
    :param upload_to_nextcloud: whether to upload to the cloud
    :return: temporary directory path on success, None on failure
    """
    configs = load_scan_configs()
    if config_name not in configs:
        print(f"Error: configuration '{config_name}' is not defined in mode.json")
        return None
    
    cfg = configs[config_name]
    tmp_dir, timestamp = create_timestamp_dir()
    print(f"Created temporary scan directory: {tmp_dir}")
    
    # Scan settings
    scanner_cfg = load_scanner_config()
    device_name = scanner_cfg["device_name"]
    resolution = cfg.get('resolution', 200)
    mode = cfg.get('mode', 'Color')
    # scanimage is usually case-insensitive, but normalize for clarity
    if isinstance(mode, str) and mode:
        mode = mode[0].upper() + mode[1:].lower()
    else:
        mode = "Color"
    # Prefer source from mode.json, fall back to scanner.json default_source
    source = cfg.get('source', scanner_cfg.get('default_source', 'ADF Duplex'))
    format = cfg.get('file_format', 'jpeg').lower()
    if format == 'jpg':
        format = 'jpeg'  # scanimage expects 'jpeg'
    
    # Output pattern (extension fixed to .jpg for intermediate images)
    output_pattern = str(tmp_dir / f"{config_name}-%d.jpg")
    
    print(f"Starting batch scan with config: {config_name}")
    print(f"Scanner settings: device={device_name}, resolution={resolution}, mode={mode}")
    print(f"Output pattern: {output_pattern}")
    print("All pages in the feeder will be scanned...")
    
    # Use ScannerManager
    scanner = ScannerManager.get_instance()
    
    # Warm up the scanner to make sure it is ready
    scanner_ready = scanner.warm_up_scanner()
    if not scanner_ready:
        print("Warning: scanner warm-up reported an issue, but will try scanning anyway")
    
    # Execute batch scan
    print("Starting batch scan...")
    success = False
    
    # Run batch scan command
    try:
        # Build extra options from mode.json
        extra_opts = []
        if cfg.get('swdeskew'):
            extra_opts.append('--swdeskew=yes')
        if cfg.get('swcrop'):
            extra_opts.append('--swcrop=yes')
        if cfg.get('ald'):
            extra_opts.append('--ald=yes')
        # Fixed size and max height are mutually exclusive
        page_width_mm = cfg.get('page_width_mm')
        page_height_mm = cfg.get('page_height_mm')
        max_page_height_mm = cfg.get('max_page_height_mm')
        if page_width_mm:
            extra_opts.append(f'--page-width={page_width_mm}')
        if page_height_mm:
            extra_opts.append(f'--page-height={page_height_mm}')
        elif max_page_height_mm:
            extra_opts.append(f'--page-height={max_page_height_mm}')

        extra_str = ""
        if extra_opts:
            extra_str = " " + " ".join(extra_opts)

        batch_cmd = (
            f'scanimage --device="{device_name}" '
            f'--resolution={resolution} '
            f'--mode={mode} '
            f'--format=jpeg '
            f'--source="{source}" '
            f'--batch={output_pattern} '
            f'--batch-count=-1 '       # scan all pages
            f'--batch-start=1 '        # start numbering at 1
            f'--progress'
            f'{extra_str} '
        )
        
        print(f"Executing batch command: {batch_cmd}")
        result = subprocess.run(batch_cmd, shell=True, capture_output=True, text=True, timeout=180)
        
        # Log scan output
        print("scanimage stdout:")
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("scanimage stderr (errors/warnings):")
            print(result.stderr)
            
            # Inspect stderr to infer success
            if "scanned" in result.stderr and "pages scanned" in result.stderr:
                # Extract the number of pages scanned
                import re
                matches = re.search(r'(\d+) pages scanned', result.stderr)
                if matches and int(matches.group(1)) > 0:
                    print(f"Scan succeeded: {matches.group(1)} pages scanned")
                    success = True
                elif "0 pages scanned" in result.stderr:
                    print("Scan error: 0 pages scanned")
                    success = False
                else:
                    # No explicit page count but also no clear error
                    print("Treating scan as success (page count unknown)")
                    success = True
            elif "error" in result.stderr.lower():
                print("Error detected in scan stderr")
                success = False
            else:
                # No explicit error in stderr, treat as success
                print("No error message found, treating scan as success")
                success = True
        
        # Also check return code
        if result.returncode != 0:
            print(f"Warning: scanimage exited with non-zero status {result.returncode}")
            # We may still treat as success if files exist
        else:
            print("scanimage finished with status code 0")
            success = True
            
    except subprocess.TimeoutExpired:
        print("Scan process timed out. Partial files may still exist.")
        # Treat as potentially successful and verify files later
        success = True
    except Exception as e:
        print(f"Exception during batch scan: {e}")
        success = False
    
    # Always verify files after the scan
    print("\nChecking scan results...")
    time.sleep(2)  # give the filesystem a moment to flush
    
    # Inspect directory contents
    try:
        all_files = os.listdir(tmp_dir)
        jpg_files = [f for f in all_files if f.lower().endswith('.jpg')]
        jpg_files.sort()
        
        print(f"Total files in directory: {len(all_files)}")
        print(f"JPEG files: {len(jpg_files)}")
        
        if jpg_files:
            print("Scanned files:")
            for idx, file_name in enumerate(jpg_files):
                file_path = os.path.join(tmp_dir, file_name)
                file_size = os.path.getsize(file_path)
                print(f"  {idx+1}. {file_name} ({file_size / 1024:.1f} KB)")
            success = True
        else:
            print("Warning: no scanned JPEG files found")
            if success:
                print("scanimage reported success, but no files were created")
                success = False
    except Exception as e:
        print(f"Error while checking output files: {e}")
    
    # Automatic blank page removal
    # Applied only when mode.json has blank_filter=true.
    # For backward compatibility, default to diary/flyer when setting is missing.
    if jpg_files and cfg.get('blank_filter', config_name in ('diary', 'flyer')):
        print("\nDetecting and removing blank pages...")
        kept_files = []
        removed_files = []
        for file_name in jpg_files:
            file_path = os.path.join(tmp_dir, file_name)
            if is_blank_page(file_path):
                print(f"Detected blank page, removing: {file_name}")
                removed_files.append(file_name)
                try:
                    os.remove(file_path)
                    print(f"Deleted blank image file: {file_name}")
                except Exception as e:
                    print(f"Error while deleting blank file: {e}")
            else:
                kept_files.append(file_name)
        jpg_files = kept_files
        print(f"Pages remaining after blank removal: {len(jpg_files)} (removed: {len(removed_files)})")

    # If we have no results, treat as failure
    if not success or not jpg_files:
        print("Scan failed; removing temporary directory.")
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass
        return None
    
    print(f"\nScan completed: {len(jpg_files)} pages")
    
    # PDF conversion (only when file_format is PDF)
    pdf_created = False
    pdf_path = None
    
    if cfg.get('file_format', '').upper() == 'PDF':
        app_tmp_dir = Path(__file__).resolve().parent.parent / 'tmp'
        pdf_path = app_tmp_dir / f"{config_name}-{timestamp}.pdf"
        print(f"Starting PDF conversion for {len(jpg_files)} page images...")
        if convert_images_to_pdf(tmp_dir, pdf_path):
            # Verify that the PDF was created correctly
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                print(f"Created PDF: {pdf_path}")
                pdf_created = True
                
                pdf_size = os.path.getsize(pdf_path) / 1024
                print(f"Created PDF file: {pdf_path.name} ({pdf_size:.1f} KB)")
            else:
                print(f"Error: PDF file not created or has size 0: {pdf_path}")
        else:
            print("PDF conversion failed")
    
    # Upload to cloud (unless --no-upload was specified)
    if upload_to_nextcloud and success:
        uploader = get_uploader_from_config()
        if pdf_created and pdf_path:
            print("\nUploading PDF to cloud...")
            upload_success = uploader.upload_pdf(str(pdf_path))
            if upload_success:
                print("Upload to cloud completed")
                # After successful upload, we can safely delete the temp directory
                try:
                    shutil.rmtree(tmp_dir)
                    print(f"Deleted temporary directory: {tmp_dir}")
                except Exception as e:
                    print(f"Error while deleting temporary directory: {e}")
        else:
            # No PDF, upload the JPEG files instead
            print("\nUploading image files to cloud...")
            upload_success = uploader.upload_directory(str(tmp_dir))
            if upload_success:
                print("Upload to cloud completed")
    else:
        print("\nUpload to cloud was skipped")
    
    if success:
        return tmp_dir
    else:
        return None

def single_scan_with_scanimage(output_path: str, config_name: str, upload_to_nextcloud=True):
    """
    Run a single-page scan with scanimage.
    :param output_path: output file path
    :param config_name: configuration name in mode.json
    :param upload_to_nextcloud: whether to upload to the cloud
    :return: True on success, False otherwise
    """
    configs = load_scan_configs()
    if config_name not in configs:
        print(f"Error: configuration '{config_name}' is not defined in mode.json")
        return False
    
    cfg = configs[config_name]
    
    # Scan settings
    scanner_cfg = load_scanner_config()
    device_name = scanner_cfg["device_name"]
    resolution = cfg.get('resolution', 200)
    mode = cfg.get('mode', 'Color').lower()
    
    # Determine output format (only supported formats)
    format_map = {
        'jpg': 'jpeg',
        'jpeg': 'jpeg',
        'png': 'png',
        'tiff': 'tiff',
        'pnm': 'pnm'
    }
    
    ext = output_path.split('.')[-1].lower()
    format = format_map.get(ext, 'jpeg')  # default to jpeg for unsupported extensions
    
    print(f"Starting single-page scan with config: {config_name}")
    print(f"Output format: {format}")
    
    # Use ScannerManager
    scanner = ScannerManager.get_instance()
    
    # Warm up the scanner
    if not scanner.warm_up_scanner():
        print("Error: failed to warm up the scanner")
        return False
    
    scan_success = False
    try:
        # Build and run scanimage command via shell
        # source is taken from mode.json, with scanner.json default as fallback
        source = cfg.get('source', scanner_cfg.get('default_source', 'ADF Duplex'))

        cmd_parts = [
            f'scanimage --device="{device_name}"',
            f'--resolution={resolution}',
            f'--mode={mode}',
            f'--format={format}',
            f'--swdeskew=yes',
            f'--swcrop=yes',
            f'--source="{source}"'
        ]

        # For A4-fixed single-page scans, use page_width_mm/page_height_mm in mode.json
        page_width_mm = cfg.get('page_width_mm')
        page_height_mm = cfg.get('page_height_mm')
        if page_width_mm:
            cmd_parts.append(f'--page-width={page_width_mm}')
        if page_height_mm:
            cmd_parts.append(f'--page-height={page_height_mm}')
        else:
            # Default height for non-long-paper single scans
            cmd_parts.append('--page-height=512')

        cmd_parts.append(f'-o {output_path}')
        cmd_str = " ".join(cmd_parts)
        
        print(f"Executing command: {cmd_str}")
        
        # Run via shell (30-second timeout)
        result = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Scan error: {result.stderr}")
            return False
        
        print(f"Scan succeeded: {output_path}")
        scan_success = True
        
        # Upload to cloud (unless --no-upload was specified)
        if upload_to_nextcloud and scan_success:
            uploader = get_uploader_from_config()
            print("\nUploading file to cloud...")
            upload_success = uploader.upload_file(output_path)
            if upload_success:
                print("Upload to cloud completed")
        else:
            print("\nUpload to cloud was skipped")
        
        return scan_success
    
    except subprocess.TimeoutExpired:
        print("Scan process timed out; it may still have succeeded.")
        # Check whether the file was actually created
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            print(f"Scan output file exists: {output_path}")
            return True
        return False
    except Exception as e:
        print(f"Exception while running single-page scan: {e}")
        return False

def find_scanner():
    import sane
    sane.init()
    # Search for devices whose model name contains ix500 and usb
    devices = [dev for dev in sane.get_devices() 
              if 'ix500' in dev[1].lower() and 'usb' in dev[1].lower()]
    if devices:
        return devices[0][0]
    return None

class ScannerManager:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ScannerManager()
        return cls._instance
    
    def __init__(self):
        scanner_cfg = load_scanner_config()
        self.device_name = scanner_cfg["device_name"]
        # Store lowercase keywords for detection logic
        self.vendor_keyword = str(scanner_cfg.get("vendor_keyword", "")).lower()
        self.model_keyword = str(scanner_cfg.get("model_keyword", "")).lower()
        self.initialized = False
        self.scanner_process = None
        self.available = True
        
    def check_scanner_available(self):
        """
        Check whether the scanner is available.
        """
        try:
            # Use `scanimage -L` to detect scanners
            list_cmd = "scanimage -L"
            result = subprocess.run(list_cmd, shell=True, capture_output=True, text=True, timeout=15)
            
            stdout = result.stdout or ""
            stdout_lower = stdout.lower()

            # If the configured device name already appears, treat it as found.
            if result.returncode == 0 and self.device_name in stdout:
                print(f"Scanner found: {self.device_name}")
                return True

            print("Scanner not found by exact device_name. Available scanners:")
            print(stdout)

            # Try to find a device whose name/description contains the configured keywords.
            # This allows switching to a different scanner by only changing scanner.json.
            try:
                import re

                # scanimage -L output typically has lines like:
                # device `fujitsu:ScanSnap iX500:17872' is a FUJITSU ScanSnap iX500 scanner
                candidates = []
                for line in stdout.splitlines():
                    m = re.search(r"device `([^']+)'", line)
                    if not m:
                        continue
                    dev_name = m.group(1)
                    line_lower = line.lower()
                    dev_lower = dev_name.lower()
                    candidates.append((dev_name, line_lower, dev_lower))

                for dev_name, line_lower, dev_lower in candidates:
                    # If keywords are configured, require both to match either device name or description.
                    if self.vendor_keyword and self.model_keyword:
                        if (self.vendor_keyword in dev_lower or self.vendor_keyword in line_lower) and (
                            self.model_keyword in dev_lower or self.model_keyword in line_lower
                        ):
                            print("Detected scanner by vendor/model keywords; updating device name")
                            self.device_name = dev_name
                            print(f"New device name: {self.device_name}")
                            return True

                # No keyword-based match found. Fall back to the first discovered device, if any.
                if candidates:
                    print("No keyword match found; falling back to first discovered device.")
                    self.device_name = candidates[0][0]
                    print(f"Fallback device name: {self.device_name}")
                    return True

            except Exception as e_inner:
                print(f"Error while parsing scanimage output: {e_inner}")

            # As a last resort, fall back to the configured device name.
            print(f"Falling back to configured device name: {self.device_name}")
            return True
        except Exception as e:
            print(f"Error while detecting scanner: {e}")
            print(f"Using configured scanner: {self.device_name}")
            return True
        
    def warm_up_scanner(self):
        """Warm up the scanner so it is ready to use."""
        try:
            print("Warming up scanner...")
            
            # First check that the scanner exists
            has_scanner = self.check_scanner_available()
            if not has_scanner:
                print("Scanner not found.")
                return False
            
            # Run a small test scan (no output) to wake up the device
            test_cmd = f'scanimage --device="{self.device_name}" -n'
            print(f"Scanner test command: {test_cmd}")
            
            try:
                test_result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True, timeout=10)
                
                if test_result.returncode != 0:
                    print("Scanner self-test failed:")
                    print("stderr: " + test_result.stderr)
                    print("stdout: " + test_result.stdout)
                    print("There may be an issue with the scanner connection; continuing anyway...")
                else:
                    print("Scanner self-test succeeded. The scanner appears to be working.")
            except Exception as e:
                print(f"Error while running scanner self-test: {e}")
                print("Skipping self-test but continuing anyway...")
            
            print("Scanner warm-up completed")
            return True
        except Exception as e:
            print(f"Error while warming up scanner: {e}")
            print("The scanner may be disconnected or busy.")
            return False

def run_dry_run_check() -> bool:
    """
    Run a dry-run connectivity check without performing any real scan
    or cloud upload. This verifies:
    - scanner discovery
    - scanner warm-up / self-test
    - cloud endpoint connectivity (Nextcloud or future providers)
    """
    print("=== Dry-run: environment check ===")
    scanner = ScannerManager.get_instance()

    print("\n[Scanner detection]")
    scanner_available = scanner.check_scanner_available()
    print(f"Scanner available: {scanner_available}")

    print("\n[Scanner warm-up]")
    warm_up_ok = scanner.warm_up_scanner()
    print(f"Scanner warm-up: {warm_up_ok}")

    print("\n[Cloud connectivity]")
    try:
        try:
            from .nextcloud import test_nextcloud_connection
        except ImportError:
            from lib.nextcloud import test_nextcloud_connection

        cloud_ok = test_nextcloud_connection()
    except Exception as e:
        print(f"Cloud connectivity check error: {e}")
        cloud_ok = False
    print(f"Cloud connectivity: {cloud_ok}")

    all_ok = scanner_available and warm_up_ok and cloud_ok
    print("\n[Summary]")
    print(f"Scanner: {'OK' if scanner_available else 'NG'} / "
          f"Warm-up: {'OK' if warm_up_ok else 'NG'} / "
          f"Cloud: {'OK' if cloud_ok else 'NG'}")
    return all_ok


def run_dry_run_single_scan(config_name: str) -> bool:
    """
    Run a single-page dry-run scan:
    - Uses the specified mode for resolution/mode/source
    - Forces A4 single-sided scan
    - Saves exactly one page under tmp/DRYRUN-YYYYMMDDHHMMSS/
    - Does NOT perform any upload or deletion
    """
    print(f"=== Dry-run: single test scan (mode={config_name}) ===")

    configs = load_scan_configs()
    if config_name not in configs:
        print(f"Error: configuration '{config_name}' is not defined in mode.json")
        return False

    cfg = configs[config_name]
    scanner_cfg = load_scanner_config()
    device_name = scanner_cfg["device_name"]
    resolution = cfg.get("resolution", 200)
    mode = cfg.get("mode", "Color")
    if isinstance(mode, str) and mode:
        mode = mode[0].upper() + mode[1:].lower()
    else:
        mode = "Color"
    source = cfg.get("source", scanner_cfg.get("default_source", "ADF Duplex"))

    scanner = ScannerManager.get_instance()
    print("\n[Scanner warm-up]")
    if not scanner.warm_up_scanner():
        print("Error: failed to warm up the scanner for dry-run single scan")
        return False

    # Create dedicated dry-run tmp directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    base_tmp = Path(__file__).resolve().parent.parent / "tmp"
    tmp_dir = base_tmp / f"DRYRUN-{timestamp}"
    os.makedirs(tmp_dir, exist_ok=True)
    output_path = tmp_dir / f"{config_name}-dryrun-1.jpg"

    print("\n[Scan command]")
    cmd_parts = [
        f'scanimage --device="{device_name}"',
        f"--resolution={resolution}",
        f"--mode={mode}",
        "--format=jpeg",
        f'--source="{source}"',
        f"--page-width={A4_PAGE_WIDTH_MM}",
        f"--page-height={A4_PAGE_HEIGHT_MM}",
    ]

    # Optional software options, mirroring batch_scan_with_scanimage where reasonable
    if cfg.get("swdeskew"):
        cmd_parts.append("--swdeskew=yes")
    if cfg.get("swcrop"):
        cmd_parts.append("--swcrop=yes")
    if cfg.get("ald"):
        cmd_parts.append("--ald=yes")

    cmd_parts.append(f"-o {output_path}")
    cmd_str = " ".join(cmd_parts)
    print(f"Executing command: {cmd_str}")

    try:
        result = subprocess.run(
            cmd_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout:
            print("\nscanimage stdout:")
            print(result.stdout)
        if result.stderr:
            print("\nscanimage stderr:")
            print(result.stderr)

        if result.returncode != 0:
            print(f"Dry-run scan failed with status {result.returncode}")
            return False
    except subprocess.TimeoutExpired:
        print("Dry-run scan process timed out.")
        # fall through to file existence check
    except Exception as e:
        print(f"Exception during dry-run single scan: {e}")
        return False

    if not os.path.exists(output_path):
        print(f"Error: expected output file was not created: {output_path}")
        return False

    size = os.path.getsize(output_path)
    if size <= 0:
        print(f"Error: output file is empty: {output_path}")
        return False

    print("\n[Result]")
    print(f"Dry-run scan succeeded.")
    print(f"- output directory: {tmp_dir}")
    print(f"- output file     : {output_path.name} ({size / 1024:.1f} KB)")
    print("No upload or deletion was performed (dry-run mode).")
    return True


def check_keypad_daemon_running():
    """
    Check whether the keypad daemon process appears to be running.
    Returns a tuple of (running: bool, matched_lines: list[str]).
    """
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout or ""
        lines = stdout.splitlines()
        matched = []
        for line in lines:
            if "keypad_daemon.py" in line or "app/keypad_daemon.py" in line:
                matched.append(line)
        return (len(matched) > 0, matched)
    except Exception as e:
        print(f"Error while checking daemon status: {e}")
        return (False, [])


def run_health_check() -> bool:
    """
    Run a health check for:
    - available scanners
    - configured scanner connectivity
    - cloud connectivity
    - keypad daemon status
    Returns True if all mandatory checks are OK, otherwise False.
    """
    print("=== Health Check ===")
    print("")

    # 1) List available scanners
    scanners_ok = False
    print("[Scanners]")
    try:
        scanners_text = get_scanner_list()
        if scanners_text:
            lines = [ln for ln in scanners_text.splitlines() if ln.strip()]
            if lines:
                for line in lines:
                    print(f"- {line}")
                scanners_ok = True
            else:
                print("Scanners: NG (no scanners detected)")
        else:
            print("Scanners: NG (no scanners detected)")
    except Exception as e:
        print(f"Scanners: NG (failed to run 'scanimage -L': {e})")
    print("")

    # 2) Configured scanner connectivity via ScannerManager
    configured_ok = False
    print("[Configured scanner]")
    try:
        scanner = ScannerManager.get_instance()
        print(f"device_name: {scanner.device_name}")
        available = scanner.check_scanner_available()
        warm_up_ok = scanner.warm_up_scanner()
        configured_ok = bool(available and warm_up_ok)
        print(f"reachable: {str(configured_ok).lower()}")
    except Exception as e:
        print(f"reachable: false (error during scanner check: {e})")
    print("")

    # 3) Cloud connectivity
    cloud_ok = True
    print("[Cloud]")
    provider = "<unknown>"
    endpoint = "<unknown>"

    try:
        raw = _load_upload_config_raw()
        provider = str(raw.get("provider", "nextcloud"))
        if provider == "nextcloud":
            cfg = load_nextcloud_config()
            endpoint = cfg.get("endpoint", "<missing-endpoint>")
            try:
                try:
                    from .nextcloud import test_nextcloud_connection
                except ImportError:
                    from lib.nextcloud import test_nextcloud_connection

                reachable = bool(test_nextcloud_connection())
            except Exception as e:
                print(f"reachable: false (error during cloud check: {e})")
                reachable = False
            print(f"provider: {provider}")
            print(f"endpoint: {endpoint}")
            if reachable:
                print("reachable: true")
            else:
                print("reachable: false")
            cloud_ok = reachable
        else:
            endpoint_cfg = raw.get(provider, {})
            if isinstance(endpoint_cfg, dict):
                endpoint = str(endpoint_cfg.get("endpoint", "<unknown-endpoint>"))
            print(f"provider: {provider}")
            print(f"endpoint: {endpoint}")
            print("reachable: N/A (provider not supported for health check)")
            # Treat unsupported providers as neutral (do not fail overall health)
            cloud_ok = True
    except FileNotFoundError:
        print("provider: <missing>")
        print("endpoint: <missing>")
        print("reachable: false (upload.json not found)")
        cloud_ok = False
    except Exception as e:
        print(f"provider: {provider}")
        print(f"endpoint: {endpoint}")
        print(f"reachable: false (error while reading upload config: {e})")
        cloud_ok = False
    print("")

    # 4) Keypad daemon status
    print("[Daemon]")
    daemon_running, daemon_lines = check_keypad_daemon_running()
    print(f"running: {str(daemon_running).lower()}")
    if daemon_lines:
        # Show at most first two lines to avoid flooding output
        for line in daemon_lines[:2]:
            print(f"process: {line}")
        if len(daemon_lines) > 2:
            print(f"... ({len(daemon_lines) - 2} more processes)")
    print("")

    all_ok = bool(scanners_ok and configured_ok and cloud_ok and daemon_running)
    print("[Summary]")
    print(
        f"scanners: {'OK' if scanners_ok else 'NG'} / "
        f"configured: {'OK' if configured_ok else 'NG'} / "
        f"cloud: {'OK' if cloud_ok else 'NG'} / "
        f"daemon: {'OK' if daemon_running else 'NG'}"
    )
    return all_ok


def main(argv=None):
    import argparse

    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Scan documents with scanimage and save the result")
    parser.add_argument("config", nargs='?', help="Configuration name in mode.json (e.g. receipt)")
    parser.add_argument("--output", help="Output file path for single-page scan (e.g. output.png)")
    parser.add_argument("--list", action="store_true", help="List available scanners")
    parser.add_argument("--no-upload", action="store_true", help="Skip uploading to cloud")
    parser.add_argument(
        "--dump-config",
        metavar="MODE",
        help="Dump effective scan and upload configuration for the given mode",
    )
    parser.add_argument(
        "--dry-run",
        choices=["check", "scan"],
        help="Run in dry-run mode: 'check' for environment check, 'scan' for single-page test scan",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Run health check for scanner, cloud, and daemon",
    )

    args = parser.parse_args(argv)

    try:
        if args.health:
            # Health check cannot be combined with other operational flags.
            if args.dry_run or args.dump_config or args.list or args.output or args.config:
                print("Error: --health cannot be combined with other scan options.", file=sys.stderr)
                return 1
            ok = run_health_check()
            return 0 if ok else 1

        if args.dry_run:
            # Dry-run cannot be combined with other operational flags.
            if args.dump_config or args.list or args.output:
                print("Error: --dry-run cannot be combined with --dump-config, --list, or --output.", file=sys.stderr)
                return 1
            if args.dry_run == "check":
                if args.config:
                    print("Error: --dry-run check must not be combined with a config name.", file=sys.stderr)
                    return 1
                ok = run_dry_run_check()
                return 0 if ok else 1
            if args.dry_run == "scan":
                if not args.config:
                    print("Error: --dry-run scan requires a config name.", file=sys.stderr)
                    return 1
                ok = run_dry_run_single_scan(args.config)
                return 0 if ok else 1

        if args.dump_config:
            if args.config or args.output:
                print("Error: --dump-config cannot be combined with other scan options.", file=sys.stderr)
                return 1
            try:
                text = dump_config(args.dump_config)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1
            print(text)
            return 0
        if args.list:
            # List scanners
            scanners = get_scanner_list()
            print(f"Available scanners:\n{scanners}")
            return 0
        if args.output and args.config:
            # Single-page mode
            success = single_scan_with_scanimage(args.output, args.config, not args.no_upload)
            return 0 if success else 1
        if args.config:
            # Batch scan mode
            result = batch_scan_with_scanimage(args.config, not args.no_upload)
            return 0 if result else 1

        parser.print_help()
        return 0
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
