#!/usr/bin/env python3
"""
File operations for DiskMan V3.
"""
import os
import shutil
import datetime
import sys
from .utils import get_size, is_hidden, start_spinner, stop_spinner
from .cache import get_cache
from colorama import Fore, Style

# Try to import send2trash for safe deletion
try:
    from send2trash import send2trash
    TRASH_AVAILABLE = True
except ImportError:
    TRASH_AVAILABLE = False


def list_directory_cached(directory, force_rescan=False):
    """List directory contents using cache when possible."""
    cache = get_cache()
    abs_dir = os.path.abspath(directory)
    
    if not force_rescan and cache.is_in_scope(abs_dir):
        cached_items = cache.get_directory(abs_dir)
        if cached_items is not None:
            return cached_items, True
    
    items = cache.scan_directory_tree(abs_dir)
    return items, False


def delete_item(item_path, use_trash=True):
    """Delete a file or directory.
    
    Args:
        item_path: Path to delete
        use_trash: If True, move to trash (if available). If False, permanent delete.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        name = os.path.basename(item_path)
        is_dir = os.path.isdir(item_path)
        
        if use_trash and TRASH_AVAILABLE:
            start_spinner(f"Moving to Trash: {name}...")
            send2trash(item_path)
            stop_spinner()
            return True, "Moved to Trash"
        else:
            if is_dir:
                start_spinner(f"Permanently deleting directory: {name}...")
                shutil.rmtree(item_path)
            else:
                start_spinner(f"Permanently deleting file: {name}...")
                os.remove(item_path)
            stop_spinner()
            return True, "Permanently deleted"
    except Exception as e:
        stop_spinner()
        return False, str(e)


def copy_item(source_path, dest_path, progress_callback=None):
    """Copy a file or directory to destination."""
    try:
        name = os.path.basename(source_path)
        
        if os.path.isdir(dest_path):
            dest_path = os.path.join(dest_path, name)
        
        if os.path.isdir(source_path):
            start_spinner(f"Copying directory: {name}...")
            shutil.copytree(source_path, dest_path)
        else:
            start_spinner(f"Copying file: {name}...")
            _copy_with_progress(source_path, dest_path)
        
        stop_spinner()
        return True, dest_path
    except Exception as e:
        stop_spinner()
        return False, str(e)


def move_item(source_path, dest_path):
    """Move a file or directory to destination."""
    try:
        name = os.path.basename(source_path)
        
        if os.path.isdir(dest_path):
            dest_path = os.path.join(dest_path, name)
        
        start_spinner(f"Moving: {name}...")
        shutil.move(source_path, dest_path)
        stop_spinner()
        return True, dest_path
    except Exception as e:
        stop_spinner()
        return False, str(e)


def _copy_with_progress(source_path, dest_path):
    """Copy file with progress display."""
    file_size = os.path.getsize(source_path)
    
    with open(source_path, 'rb') as fsrc:
        with open(dest_path, 'wb') as fdst:
            copied = 0
            chunk_size = 1024 * 1024  # 1MB
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk:
                    break
                fdst.write(chunk)
                copied += len(chunk)


def get_item_details(item_path):
    """Get detailed information about a file or directory."""
    try:
        name = os.path.basename(item_path)
        size = get_size(item_path)
        is_dir = os.path.isdir(item_path)
        
        stats = os.stat(item_path)
        created_time = datetime.datetime.fromtimestamp(stats.st_ctime)
        modified_time = datetime.datetime.fromtimestamp(stats.st_mtime)
        accessed_time = datetime.datetime.fromtimestamp(stats.st_atime)
        
        details = {
            'name': name,
            'path': item_path,
            'size': size,
            'is_dir': is_dir,
            'created': created_time,
            'modified': modified_time,
            'accessed': accessed_time
        }
        
        if is_dir:
            try:
                contents = []
                for i, item in enumerate(os.listdir(item_path)):
                    if i >= 20:
                        contents.append("... (more items not shown)")
                        break
                    
                    sub_path = os.path.join(item_path, item)
                    sub_is_dir = os.path.isdir(sub_path)
                    sub_size = get_size(sub_path)
                    
                    contents.append({
                        'name': item,
                        'is_dir': sub_is_dir,
                        'size': sub_size
                    })
                
                details['contents'] = contents
                details['item_count'] = len(os.listdir(item_path))
            except (OSError, PermissionError):
                details['contents'] = ["Error: Unable to access directory contents"]
        
        return details
    except (OSError, PermissionError) as e:
        print(f"{Fore.RED}Error getting item details: {e}{Style.RESET_ALL}")
        return None


def get_file_preview(file_path, max_lines=10):
    """Get preview of text file contents."""
    try:
        # Check if it's likely a text file
        text_extensions = {'.txt', '.md', '.py', '.js', '.json', '.html', '.css', 
                          '.xml', '.yml', '.yaml', '.sh', '.bat', '.log', '.csv',
                          '.ini', '.cfg', '.conf', '.toml'}
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in text_extensions:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= max_lines:
                        lines.append(f"... ({max_lines} lines shown)")
                        break
                    lines.append(line.rstrip())
                return {'type': 'text', 'content': lines}
        
        # Image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
        if ext in image_extensions:
            size = os.path.getsize(file_path)
            return {'type': 'image', 'size': size, 'format': ext[1:].upper()}
        
        # Video files
        video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v'}
        if ext in video_extensions:
            size = os.path.getsize(file_path)
            return {'type': 'video', 'size': size, 'format': ext[1:].upper()}
        
        # Audio files
        audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.m4a', '.ogg'}
        if ext in audio_extensions:
            size = os.path.getsize(file_path)
            return {'type': 'audio', 'size': size, 'format': ext[1:].upper()}
        
        return {'type': 'binary', 'size': os.path.getsize(file_path)}
    
    except Exception as e:
        return {'type': 'error', 'message': str(e)}


def invalidate_cache():
    """Invalidate the directory cache."""
    get_cache().invalidate()


def remove_from_cache(item_path):
    """Remove an item from cache."""
    get_cache().remove_item(item_path)


def get_cache_scan_root():
    """Get the current cache scan root."""
    return get_cache().get_scan_root()


def parse_selection(selection_str, max_items):
    """Parse selection string like '1,3,5' or '1-5' or '1-3,7,9' into indices."""
    indices = set()
    
    parts = selection_str.replace(' ', '').split(',')
    
    for part in parts:
        if '-' in part:
            try:
                start, end = part.split('-')
                start = int(start) - 1  # Convert to 0-indexed
                end = int(end) - 1
                for i in range(start, end + 1):
                    if 0 <= i < max_items:
                        indices.add(i)
            except ValueError:
                pass
        else:
            try:
                idx = int(part) - 1  # Convert to 0-indexed
                if 0 <= idx < max_items:
                    indices.add(idx)
            except ValueError:
                pass
    
    return sorted(list(indices))


def export_report(directory, items, output_path=None):
    """Export directory analysis to CSV."""
    import csv
    from datetime import datetime
    
    if output_path is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(os.path.expanduser('~'), f'diskman_report_{timestamp}.csv')
    
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Size (bytes)', 'Size (human)', 'Type', 'Hidden', 'Path'])
            
            for name, size, is_dir, is_hid, mtime in items:
                import humanize
                item_path = os.path.join(directory, name)
                writer.writerow([
                    name,
                    size,
                    humanize.naturalsize(size),
                    'Directory' if is_dir else 'File',
                    'Yes' if is_hid else 'No',
                    item_path
                ])
        
        return True, output_path
    except Exception as e:
        return False, str(e)
