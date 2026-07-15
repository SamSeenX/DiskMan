#!/usr/bin/env python3
"""
DiskMan V4 Curses - Zero-Dependency polished TUI using native curses.
"""
import os
import sys
import curses
import humanize
import platform
import subprocess
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import shutil

__version__ = "4.2.2-curses"

# Import V2/V3 modules for filesystem actions and bookmarks
import lib.utils
from lib.utils import (
    open_file_explorer,
    detect_terminal,
    get_size,
    is_hidden
)
from lib.file_operations import (
    delete_item,
    get_item_details,
    copy_item,
    move_item,
    export_report
)
from lib.bookmarks import (
    add_bookmark,
    remove_bookmark,
    get_bookmark,
    list_bookmarks
)
from lib.system_cache import scan_cache_folders, clear_folder
from lib.cache import DirectoryCache
import lib.cache

# Silence the spinners from writing raw output to stdout during curses execution
lib.utils.start_spinner = lambda *args, **kwargs: None
lib.utils.stop_spinner = lambda *args, **kwargs: None
lib.utils.update_spinner_folder = lambda *args, **kwargs: None

# Detect du
HAS_DU = shutil.which('du') is not None

def calculate_dir_size_python(path):
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
    except OSError:
        pass
    return total


def get_single_dir_size(path):
    """Calculate size of a single directory using du or fallback python walker."""
    if HAS_DU:
        try:
            cmd = ['du', '-s', '-k', path]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            if proc.returncode == 0:
                parts = proc.stdout.strip().split('\t', 1)
                if len(parts) >= 1:
                    return int(parts[0]) * 1024
        except Exception:
            pass
    # Fallback
    return calculate_dir_size_python(path)


class CursesDirectoryCache(DirectoryCache):
    """DuDirectoryCache that calculates subdirectory sizes one-by-one with request deduplication."""
    def __init__(self):
        super().__init__()
        self.scanned_directories = set()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.cache_updated = False
        # Use RLock (Reentrant Lock) to prevent self-deadlocks
        self.cache_updated_lock = threading.RLock()
        self.calculating_dirs_lock = threading.RLock()
        self.calculating_dirs = set()

    def set_update_flag(self):
        with self.cache_updated_lock:
            self.cache_updated = True

    def check_and_clear_update_flag(self):
        with self.cache_updated_lock:
            if self.cache_updated:
                self.cache_updated = False
                return True
            return False

    def scan_directory_tree(self, root_path):
        self.scan_root = os.path.realpath(root_path)
        self.scanned_directories.add(self.scan_root)
        
        items = []
        needs_size_calc = []
        
        try:
            for entry in os.scandir(self.scan_root):
                try:
                    name = entry.name
                    path = os.path.realpath(entry.path)
                    is_dir = entry.is_dir(follow_symlinks=False)
                    is_hid = name.startswith('.')
                    stat = entry.stat(follow_symlinks=False)
                    mtime = stat.st_mtime
                    
                    if is_dir:
                        if path in self.sizes and self.sizes[path] >= 0:
                            size = self.sizes[path]
                        else:
                            size = -1
                            # Deduplicate background tasks: only scan if not already in progress
                            with self.calculating_dirs_lock:
                                if path not in self.calculating_dirs:
                                    self.calculating_dirs.add(path)
                                    needs_size_calc.append(path)
                    else:
                        size = stat.st_size
                        self.sizes[path] = size
                    
                    self.mtimes[path] = mtime
                    items.append((name, size, is_dir, is_hid, mtime))
                except (OSError, PermissionError):
                    pass
        except (OSError, PermissionError):
            pass
            
        self.cache[self.scan_root] = self._apply_filters_and_sort(items)
        self.sizes[self.scan_root] = sum(item[1] for item in items if item[1] >= 0)

        # Submit individual size calculations one-by-one to ThreadPoolExecutor
        for path in needs_size_calc:
            def make_task(p):
                def task():
                    sz = get_single_dir_size(p)
                    self.sizes[p] = sz
                    
                    # Remove from active calculation tracking
                    with self.calculating_dirs_lock:
                        if p in self.calculating_dirs:
                            self.calculating_dirs.remove(p)
                    
                    target_dir = os.path.dirname(p)
                    with self.cache_updated_lock:
                        curr_items = self.cache.get(target_dir, [])
                        if curr_items:
                            updated = []
                            for name, size, is_dir, is_hid, mtime in curr_items:
                                item_path = os.path.realpath(os.path.join(target_dir, name))
                                if item_path == p:
                                    updated.append((name, sz, is_dir, is_hid, mtime))
                                else:
                                    updated.append((name, size, is_dir, is_hid, mtime))
                            
                            self.cache[target_dir] = self._apply_filters_and_sort(updated)
                            
                            # Only trigger UI refresh if the finished calculation matches current visible path
                            if target_dir == self.scan_root:
                                self.sizes[self.scan_root] = sum(item[1] for item in updated if item[1] >= 0)
                                self.cache_updated = True # Direct assignment since we already hold the lock
                return task
            
            self.executor.submit(make_task(path))

        return self._apply_filters_and_sort(self.cache[self.scan_root])


du_cache = CursesDirectoryCache()
lib.cache._directory_cache = du_cache

SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

# Visual Theme Definitions
THEMES = [
    ("Neon Cyan", curses.COLOR_CYAN, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_CYAN),
    ("Classic Amber", curses.COLOR_YELLOW, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_YELLOW),
    ("Hacker Green", curses.COLOR_GREEN, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_GREEN),
    ("Royal Purple", curses.COLOR_MAGENTA, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_MAGENTA),
    ("Sweet Pink", curses.COLOR_MAGENTA, curses.COLOR_WHITE, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA),
    ("Sunset Orange", curses.COLOR_YELLOW, curses.COLOR_WHITE, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_RED, curses.COLOR_YELLOW),
    ("Sleek Gray", curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_WHITE)
]

THEME_CACHE_DIR = os.path.expanduser("~/.diskman")
THEME_CACHE_FILE = os.path.join(THEME_CACHE_DIR, "theme")


