#!/usr/bin/env python3
"""
File operations for DiskMan.
"""
import os
import shutil
import datetime
import sys
from .utils import get_size, is_hidden, start_spinner, stop_spinner
from .cache import get_cache
from colorama import Fore, Style

def list_directory(directory):
    """List all files and directories in the given directory with their sizes."""
    try:
        # Start spinner
        start_spinner(f"Calculating sizes in {os.path.basename(directory)}...")

        # Get all items in the directory
        items = []
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            try:
                size = get_size(item_path)
                is_dir = os.path.isdir(item_path)
                is_hidden_item = is_hidden(item_path)
                items.append((item, size, is_dir, is_hidden_item))
            except (OSError, PermissionError):
                # Skip items that can't be accessed
                pass

        # Sort by size (largest first)
        items.sort(key=lambda x: x[1], reverse=True)

        # Stop spinner
        stop_spinner()

        return items
    except (OSError, PermissionError) as e:
        # Stop spinner if there's an error
        stop_spinner()

        print(f"{Fore.RED}Error accessing directory: {e}{Style.RESET_ALL}")
        return []


def list_directory_cached(directory, force_rescan=False):
    """
    List directory contents using cache when possible.
    
    Args:
        directory: Path to the directory to list
        force_rescan: If True, always rescan even if cached
    
    Returns:
        tuple: (items list, is_cached boolean)
    """
    cache = get_cache()
    abs_dir = os.path.abspath(directory)
    
    # Check if we can use cache
    if not force_rescan and cache.is_in_scope(abs_dir):
        cached_items = cache.get_directory(abs_dir)
        if cached_items is not None:
            return cached_items, True
    
    # Need to scan - either forced, out of scope, or not cached
    items = cache.scan_directory_tree(abs_dir)
    return items, False


def invalidate_cache():
    """Invalidate the directory cache."""
    get_cache().invalidate()


def remove_from_cache(item_path):
    """Remove an item from cache (after deletion)."""
    get_cache().remove_item(item_path)


def get_cache_scan_root():
    """Get the current cache scan root."""
    return get_cache().get_scan_root()


def delete_item(item_path):
    """Delete a file or directory.

    Args:
        item_path (str): Path to the file or directory to delete

    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        if os.path.isdir(item_path):
            # Delete directory and all its contents
            start_spinner(f"Deleting directory: {os.path.basename(item_path)}...")
            shutil.rmtree(item_path)
        else:
            # Delete file
            start_spinner(f"Deleting file: {os.path.basename(item_path)}...")
            os.remove(item_path)

        stop_spinner()
        return True
    except (OSError, PermissionError) as e:
        stop_spinner()
        print(f"{Fore.RED}Error deleting item: {e}{Style.RESET_ALL}")
        return False

def get_item_details(item_path):
    """Get detailed information about a file or directory.

    Args:
        item_path (str): Path to the file or directory

    Returns:
        dict: Dictionary containing item details
    """
    try:
        # Get basic file information
        name = os.path.basename(item_path)
        size = get_size(item_path)
        is_dir = os.path.isdir(item_path)

        # Get file stats
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

        # If it's a directory, get its contents
        if is_dir:
            try:
                contents = []
                for i, item in enumerate(os.listdir(item_path)):
                    if i >= 20:  # Limit to first 20 items
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

def list_all_files_recursive(directory):
    """List all files in a directory and its subdirectories, sorted by size."""
    start_spinner(f"Scanning all files in {os.path.basename(directory)}...")
    all_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                if not os.path.islink(file_path):
                    size = os.path.getsize(file_path)
                    all_files.append((file_path, file, size))
            except (OSError, PermissionError):
                pass
    
    all_files.sort(key=lambda x: x[2], reverse=True)
    stop_spinner()
    return all_files

def _print_progress_bar(iteration, total, prefix='', suffix='', decimals=1, length=50, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()

def move_file_with_progress(source_path, destination_path):
    """Move a file from source_path to destination_path with a progress bar."""
    try:
        file_size = os.path.getsize(source_path)
        file_name = os.path.basename(source_path)
        
        if os.path.isdir(destination_path):
            destination_path = os.path.join(destination_path, file_name)

        print(f"Moving {file_name}...")
        with open(source_path, 'rb') as fsrc:
            with open(destination_path, 'wb') as fdst:
                copied = 0
                chunk_size = 1024 * 1024  # 1MB chunks
                _print_progress_bar(0, file_size, prefix='Progress:', suffix='Complete', length=50)
                while True:
                    chunk = fsrc.read(chunk_size)
                    if not chunk:
                        break
                    fdst.write(chunk)
                    copied += len(chunk)
                    _print_progress_bar(copied, file_size, prefix='Progress:', suffix='Complete', length=50)
        
        os.remove(source_path)
        print("\nMove complete.")
        return True
    except (OSError, PermissionError) as e:
        print(f"\n{Fore.RED}Error moving file: {e}{Style.RESET_ALL}")
        return False

def move_file(source_path, destination_path):
    """Move a file from source_path to destination_path."""
    return move_file_with_progress(source_path, destination_path)


