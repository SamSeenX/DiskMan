import os
import sys
import platform
import subprocess
import time
from datetime import datetime
import shutil
import curses

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}

SCANNING_MESSAGES = [
    (0, "Starting up... 🚀"),
    (1, "Counting your files... 🧛"),
    (2, "Still working... 😊"),
    (3, "This folder is bigger than expected..."),
    (4, "Wow, you really have a lot of stuff..."),
    (5, "Did you ever delete anything? 🤔"),
    (7, "I've seen smaller hard disks..."),
    (10, "Making coffee while we wait... ☕"),
    (15, "Maybe time for a snack break? 🍕"),
    (20, "I'm not stuck, it's just... you have too many files! 😅"),
    (30, "Still going... you might want to sit down 🪑"),
    (40, "This is taking forever. Literally. ⏳"),
    (50, "I'm starting to question my life choices... 🤷"),
    (60, "We're still friends, right? 🥺")
]


def get_funny_loading_message(start_time):
    if start_time is None:
        return ""
    elapsed = int(time.time() - start_time)
    message = SCANNING_MESSAGES[0][1]
    for t, msg in SCANNING_MESSAGES:
        if elapsed >= t:
            message = msg
    return message


def is_image_file(path):
    """Checks if the file extension corresponds to a supported image type."""
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS


def gather_images(directory, recursive=False):
    """Gathers all image file paths from a directory, excluding originals backups."""
    images = []
    try:
        if recursive:
            for root, dirs, files in os.walk(directory):
                # Avoid compressing the backup directory itself recursively
                if "originals" in os.path.split(root):
                    continue
                for f in files:
                    p = os.path.join(root, f)
                    if is_image_file(p):
                        images.append(os.path.realpath(p))
        else:
            for entry in os.scandir(directory):
                if entry.is_file() and is_image_file(entry.path):
                    images.append(os.path.realpath(entry.path))
    except Exception:
        pass
    return images


def get_creation_time(path):
    """Retrieves file creation time (st_birthtime on macOS/BSD, st_mtime on others)."""
    try:
        stat = os.stat(path)
        return getattr(stat, 'st_birthtime', stat.st_mtime)
    except Exception:
        return 0


def copy_creation_time_macos(src_path, dst_path):
    """Copies creation and modification dates to output file using macOS SetFile."""
    if platform.system() == 'Darwin':
        try:
            stat = os.stat(src_path)
            birthtime = getattr(stat, 'st_birthtime', None)
            if birthtime:
                dt = datetime.fromtimestamp(birthtime)
                date_str = dt.strftime("%m/%d/%Y %H:%M:%S")
                # Set creation date
                subprocess.run(["SetFile", "-d", date_str, dst_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # Set modification date
                mod_str = datetime.fromtimestamp(stat.st_mtime).strftime("%m/%d/%Y %H:%M:%S")
                subprocess.run(["SetFile", "-m", mod_str, dst_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


def check_and_install_pillow(stdscr, safe_addstr_fn):
    """Verifies Pillow library exists, installing it via pip if missing."""
    try:
        import PIL
        from PIL import Image
        return True
    except ImportError:
        height, width = stdscr.getmaxyx()
        stdscr.attron(curses.A_BOLD)
        safe_addstr_fn(height - 3, 2, "📦 Pillow missing. Installing Pillow library via pip... Please wait...", curses.color_pair(4))
        stdscr.attroff(curses.A_BOLD)
        stdscr.refresh()
        
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            import PIL
            from PIL import Image
            return True
        except Exception:
            return False


def compress_single_image(filepath, out_format, quality, save_style='o', compression_root=None):
    """Compresses a single image file, supporting backup-originals (o) or save-compressed-to-subfolder (c) modes."""
    from PIL import Image
    
    try:
        parent_dir = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        stat = os.stat(filepath)
        orig_size = stat.st_size
        
        ext = '.jpg' if out_format == 'jpeg' else '.webp'
        base_name_no_ext = os.path.splitext(filename)[0]
        
        if save_style == 'o':
            if compression_root:
                rel_dir = os.path.relpath(parent_dir, compression_root)
                if rel_dir == '.':
                    originals_dir = os.path.join(compression_root, "originals")
                else:
                    originals_dir = os.path.join(compression_root, "originals", rel_dir)
            else:
                originals_dir = os.path.join(parent_dir, "originals")
            os.makedirs(originals_dir, exist_ok=True)
            backup_path = os.path.join(originals_dir, filename)
            
            # Backup original using copy2 (preserves metadata and timestamps)
            shutil.copy2(filepath, backup_path)
            
            out_filepath = os.path.join(parent_dir, base_name_no_ext + ext)
            temp_out = out_filepath + ".tmp"
            
            with Image.open(backup_path) as img:
                if out_format == 'jpeg' and img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                img.save(temp_out, format=out_format.upper(), quality=quality)
                
            temp_size = os.path.getsize(temp_out)
            
            if temp_size < orig_size:
                # If extension changed, delete the original file first
                if os.path.realpath(filepath) != os.path.realpath(out_filepath):
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        
                shutil.move(temp_out, out_filepath)
                
                # Restore timestamps
                os.utime(out_filepath, (stat.st_atime, stat.st_mtime))
                copy_creation_time_macos(backup_path, out_filepath)
                
                return True, (orig_size - temp_size)
            else:
                # Clean up temporary output and backup copy if compression didn't save space
                if os.path.exists(temp_out):
                    os.remove(temp_out)
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                return False, 0
        else: # save_style == 'c' (Keep originals as is, save compressed in subfolder named by output format)
            subfolder_name = 'jpeg' if out_format == 'jpeg' else 'webp'
            target_dir = os.path.join(parent_dir, subfolder_name)
            os.makedirs(target_dir, exist_ok=True)
            
            out_filepath = os.path.join(target_dir, base_name_no_ext + ext)
            temp_out = out_filepath + ".tmp"
            
            with Image.open(filepath) as img:
                if out_format == 'jpeg' and img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                img.save(temp_out, format=out_format.upper(), quality=quality)
                
            temp_size = os.path.getsize(temp_out)
            
            if temp_size < orig_size:
                if os.path.exists(out_filepath):
                    os.remove(out_filepath)
                shutil.move(temp_out, out_filepath)
                
                # Restore timestamps from original
                os.utime(out_filepath, (stat.st_atime, stat.st_mtime))
                copy_creation_time_macos(filepath, out_filepath)
                
                return True, (orig_size - temp_size)
            else:
                # Clean up temporary output if compression didn't save space
                if os.path.exists(temp_out):
                    os.remove(temp_out)
                return False, 0
    except Exception:
        return False, 0