def save_theme_cache(theme_idx):
    """Save the selected theme index to a persistent hidden ~/.diskman directory file."""
    try:
        os.makedirs(THEME_CACHE_DIR, exist_ok=True)
        with open(THEME_CACHE_FILE, "w") as f:
            f.write(str(theme_idx))
    except Exception:
        pass


def load_theme_cache():
    """Load the saved theme index from persistent hidden ~/.diskman directory file."""
    try:
        if os.path.exists(THEME_CACHE_FILE):
            with open(THEME_CACHE_FILE, "r") as f:
                idx = int(f.read().strip())
                if 0 <= idx < len(THEMES):
                    return idx
    except Exception:
        pass
    return 0


def apply_theme(theme_idx):
    """Dynamically updates the color pairs in memory to switch visual themes on the fly."""
    theme = THEMES[theme_idx]
    _, dir_col, file_col, low_col, med_col, high_col, border_col = theme
    curses.init_pair(1, dir_col, -1)   # Folders / Cyan titles
    curses.init_pair(2, file_col, -1)  # Standard files / text
    curses.init_pair(3, low_col, -1)   # Green / low ratio space
    curses.init_pair(4, med_col, -1)   # Yellow highlights / medium ratio
    curses.init_pair(5, high_col, -1)  # Red warning / high ratio space
    curses.init_pair(6, border_col, -1) # Panel border colors


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}


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


def check_and_install_pillow(stdscr):
    """Verifies Pillow library exists, installing it via pip if missing."""
    try:
        import PIL
        from PIL import Image
        return True
    except ImportError:
        height, width = stdscr.getmaxyx()
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(height - 3, 2, "📦 Pillow missing. Installing Pillow library via pip... Please wait...", curses.color_pair(4))
        stdscr.attroff(curses.A_BOLD)
        stdscr.refresh()
        
        import sys
        import subprocess
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
    import shutil
    
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


def draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg=None):
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    # Minimum terminal size check
    if height < 15 or width < 70:
        stdscr.addstr(0, 0, "Terminal too small!", curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(1, 0, f"Current: {width}x{height}. Minimum: 70x15.", curses.color_pair(2))
        stdscr.refresh()
        return scroll_offset

    # Border attribute (Dimmed Border color pair)
    border_attr = curses.color_pair(6) | curses.A_DIM

    # Split Column calculation (Left pane is 70% width)
    split_col = int(width * 0.70)

    # Safe drawing helper wrapper to suppress curses ERR code when writing to the bottom-right character
    def safe_addstr(y, x, s, attr=curses.A_NORMAL):
        try:
            stdscr.addstr(y, x, s, attr)
        except curses.error:
            pass

    # Draw horizontal borders
    safe_addstr(0, 0, '┌' + '─' * (width - 2) + '┐', border_attr)
    # Row 5 becomes a full-width divider separator, giving padding space below the column headers
    safe_addstr(3, 0, '├' + '─' * (split_col - 1) + '┬' + '─' * (width - split_col - 2) + '┤', border_attr)
    safe_addstr(5, 0, '├' + '─' * (split_col - 1) + '┼' + '─' * (width - split_col - 2) + '┤', border_attr)
    safe_addstr(height - 4, 0, '├' + '─' * (split_col - 1) + '┴' + '─' * (width - split_col - 2) + '┤', border_attr)
    safe_addstr(height - 1, 0, '└' + '─' * (width - 2) + '┘', border_attr)

    # Draw vertical border columns
    safe_addstr(1, 0, '│', border_attr)
    safe_addstr(1, width - 1, '│', border_attr)
    safe_addstr(2, 0, '│', border_attr)
    safe_addstr(2, width - 1, '│', border_attr)

    for y in range(4, height - 4):
        safe_addstr(y, 0, '│', border_attr)
        safe_addstr(y, split_col, '│', border_attr)
        safe_addstr(y, width - 1, '│', border_attr)

    safe_addstr(height - 3, 0, '│', border_attr)
    safe_addstr(height - 3, width - 1, '│', border_attr)
    safe_addstr(height - 2, 0, '│', border_attr)
    safe_addstr(height - 2, width - 1, '│', border_attr)

    # Top Header Box
    stdscr.attron(curses.A_BOLD)
    safe_addstr(1, 2, f" DISKMAN V4 CURSES  (V{__version__}) │ Sort: {du_cache.sort_mode.upper()} ", curses.color_pair(1))
    stdscr.attroff(curses.A_BOLD)

    # Check if there are active calculating directories in cache
    is_scanning = False
    with du_cache.calculating_dirs_lock:
        if du_cache.calculating_dirs:
            is_scanning = True

    spinner_char = SPINNER_FRAMES[spinner_frame]
    status_text = f"[ {spinner_char} SCANNING... ]" if is_scanning else "[ ✓ SCAN COMPLETE ]"
    status_color = curses.color_pair(4) if is_scanning else curses.color_pair(3)

    status_x = width - len(status_text) - 3
    if status_x > 35: # Make sure it doesn't overlap title on very narrow screens
        safe_addstr(1, status_x, status_text, status_color | curses.A_BOLD)
    
    # Path line inside header box
    safe_addstr(2, 2, "📁 ", curses.color_pair(1))
    max_path_len = width - 8
    path_display = current_dir
    if len(path_display) > max_path_len:
        path_display = "..." + path_display[-max_path_len+3:]
    safe_addstr(2, 5, path_display, curses.color_pair(2) | curses.A_BOLD)

    # Headers for columns (Drawn at row 4, with line separation at row 5)
    col_idx_w = 4
    col_size_w = 11
    col_bar_w = 12
    col_type_w = 6
    col_name_w = split_col - col_idx_w - col_size_w - col_bar_w - col_type_w - 4 # Spacing padding

    headers = (
        f"{'#':<{col_idx_w}} "
        f"{'Name':<{col_name_w}} "
        f"{'Ratio Bar':<{col_bar_w}} "
        f"{'Size':<{col_size_w}} "
        f"{'Type':<{col_type_w}}"
    )
    safe_addstr(4, 2, headers[:split_col - 3], curses.color_pair(1) | curses.A_BOLD)

    # Total space calculated so far
    total_size = sum(item[1] for item in items if item[1] >= 0)

    # Left Pane Directory/File Listing (Starts at row 6, height is shifted down for padding room)
    list_height = height - 10
    total_items = len(items)
    
    if selected_idx >= scroll_offset + list_height:
        scroll_offset = selected_idx - list_height + 1
    elif selected_idx < scroll_offset:
        scroll_offset = selected_idx
    scroll_offset = max(0, min(scroll_offset, total_items - list_height))

    spinner_char = SPINNER_FRAMES[spinner_frame]

    for i in range(list_height):
        item_idx = scroll_offset + i
        if item_idx >= total_items:
            break
        
        name, size, is_dir, is_hid, mtime = items[item_idx]
        
        # Calculate visual ratio progress bar
        pct = 0.0
        if size >= 0 and total_size > 0:
            pct = (size / total_size) * 100
        
        bar_len = 6
        filled = int((pct / 100) * bar_len)
        bar_str = f"[{'█' * filled}{'░' * (bar_len - filled)}]"
        
        # Size string configuration with dynamic spinner indicator
        if size == -1:
            size_str = f"{spinner_char} Sizing"
            pct_str = "  ~ "
            bar_str = f"[{spinner_char * bar_len}]"
        else:
            size_str = humanize.naturalsize(size)
            pct_str = f"{pct:.0f}%"

        # Percentage color scaling
        if pct > 25:
            pct_color = curses.color_pair(5) # Red
        elif pct > 10:
            pct_color = curses.color_pair(4) # Yellow
        else:
            pct_color = curses.color_pair(3) # Green

        type_str = "📁" if is_dir else "📄"
        
        # Draw columns sequentially with formatting constraints (Starts at row 6 now)
        y_pos = 6 + i
        safe_addstr(y_pos, 2, f"{item_idx+1:<{col_idx_w}}", curses.color_pair(4))
        
        # Highlights selection row
        row_attr = curses.A_REVERSE | curses.A_BOLD if item_idx == selected_idx else curses.A_NORMAL
        item_color = curses.color_pair(1) if is_dir else curses.color_pair(2)
        if item_idx == selected_idx:
            item_color = curses.color_pair(1) # selected style
        
        display_name = name[:col_name_w - 2]
        safe_addstr(y_pos, 2 + col_idx_w + 1, f"{display_name:<{col_name_w}}", item_color | row_attr)
        
        # Progress Bar and details columns
        bar_col = 2 + col_idx_w + 1 + col_name_w + 1
        safe_addstr(y_pos, bar_col, bar_str, border_attr)
        safe_addstr(y_pos, bar_col + bar_len + 3, pct_str, pct_color)
        
        size_col = bar_col + col_bar_w + 1
        safe_addstr(y_pos, size_col, f"{size_str:<{col_size_w}}", pct_color)
        
        type_col = size_col + col_size_w + 1
        safe_addstr(y_pos, type_col, f"{type_str:<{col_type_w}}", item_color)

    # Right Pane: Detailed Metadata Inspector Panel
    right_pane_width = width - split_col - 3
    right_pane_x = split_col + 2

    # Draw Pane Header (Drawn at row 4, with divider at row 5)
    safe_addstr(4, right_pane_x, " INSPECTOR ", curses.color_pair(1) | curses.A_BOLD)

    if total_items > 0 and selected_idx < total_items:
        name, size, is_dir, is_hid, mtime = items[selected_idx]
        full_path = os.path.realpath(os.path.join(current_dir, name))

        # Visual lines inside inspector panel (Formatted compactly on a single line per attribute, starting at row 6)
        lines = [
            ("Name", name, curses.color_pair(1) if is_dir else curses.color_pair(2)),
            ("Type", "Directory 📁" if is_dir else "File 📄", curses.color_pair(4)),
            ("Size", humanize.naturalsize(size) if size >= 0 else "Calculating...", curses.color_pair(3)),
            ("Bytes", f"{size:,} B" if size >= 0 else "Computing...", curses.color_pair(3)),
            ("Modified", datetime.fromtimestamp(mtime).strftime('%y-%m-%d %H:%M') if mtime > 0 else "Unknown", curses.color_pair(2))
        ]

        # Render stats metadata (Starts at row 6 now)
        current_y = 6
        for label, val, val_color in lines:
            if current_y >= height - 4:
                break
            safe_addstr(current_y, right_pane_x, f"{label}:", curses.color_pair(4) | curses.A_BOLD)
            
            val_display = str(val)
            val_x = right_pane_x + len(label) + 2
            max_val_w = right_pane_width - len(label) - 3
            if len(val_display) > max_val_w:
                val_display = val_display[:max_val_w - 3] + "..."
            
            safe_addstr(current_y, val_x, val_display, val_color)
            current_y += 1

        # Get and display top subfolders if it's a directory
        subfolders = []
        if is_dir:
            try:
                for entry in os.scandir(full_path):
                    if entry.is_dir(follow_symlinks=False):
                        if not du_cache.show_hidden and entry.name.startswith('.'):
                            continue
                        sub_path = os.path.realpath(entry.path)
                        sub_size = du_cache.sizes.get(sub_path, -1)
                        
                        # Trigger background calculation if size is unknown and not already in progress
                        if sub_size < 0:
                            with du_cache.calculating_dirs_lock:
                                if sub_path not in du_cache.calculating_dirs:
                                    du_cache.calculating_dirs.add(sub_path)
                                    def make_bg_task(p):
                                        def task():
                                            sz = get_single_dir_size(p)
                                            du_cache.sizes[p] = sz
                                            with du_cache.calculating_dirs_lock:
                                                if p in du_cache.calculating_dirs:
                                                    du_cache.calculating_dirs.remove(p)
                                            du_cache.set_update_flag()
                                        return task
                                    du_cache.executor.submit(make_bg_task(sub_path))
                        
                        subfolders.append((entry.name, sub_size))
            except Exception:
                pass
            
            # Sort subfolders by size descending (putting "Calculating..." at bottom)
            subfolders.sort(key=lambda x: (x[1] >= 0, x[1]), reverse=True)

        if is_dir and subfolders:
            if current_y + 4 < height - 4:
                # Draw divider line
                line = '├' + '─' * (width - split_col - 2) + '┤'
                safe_addstr(current_y, split_col, line, border_attr)
                current_y += 1
                
                safe_addstr(current_y, right_pane_x, " TOP SUBFOLDERS ", curses.color_pair(1) | curses.A_BOLD)
                current_y += 1
                
                # Draw divider under title
                safe_addstr(current_y, right_pane_x, '─' * (right_pane_width), border_attr)
                current_y += 1
                
                # Show up to 10 subfolders
                for sf_name, sf_sz in subfolders[:10]:
                    if current_y >= height - 4:
                        break
                    
                    sz_str = humanize.naturalsize(sf_sz) if sf_sz >= 0 else "Calculating..."
                    sz_color = curses.color_pair(3) if sf_sz >= 0 else curses.color_pair(4)
                    
                    # Truncate subfolder name if it exceeds pane width
                    max_name_w = right_pane_width - len(sz_str) - 6
                    if max_name_w < 5:
                        max_name_w = 5
                    
                    disp_name = sf_name
                    if len(disp_name) > max_name_w:
                        disp_name = disp_name[:max_name_w - 3] + "..."
                    
                    safe_addstr(current_y, right_pane_x, f"• {disp_name}", curses.color_pair(1))
                    safe_addstr(current_y, right_pane_x + right_pane_width - len(sz_str) - 1, sz_str, sz_color)
                    current_y += 1

        # Draw Divider Line and Help Card below metadata
        help_y = current_y + 1
        if help_y + 8 < height - 4:
            # Draw panel crossing horizontal line connecting vertical dividers (aligned on row)
            line = '├' + '─' * (width - split_col - 2) + '┤'
            safe_addstr(help_y, split_col, line, border_attr)
            
            safe_addstr(help_y + 1, right_pane_x, " SHORTCUTS CARD ", curses.color_pair(1) | curses.A_BOLD)
            
            # Sub-separator line under Shortcuts title
            safe_addstr(help_y + 2, right_pane_x, '─' * (right_pane_width), border_attr)
            
            shortcuts = [
                ("UP/DN", "Move cursor selection"),
                ("ENTER", "Go inside / Open file"),
                ("BKSP", "Go to parent folder"),
                ("G", "Go to folder path"),
                ("F / /", "Filter items in view"),
                ("A / B", "Add / Open Bookmarks"),
                ("T / U", "Top files / Duplicates"),
                ("W / X", "Clean Cache / Export CSV"),
                ("C / M", "Copy / Move items"),
                ("I", "Compress images"),
                ("S", "Cycle sort (Size/Name/Date)"),
                ("d / D", "Delete / Permanent Del"),
                ("V", "Cycle Color Themes"),
                ("R / Q", "Rescan Folder / Quit")
            ]
            
            for idx, (key, desc) in enumerate(shortcuts):
                row_y = help_y + 3 + idx
                if row_y >= height - 4:
                    break
                safe_addstr(row_y, right_pane_x, f"{key:<6}", curses.color_pair(4) | curses.A_BOLD)
                safe_addstr(row_y, right_pane_x + 7, desc[:right_pane_width - 8], curses.color_pair(2))
    else:
        safe_addstr(6, right_pane_x, "Empty folder", curses.color_pair(2) | curses.A_DIM)

    # Bottom Footer Actions Box
    actions_1 = "Nav: UP/DN │ Enter: Open │ Backspace: Up │ F: Filter │ A: Bookmark │ B: Bookmarks"
    actions_2 = "G: Go │ D: Del │ M: Move │ C: Copy │ I: Compress │ S: Sort │ X: Export │ T: Largest │ U: Dups │ W: Clean │ V: Theme │ Q: Quit"
    
    if status_msg:
        # Display the alert / information message
        safe_addstr(height - 3, 2, status_msg[:width-4], curses.color_pair(4) | curses.A_BOLD)
    else:
        # Display directory status
        status_text = f"Total size: {humanize.naturalsize(total_size)} │ Items: {total_items} │ {actions_1}"
        safe_addstr(height - 3, 2, status_text[:width-4], curses.color_pair(3))
        
    safe_addstr(height - 2, 2, actions_2[:width-4], curses.color_pair(4) | curses.A_BOLD)

    stdscr.refresh()
    return scroll_offset


def get_string_input(stdscr, prompt, default_val=None, autocomplete_path=False, initial_value=""):
    """Safely reads string input from user in the curses footer line with optional default fallback. Supports ESC key to cancel and TAB autocompletion."""
    height, width = stdscr.getmaxyx()
    display_prompt = prompt
    if default_val is not None:
        display_prompt = f"{prompt} [{default_val}]: "
    elif not (prompt.endswith(":") or prompt.endswith("?")):
        display_prompt = f"{prompt}: "

    # Block waiting for keys during input loop
    stdscr.timeout(-1)
    curses.curs_set(1) # Enable cursor visibility
    
    input_str = initial_value
    start_x = 2 + len(display_prompt)
    max_len = 80
    candidates_display = ""
    
    while True:
        # Clear typing row first
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(height - 3, 2, " " * (width - 4), curses.color_pair(4))
        # Clear the matches line above the input prompt
        stdscr.addstr(height - 4, 2, " " * (width - 4), curses.color_pair(2))
        
        # Draw prompt text
        stdscr.addstr(height - 3, 2, display_prompt, curses.color_pair(4))
        stdscr.attroff(curses.A_BOLD)
        
        # Draw candidates if any
        if candidates_display:
            stdscr.addstr(height - 4, 2, candidates_display[:width-4], curses.color_pair(3))
            
        # Draw typed content so far
        stdscr.addstr(height - 3, start_x, input_str, curses.color_pair(2))
        
        # Position flashing terminal cursor at end of text
        stdscr.move(height - 3, start_x + len(input_str))
        stdscr.refresh()
        
        ch = stdscr.getch()
        
        # Clear matches display on any normal keypress except TAB
        if ch != 9:
            candidates_display = ""
            
        if ch == 27: # ESCAPE key (cancel)
            input_str = None
            break
        elif ch in [10, 13]: # ENTER key (accept)
            break
        elif ch in [curses.KEY_BACKSPACE, 127, 8]: # Backspace key triggers
            if len(input_str) > 0:
                input_str = input_str[:-1]
        elif ch == 9: # TAB key (autocompletion)
            if autocomplete_path and input_str:
                path_expanded = os.path.expanduser(input_str)
                if input_str.endswith('/') or os.path.isdir(path_expanded):
                    dir_part = path_expanded
                    base_part = ""
                else:
                    dir_part = os.path.dirname(path_expanded)
                    base_part = os.path.basename(path_expanded)
                
                try:
                    if not dir_part:
                        dir_part = "."
                    dirs = []
                    for name in os.listdir(dir_part):
                        full_path = os.path.join(dir_part, name)
                        if os.path.isdir(full_path) and not name.startswith('.'):
                            if name.lower().startswith(base_part.lower()):
                                dirs.append(name)
                    
                    if len(dirs) == 1:
                        completed = dirs[0]
                        input_str = (input_str[:-len(base_part)] if base_part else input_str) + completed + "/"
                    elif len(dirs) > 1:
                        common = os.path.commonprefix(dirs)
                        if common and len(common) > len(base_part):
                            input_str = (input_str[:-len(base_part)] if base_part else input_str) + common
                        candidates_display = "Matches: " + "  ".join([d + "/" for d in sorted(dirs)])
                except Exception:
                    pass
        elif 32 <= ch <= 126: # Regular printable text characters
            if len(input_str) < max_len:
                input_str += chr(ch)
                
    curses.curs_set(0) # Hide cursor
    stdscr.timeout(100) # Restore standard non-blocking timeout
    
    if input_str is None:
        return None # Explicitly canceled
    if not input_str and default_val is not None:
        return str(default_val)
    return input_str


def show_modal_list(stdscr, title, options, draw_bg_fn):
    """Draws an interactive modal selection overlay dialog."""
    selected = 0
    height, width = stdscr.getmaxyx()
    
    if not options:
        options = ["<No items>"]
        is_empty = True
    else:
        is_empty = False
        
    while True:
        draw_bg_fn() # Draw current background
        
        # Modal dims sizing
        modal_w = min(width - 10, 60)
        modal_h = min(height - 6, len(options) + 4)
        start_y = (height - modal_h) // 2
        start_x = (width - modal_w) // 2
        
        border_attr = curses.color_pair(4) | curses.A_BOLD
        
        # Fill dialog background space with clean spaces
        for y in range(start_y, start_y + modal_h):
            for x in range(start_x, start_x + modal_w):
                try:
                    stdscr.addch(y, x, ' ', curses.color_pair(2))
                except curses.error:
                    pass
                
        # Draw framing boxes
        try:
            stdscr.addstr(start_y, start_x, '┌' + '─' * (modal_w - 2) + '┐', border_attr)
            for y in range(start_y + 1, start_y + modal_h - 1):
                stdscr.addstr(y, start_x, '│', border_attr)
                stdscr.addstr(y, start_x + modal_w - 1, '│', border_attr)
            stdscr.addstr(start_y + modal_h - 1, start_x, '└' + '─' * (modal_w - 2) + '┘', border_attr)
        except curses.error:
            pass
        
        # Title
        title_str = f" {title} "
        stdscr.addstr(start_y, start_x + (modal_w - len(title_str)) // 2, title_str, curses.color_pair(1) | curses.A_BOLD)
        
        # Draw selectable items inside frame
        list_h = modal_h - 3
        for i in range(list_h):
            idx = i
            if idx >= len(options):
                break
            opt = options[idx]
            
            # Selection Highlight
            attr = curses.A_REVERSE | curses.A_BOLD if idx == selected and not is_empty else curses.A_NORMAL
            color = curses.color_pair(1) if idx == selected else curses.color_pair(2)
            
            opt_str = str(opt)
            display_opt = opt_str[:modal_w - 6]
            stdscr.addstr(start_y + 2 + i, start_x + 3, f"{idx+1}. {display_opt:<{modal_w - 8}}", color | attr)
            
        stdscr.refresh()
        
        ch = stdscr.getch()
        if ch in [27, ord('q'), ord('Q')]: # Escape or Q closes modal
            return None
        elif ch == curses.KEY_UP:
            if selected > 0:
                selected -= 1
        elif ch == curses.KEY_DOWN:
            if selected < len(options) - 1:
                selected += 1
        elif ch in [curses.KEY_ENTER, 10, 13]: # Enter selects
            if is_empty:
                return None
            return selected


def curses_main(stdscr):
    # Setup standard locale for Unicode character rendering
    import locale
    locale.setlocale(locale.LC_ALL, '')

    # Setup curses terminal settings
    curses.use_default_colors()
    curses.curs_set(0) # Hide standard cursor block
    stdscr.keypad(True)
    stdscr.timeout(100) # Key read loop timeout in ms (non-blocking updates)

    # Initialize with saved theme from cache file
    theme_index = load_theme_cache()
    apply_theme(theme_index)

    current_dir = os.path.realpath(os.getcwd())
    selected_idx = 0
    scroll_offset = 0
    spinner_frame = 0
    status_msg = None
    status_msg_time = 0

    items = du_cache.scan_directory_tree(current_dir)

    while True:
        # Clear status message after 4 seconds
        if status_msg and time.time() - status_msg_time > 4:
            status_msg = None

        # Fetch updates from background task scans
        if du_cache.check_and_clear_update_flag():
            items = du_cache.scan_directory_tree(current_dir)

        # Advance spinner animations
        spinner_frame = (spinner_frame + 1) % len(SPINNER_FRAMES)

        scroll_offset = draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)

        try:
            ch = stdscr.getch()
        except KeyboardInterrupt:
            break

        if ch == ord('q') or ch == ord('Q'):
            break

        elif ch == curses.KEY_DOWN:
            if selected_idx < len(items) - 1:
                selected_idx += 1

        elif ch == curses.KEY_UP:
            if selected_idx > 0:
                selected_idx -= 1

        elif ch in [curses.KEY_ENTER, 10, 13]: # Enter key select
            if len(items) > 0:
                name, _, is_dir, _, _ = items[selected_idx]
                target_path = os.path.realpath(os.path.join(current_dir, name))
                if is_dir:
                    current_dir = target_path
                    items = du_cache.scan_directory_tree(current_dir)
                    selected_idx = 0
                    scroll_offset = 0
                    status_msg = None
                    stdscr.clear() # Hard refresh screen
                else:
                    # Open file explorer/editor natively
                    open_file_explorer(target_path, name)

        elif ch in [curses.KEY_BACKSPACE, 127, 8]: # Backspace (navigate up directory)
            parent = os.path.realpath(os.path.dirname(current_dir))
            if parent != current_dir:
                current_dir = parent
                items = du_cache.scan_directory_tree(current_dir)
                selected_idx = 0
                scroll_offset = 0
                status_msg = None
                stdscr.clear() # Hard refresh screen

        elif ch in [ord('g'), ord('G')]: # Go to folder path
            init_val = current_dir if current_dir.endswith('/') else current_dir + '/'
            dest = get_string_input(stdscr, "Go to folder path:", autocomplete_path=True, initial_value=init_val)
            if dest is None:
                status_msg = "ℹ️ Go-to canceled."
                status_msg_time = time.time()
            elif dest:
                expanded = os.path.realpath(os.path.expanduser(dest))
                if os.path.isdir(expanded):
                    current_dir = expanded
                    items = du_cache.scan_directory_tree(current_dir)
                    selected_idx = 0
                    scroll_offset = 0
                    status_msg = f"📂 Switched to: {expanded}"
                    status_msg_time = time.time()
                    stdscr.clear()
                else:
                    status_msg = "❌ Invalid directory path."
                    status_msg_time = time.time()

        elif ch == ord('r') or ch == ord('R'): # Force Directory Rescan
            items = du_cache.scan_directory_tree(current_dir)
            selected_idx = 0
            scroll_offset = 0
            status_msg = "🔄 Directory rescan triggered."
            status_msg_time = time.time()
            stdscr.clear() # Hard refresh screen

        elif ch in [ord('f'), ord('F'), ord('/')]: # Filter items by text query
            query = get_string_input(stdscr, "Filter query (empty to clear):")
            du_cache.set_filter(query if query else None)
            items = du_cache.scan_directory_tree(current_dir)
            selected_idx = 0
            scroll_offset = 0
            status_msg = f"🔍 Filter set to: '{query}'" if query else "🔍 Filter cleared."
            status_msg_time = time.time()

        elif ch in [ord('a'), ord('A')]: # Bookmark current folder
            success, msg = add_bookmark(current_dir)
            status_msg = f"🔖 {msg}"
            status_msg_time = time.time()

        elif ch in [ord('b'), ord('B')]: # View and manage saved bookmarks list
            bookmarks_data = list_bookmarks()
            if not bookmarks_data:
                status_msg = "🔖 No bookmarks saved. Press 'A' to bookmark current directory."
                status_msg_time = time.time()
            else:
                bookmarks = [path for _, path in bookmarks_data]
                def draw_bg():
                    draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)
                
                sel_idx = show_modal_list(stdscr, "Select Bookmark", bookmarks, draw_bg)
                if sel_idx is not None:
                    target = bookmarks[sel_idx]
                    if os.path.isdir(target):
                        current_dir = target
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = 0
                        scroll_offset = 0
                        status_msg = f"🔖 Jumped to: {target}"
                        status_msg_time = time.time()
                        stdscr.clear() # Hard refresh screen

        elif ch in [ord('s'), ord('S')]: # Cycle sort options
            sort_mode = du_cache.cycle_sort()
            items = du_cache.scan_directory_tree(current_dir)
            selected_idx = 0
            scroll_offset = 0
            status_msg = f"🔀 Sort mode changed to: {sort_mode.upper()}"
            status_msg_time = time.time()

        elif ch in [ord('t'), ord('T')]: # Show largest files in the tree
            files = du_cache.get_largest_files(current_dir, limit=20)
            if not files:
                status_msg = "⚠️ No files found."
                status_msg_time = time.time()
            else:
                options = [f"{humanize.naturalsize(f[2]):<10} │ {f[1]} ({f[5]})" for f in files]
                def draw_bg():
                    draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)
                
                sel_idx = show_modal_list(stdscr, "Largest Files", options, draw_bg)
                if sel_idx is not None:
                    target_file = files[sel_idx][0]
                    target_dir = os.path.dirname(target_file)
                    if os.path.isdir(target_dir):
                        current_dir = os.path.realpath(target_dir)
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = 0
                        for idx, item in enumerate(items):
                            if item[0] == os.path.basename(target_file):
                                selected_idx = idx
                                break
                        scroll_offset = 0
                        stdscr.clear() # Hard refresh screen

        elif ch in [ord('u'), ord('U')]: # Find duplicate files
            dups = du_cache.find_duplicates(current_dir)
            if not dups:
                status_msg = "✅ No duplicates found."
                status_msg_time = time.time()
            else:
                options = [f"{humanize.naturalsize(d['wasted']):<10} wasted │ {d['count']} files of {humanize.naturalsize(d['size'])}" for d in dups]
                def draw_bg():
                    draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)
                
                sel_idx = show_modal_list(stdscr, "Duplicates", options, draw_bg)
                if sel_idx is not None:
                    group = dups[sel_idx]
                    dup_paths = group['files']
                    dup_options = [f"Focus: {os.path.basename(p)} ({os.path.dirname(p)})" for p in dup_paths]
                    
                    sel_path_idx = show_modal_list(stdscr, "Duplicate Group Details", dup_options, draw_bg)
                    if sel_path_idx is not None:
                        target_file = dup_paths[sel_path_idx]
                        target_dir = os.path.dirname(target_file)
                        if os.path.isdir(target_dir):
                            current_dir = os.path.realpath(target_dir)
                            items = du_cache.scan_directory_tree(current_dir)
                            selected_idx = 0
                            for idx, item in enumerate(items):
                                if item[0] == os.path.basename(target_file):
                                    selected_idx = idx
                                    break
                            scroll_offset = 0
                            stdscr.clear() # Hard refresh screen

        elif ch in [ord('w'), ord('W')]: # Wipe System Cache / temp folders
            cache_folders = scan_cache_folders()
            options = [f"{humanize.naturalsize(c[3]):<10} │ {c[2]} ({c[0]})" for c in cache_folders]
            def draw_bg():
                draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)
            
            sel_idx = show_modal_list(stdscr, "System Cache Cleaner", options, draw_bg)
            if sel_idx is not None:
                folder_info = cache_folders[sel_idx]
                path, name, desc, size, _ = folder_info
                confirm = get_string_input(stdscr, f"Clear all files in {name}? Type 'yes':")
                if confirm.lower() == "yes":
                    success, msg, freed = clear_folder(path)
                    if success:
                        status_msg = f"✅ Freed {humanize.naturalsize(freed)}: {msg}"
                        items = du_cache.scan_directory_tree(current_dir)
                    else:
                        status_msg = f"❌ Error: {msg}"
                    status_msg_time = time.time()

        elif ch == ord('v'): # Cycle color themes forward
            theme_index = (theme_index + 1) % len(THEMES)
            apply_theme(theme_index)
            save_theme_cache(theme_index)
            status_msg = f"🎨 Theme changed to: {THEMES[theme_index][0]}"
            status_msg_time = time.time()

        elif ch == ord('V'): # Cycle color themes backward (Shift + V)
            theme_index = (theme_index - 1) % len(THEMES)
            apply_theme(theme_index)
            save_theme_cache(theme_index)
            status_msg = f"🎨 Theme changed to: {THEMES[theme_index][0]}"
            status_msg_time = time.time()

        elif ch == ord('x') or ch == ord('X'): # Export directory CSV report
            confirm = get_string_input(stdscr, "Export CSV report? (y/n):")
            if confirm.lower() == 'y':
                success, result = export_report(current_dir, items)
                status_msg = f"📄 Exported CSV to: {result}" if success else f"❌ Export failed: {result}"
                status_msg_time = time.time()

        elif ch == ord('d'): # Delete to Trash
            if len(items) > 0:
                name, _, _, _, _ = items[selected_idx]
                path = os.path.realpath(os.path.join(current_dir, name))
                confirm = get_string_input(stdscr, f"Move '{name}' to Trash? Type 'yes' to confirm:")
                if confirm is None:
                    status_msg = "ℹ️ Delete canceled."
                    status_msg_time = time.time()
                elif confirm.lower() == 'yes':
                    success, msg = delete_item(path, use_trash=True)
                    if success:
                        status_msg = f"🗑️ Moved to Trash: '{name}'"
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = max(0, selected_idx - 1)
                    else:
                        status_msg = f"❌ Error: {msg}"
                    status_msg_time = time.time()

        elif ch == ord('D'): # Permanent delete
            if len(items) > 0:
                name, _, _, _, _ = items[selected_idx]
                path = os.path.realpath(os.path.join(current_dir, name))
                confirm = get_string_input(stdscr, f"PERMANENTLY delete '{name}'? Type 'yes' to confirm:")
                if confirm is None:
                    status_msg = "ℹ️ Delete canceled."
                    status_msg_time = time.time()
                elif confirm.lower() == 'yes':
                    success, msg = delete_item(path, use_trash=False)
                    if success:
                        status_msg = f"💥 Permanently deleted: '{name}'"
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = max(0, selected_idx - 1)
                    else:
                        status_msg = f"❌ Error: {msg}"
                    status_msg_time = time.time()

        elif ch in [ord('m'), ord('M')]: # Move selected item
            if len(items) > 0:
                name, _, _, _, _ = items[selected_idx]
                path = os.path.realpath(os.path.join(current_dir, name))
                dest = get_string_input(stdscr, f"Move '{name}' to folder path:")
                if dest is None:
                    status_msg = "ℹ️ Move canceled."
                    status_msg_time = time.time()
                elif dest and os.path.isdir(dest):
                    success, result = move_item(path, dest)
                    if success:
                        status_msg = f"🚚 Moved '{name}' to '{dest}'"
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = max(0, selected_idx - 1)
                    else:
                        status_msg = f"❌ Error: {result}"
                    status_msg_time = time.time()
                elif dest:
                    status_msg = "❌ Invalid destination path."
                    status_msg_time = time.time()

        elif ch in [ord('c'), ord('C')]: # Copy selected item
            if len(items) > 0:
                name, _, _, _, _ = items[selected_idx]
                path = os.path.realpath(os.path.join(current_dir, name))
                dest = get_string_input(stdscr, f"Copy '{name}' to folder path:")
                if dest is None:
                    status_msg = "ℹ️ Copy canceled."
                    status_msg_time = time.time()
                elif dest and os.path.isdir(dest):
                    success, result = copy_item(path, dest)
                    status_msg = f"📋 Copied '{name}' to '{dest}'" if success else f"❌ Error: {result}"
                    status_msg_time = time.time()
                elif dest:
                    status_msg = "❌ Invalid destination path."
                    status_msg_time = time.time()

        elif ch in [ord('i'), ord('I')]: # Image compression feature
            # Check Pillow dependency
            if not check_and_install_pillow(stdscr):
                status_msg = "❌ Error: Failed to import/install Pillow library."
                status_msg_time = time.time()
                continue
                
            from PIL import Image

            # Default selections wizard
            scope_input = get_string_input(stdscr, "Compress: [s]elected file, or [f]older?", default_val="f")
            if scope_input is None:
                status_msg = "ℹ️ Compression canceled."
                status_msg_time = time.time()
                continue
            
            scope = scope_input.lower()
            if scope not in ['s', 'f']:
                status_msg = "⚠️ Aborted: Invalid scope selection."
                status_msg_time = time.time()
                continue
                
            target_files = []
            target_root = None
            recursive = False
            
            if scope == 's':
                if len(items) > 0:
                    name, _, is_dir, _, _ = items[selected_idx]
                    path = os.path.realpath(os.path.join(current_dir, name))
                    if is_dir:
                        confirm_dir = get_string_input(stdscr, f"Compress images inside folder '{name}'? ([y]es/[n]o)", default_val="y")
                        if confirm_dir is None:
                            status_msg = "ℹ️ Compression canceled."
                            status_msg_time = time.time()
                            continue
                        if confirm_dir.lower() in ['y', 'yes']:
                            rec_input = get_string_input(stdscr, "Compress recursively? ([y]es/[n]o)", default_val="n")
                            if rec_input is None:
                                status_msg = "ℹ️ Compression canceled."
                                status_msg_time = time.time()
                                continue
                            recursive = rec_input.lower() in ['y', 'yes']
                            target_root = path
                            target_files = gather_images(path, recursive=recursive)
                    else:
                        if is_image_file(path):
                            target_files = [path]
                            target_root = os.path.dirname(path)
                        else:
                            status_msg = "❌ Selected file is not a supported image format."
                            status_msg_time = time.time()
                            continue
            else:
                rec_input = get_string_input(stdscr, "Compress recursively? ([y]es/[n]o)", default_val="n")
                if rec_input is None:
                    status_msg = "ℹ️ Compression canceled."
                    status_msg_time = time.time()
                    continue
                recursive = rec_input.lower() in ['y', 'yes']
                target_root = current_dir
                target_files = gather_images(current_dir, recursive=recursive)
                
            if not target_files:
                status_msg = "⚠️ No matching image files found."
                status_msg_time = time.time()
                continue
                
            out_format_input = get_string_input(stdscr, "Output format ([w]ebp/[j]peg)", default_val="j")
            if out_format_input is None:
                status_msg = "ℹ️ Compression canceled."
                status_msg_time = time.time()
                continue
            
            out_format_raw = out_format_input.lower()
            if out_format_raw in ['w', 'webp']:
                out_format = 'webp'
            elif out_format_raw in ['j', 'jpeg']:
                out_format = 'jpeg'
            else:
                status_msg = "⚠️ Aborted: Unsupported output format."
                status_msg_time = time.time()
                continue
                
            quality_str = get_string_input(stdscr, "Compression quality (1-100)", default_val="69")
            if quality_str is None:
                status_msg = "ℹ️ Compression canceled."
                status_msg_time = time.time()
                continue
            try:
                quality = int(quality_str)
                if not (1 <= quality <= 100):
                    quality = 69
            except ValueError:
                quality = 69
 
            save_style_input = get_string_input(stdscr, "Save: [o]riginals in subfolder, or [c]ompressed in subfolder? (o/c)", default_val="c")
            if save_style_input is None:
                status_msg = "ℹ️ Compression canceled."
                status_msg_time = time.time()
                continue
            
            save_style_raw = save_style_input.lower()
            if save_style_raw in ['o', 'originals']:
                save_style = 'o'
            elif save_style_raw in ['c', 'compressed']:
                save_style = 'c'
            else:
                status_msg = "⚠️ Aborted: Invalid save style option."
                status_msg_time = time.time()
                continue
            
            compression_root = None
            if recursive and save_style == 'o':
                backup_loc_input = get_string_input(stdscr, "Save originals in: [r]oot directory or [e]ach relative directory? (r/e)", default_val="e")
                if backup_loc_input is None:
                    status_msg = "ℹ️ Compression canceled."
                    status_msg_time = time.time()
                    continue
                backup_loc_raw = backup_loc_input.lower()
                if backup_loc_raw in ['r', 'root']:
                    compression_root = target_root
                elif backup_loc_raw in ['e', 'each', 'relative']:
                    compression_root = None
                else:
                    status_msg = "⚠️ Aborted: Invalid backup location option."
                    status_msg_time = time.time()
                    continue
                
            # Sort chronologically by birthtime/mtime to preserve timeline order
            target_files.sort(key=get_creation_time)
            
            total_images = len(target_files)
            compressed_count = 0
            total_saved = 0
            
            for idx, filepath in enumerate(target_files):
                # Live status indicator
                progress_msg = f"⚙️ Compressing image {idx+1}/{total_images}... ({os.path.basename(filepath)})"
                draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, progress_msg)
                
                success, saved_bytes = compress_single_image(filepath, out_format, quality, save_style=save_style, compression_root=compression_root)
                if success:
                    compressed_count += 1
                    total_saved += saved_bytes
                    
            if compressed_count > 0:
                status_msg = f"✅ Done! Compressed {compressed_count}/{total_images} images. Saved {humanize.naturalsize(total_saved)}."
                items = du_cache.scan_directory_tree(current_dir)
            else:
                status_msg = "ℹ️ Done. Original files were already smaller than compressed versions."
            status_msg_time = time.time()

        elif ch == curses.KEY_RESIZE: # Dynamically handles terminal window resizing
            stdscr.clear()


def print_exit_message():
    """Prints a beautiful, colored goodbye message upon exit."""
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
        print(f"\n{Fore.GREEN}{Style.BRIGHT}Thanks for using DiskMan V4!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Made with ❤️  by {Fore.YELLOW}{Style.BRIGHT}SamSeen{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}☕ If you found this useful: {Fore.BLUE}{Style.BRIGHT}https://buymeacoffee.com/samseen{Style.RESET_ALL}\n")
    except ImportError:
        # Fallback if colorama is not installed in runtime environment
        print("\nThanks for using DiskMan V4!")
        print("Made with ❤️  by SamSeen")
        print("☕ If you found this useful: https://buymeacoffee.com/samseen\n")


def main():
    try:
        curses.wrapper(curses_main)
    except KeyboardInterrupt:
        pass
    print_exit_message()
    sys.exit(0)


if __name__ == "__main__":
    main()
