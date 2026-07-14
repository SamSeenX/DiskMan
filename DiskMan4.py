#!/usr/bin/env python3
"""
DiskMan V4 - Fast du-based Disk Space Analyzer by SamSeen

A powerful tool to visualize and manage disk space usage with single-level, on-demand scanning,
concurrency, background prefetching, and cross-platform native fallback.
"""
import os
import sys
import time
import platform
import subprocess
import hashlib
import select
import humanize
import threading
import shutil
from concurrent.futures import ThreadPoolExecutor
from colorama import Fore, Style

__version__ = "4.0.1"

# 1. Monkey patch humanize BEFORE importing UI modules
orig_naturalsize = humanize.naturalsize
def custom_naturalsize(size, *args, **kwargs):
    if size == -1:
        return "Calculating..."
    if size == -2:
        return "Pending..."
    if size < 0:
        return "0 B"
    return orig_naturalsize(size, *args, **kwargs)
humanize.naturalsize = custom_naturalsize

# 2. Now import V2/V3 modules
from lib.utils import (
    open_file_explorer, 
    clear_screen,
    optimize_terminal_view,
    get_optimal_display_settings,
    detect_terminal,
    start_spinner,
    stop_spinner,
    update_spinner_folder,
    is_hidden
)
from lib.file_operations import (
    list_directory_cached,
    delete_item,
    get_item_details,
    remove_from_cache,
    copy_item,
    move_item,
    parse_selection,
    export_report,
    get_file_preview
)
from lib.ui import (
    display_directory,
    show_navigation_options,
    show_welcome_message,
    show_delete_confirmation,
    show_extension_stats,
    show_bookmarks,
    show_duplicates,
    show_file_preview,
    show_help,
    show_search_results,
    show_largest_files,
    show_cache_cleaner
)
from lib.system_cache import scan_cache_folders, clear_folder
from lib.bookmarks import (
    add_bookmark,
    remove_bookmark,
    get_bookmark,
    list_bookmarks
)

# Custom du-based DirectoryCache subclass
from lib.cache import DirectoryCache
import lib.cache

# Check if du is available
HAS_DU = shutil.which('du') is not None


def calculate_dir_size_python(path):
    """Fallback directory size estimator (single-threaded walker for one folder)."""
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


class DuDirectoryCache(DirectoryCache):
    """du-based Directory Cache with threading, non-blocking scans, and background prefetching."""
    
    def __init__(self):
        super().__init__()
        self.scanned_directories = set()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.prefetch_queue = []
        self.prefetch_lock = threading.Lock()
        self.cache_updated = False
        self.cache_updated_lock = threading.Lock()
        self.start_prefetch_worker()

    def set_update_flag(self):
        with self.cache_updated_lock:
            self.cache_updated = True

    def check_and_clear_update_flag(self):
        with self.cache_updated_lock:
            if self.cache_updated:
                self.cache_updated = False
                return True
            return False

    def run_du_command(self, directory):
        """Run system du command to find sizes of subdirectories."""
        sizes = {}
        try:
            cmd = ['du', '-k', '-d', '1', directory]
            if platform.system() == 'Linux':
                cmd = ['du', '-k', '--max-depth=1', directory]
            
            proc = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                timeout=10
            )
            
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    parts = line.strip().split('\t', 1)
                    if len(parts) == 2:
                        size_kb, p = parts
                        try:
                            # Use realpath to resolve all symlinks (crucial on macOS /var -> /private/var)
                            sizes[os.path.realpath(p)] = int(size_kb) * 1024
                        except ValueError:
                            pass
        except Exception:
            pass
        return sizes

    def run_python_walk_sizes(self, directory):
        """Fallback multi-threaded Python walk to get immediate subfolder sizes."""
        sizes = {}
        try:
            subdirs = []
            for entry in os.scandir(directory):
                if entry.is_dir(follow_symlinks=False):
                    subdirs.append(os.path.realpath(entry.path))
            
            # Map subdirs to size futures
            futures = {self.executor.submit(calculate_dir_size_python, sd): sd for sd in subdirs}
            for fut, sd in futures.items():
                try:
                    sizes[sd] = fut.result(timeout=10)
                except Exception:
                    sizes[sd] = 0
        except Exception:
            pass
        return sizes

    def scan_directory_tree(self, root_path):
        """Perform a concurrent, non-blocking single-level directory scan."""
        self.scan_root = os.path.realpath(root_path)
        self.scanned_directories.add(self.scan_root)
        
        # Immediate local scan using os.scandir to display folder contents fast
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
                        # Use cached size if available, otherwise set sentinel
                        if path in self.sizes and self.sizes[path] >= 0:
                            size = self.sizes[path]
                        else:
                            size = -1  # Calculating
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
            
        # Store initial listing (sorted)
        self.cache[self.scan_root] = self._apply_filters_and_sort(items)
        self.sizes[self.scan_root] = sum(item[1] for item in items if item[1] >= 0)

        # If we have directories that need sizing, compute them concurrently
        if needs_size_calc:
            def bg_scan():
                if HAS_DU:
                    sizes = self.run_du_command(self.scan_root)
                else:
                    sizes = self.run_python_walk_sizes(self.scan_root)
                
                # Merge sizes back into cached list
                updated_items = []
                for name, size, is_dir, is_hid, mtime in self.cache.get(self.scan_root, []):
                    path = os.path.realpath(os.path.join(self.scan_root, name))
                    if is_dir and size < 0:
                        new_size = sizes.get(path, 0)
                        self.sizes[path] = new_size
                        updated_items.append((name, new_size, is_dir, is_hid, mtime))
                    else:
                        updated_items.append((name, size, is_dir, is_hid, mtime))
                
                # Cache the sorted results so the largest folders jump to the top automatically!
                self.cache[self.scan_root] = self._apply_filters_and_sort(updated_items)
                self.sizes[self.scan_root] = sum(item[1] for item in updated_items if item[1] >= 0)
                
                # Signal update to UI and queue prefetching
                self.set_update_flag()
                self.queue_prefetch(list(sizes.keys()))

            # Submit and wait up to 300ms for synchronous render
            future = self.executor.submit(bg_scan)
            try:
                future.result(timeout=0.3)
            except Exception:
                # Timeout, bg_scan will update in the background
                pass

        return self._apply_filters_and_sort(self.cache[self.scan_root])

    def is_in_scope(self, dir_path):
        return os.path.realpath(dir_path) in self.cache

    def queue_prefetch(self, paths):
        """Queue subdirectories for background size prefetching."""
        with self.prefetch_lock:
            for p in paths:
                real_p = os.path.realpath(p)
                if real_p not in self.scanned_directories and real_p not in self.prefetch_queue:
                    self.prefetch_queue.append(real_p)

    def start_prefetch_worker(self):
        """Spawn background daemon worker to prefetch directory sizes."""
        def prefetch_worker():
            while True:
                path_to_scan = None
                with self.prefetch_lock:
                    if self.prefetch_queue:
                        path_to_scan = self.prefetch_queue.pop(0)
                
                if path_to_scan:
                    try:
                        if path_to_scan not in self.scanned_directories:
                            if HAS_DU:
                                sizes = self.run_du_command(path_to_scan)
                            else:
                                sizes = self.run_python_walk_sizes(path_to_scan)
                            
                            for subpath, sz in sizes.items():
                                self.sizes[subpath] = sz
                            self.scanned_directories.add(path_to_scan)
                    except Exception:
                        pass
                else:
                    time.sleep(0.2)

        t = threading.Thread(target=prefetch_worker, daemon=True)
        t.start()

    def search_files(self, search_text, dir_path=None):
        """On-demand search across all subdirectories starting from dir_path."""
        target = dir_path or self.scan_root
        if not target or not search_text:
            return []
        
        start_spinner(f"Deep searching for '{search_text}'...")
        
        search_lower = search_text.lower()
        results = []
        count = 0
        try:
            for root, dirs, files in os.walk(target):
                # Check files
                for f in files:
                    if search_lower in f.lower():
                        file_path = os.path.join(root, f)
                        try:
                            stat = os.stat(file_path)
                            size = stat.st_size
                            mtime = stat.st_mtime
                            is_hid = f.startswith('.') or any(part.startswith('.') for part in root.split(os.sep))
                            rel_path = root.replace(target, '.', 1)
                            results.append((file_path, f, size, False, is_hid, mtime, rel_path))
                            count += 1
                            if count >= 100:
                                break
                        except (OSError, PermissionError):
                            pass
                
                # Check directories
                for d in dirs:
                    if search_lower in d.lower():
                        dir_path_full = os.path.join(root, d)
                        try:
                            stat = os.stat(dir_path_full)
                            size = self.sizes.get(dir_path_full, 0)
                            mtime = stat.st_mtime
                            is_hid = d.startswith('.') or any(part.startswith('.') for part in root.split(os.sep))
                            rel_path = root.replace(target, '.', 1)
                            results.append((dir_path_full, d, size, True, is_hid, mtime, rel_path))
                            count += 1
                            if count >= 100:
                                break
                        except (OSError, PermissionError):
                            pass
                
                if count >= 100:
                    break
        except (OSError, PermissionError):
            pass
            
        results.sort(key=lambda x: x[2], reverse=True)
        stop_spinner()
        return results[:100]

    def get_largest_files(self, dir_path=None, limit=50, show_progress=True):
        """Walk the directory tree on the fly to find the largest files."""
        target = dir_path or self.scan_root
        if not target:
            return []
        
        if show_progress:
            start_spinner("Finding largest files...")
        
        results = []
        try:
            for root, dirs, files in os.walk(target):
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        stat = os.stat(file_path)
                        size = stat.st_size
                        mtime = stat.st_mtime
                        is_hid = f.startswith('.') or any(part.startswith('.') for part in root.split(os.sep))
                        rel_path = root.replace(target, '.', 1)
                        results.append((file_path, f, size, is_hid, mtime, rel_path))
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
            
        results.sort(key=lambda x: x[2], reverse=True)
        
        if show_progress:
            stop_spinner()
        return results[:limit]

    def find_duplicates(self, dir_path=None, min_size=1024):
        """Find duplicates on the fly in the target directory."""
        target = dir_path or self.scan_root
        if not target:
            return []
            
        start_spinner("Finding duplicates...")
        
        size_groups = {}
        try:
            for root, dirs, files in os.walk(target):
                for f in files:
                    file_path = os.path.join(root, f)
                    try:
                        stat = os.stat(file_path)
                        size = stat.st_size
                        if size >= min_size:
                            if size not in size_groups:
                                size_groups[size] = []
                            size_groups[size].append(file_path)
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
            
        potential_dups = {k: v for k, v in size_groups.items() if len(v) > 1}
        duplicates = []
        total_groups = len(potential_dups)
        processed = 0
        
        for size, paths in potential_dups.items():
            processed += 1
            update_spinner_folder(f"Checking {processed}/{total_groups} groups")
            
            hashes = {}
            for path in paths:
                try:
                    with open(path, 'rb') as f:
                        file_hash = hashlib.md5(f.read(65536)).hexdigest()
                    if file_hash not in hashes:
                        hashes[file_hash] = []
                    hashes[file_hash].append(path)
                except (OSError, PermissionError):
                    pass
            
            for file_hash, hash_paths in hashes.items():
                if len(hash_paths) > 1:
                    wasted = size * (len(hash_paths) - 1)
                    duplicates.append({
                        'size': size,
                        'files': hash_paths,
                        'wasted': wasted,
                        'count': len(hash_paths)
                    })
        
        duplicates.sort(key=lambda x: x['wasted'], reverse=True)
        stop_spinner()
        return duplicates

    def get_extension_stats(self, dir_path=None):
        """Get extension stats on-the-fly."""
        target = dir_path or self.scan_root
        if not target:
            return {}
            
        start_spinner("Analyzing file extensions...")
        ext_sizes = {}
        try:
            for root, dirs, files in os.walk(target):
                for f in files:
                    try:
                        stat = os.stat(os.path.join(root, f))
                        ext = os.path.splitext(f)[1].lower() or 'no extension'
                        ext_sizes[ext] = ext_sizes.get(ext, 0) + stat.st_size
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
            
        stop_spinner()
        return dict(sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True)[:15])


# Swap global cache to our optimized implementation
du_cache = DuDirectoryCache()
lib.cache._directory_cache = du_cache


def get_input_with_auto_refresh(prompt, timeout=0.2):
    """Wait for user input, but break periodically to allow UI refresh if scan finishes."""
    sys.stdout.write(prompt)
    sys.stdout.flush()
    
    # Check platform availability for select
    has_select = hasattr(select, 'select')
    
    while True:
        if has_select:
            try:
                rlist, _, _ = select.select([sys.stdin], [], [], timeout)
                if rlist:
                    return sys.stdin.readline().strip()
            except (IOError, ValueError):
                pass
        else:
            # Fallback for platforms without select on stdin
            time.sleep(timeout)
            
        # Check if background cache thread has updated
        if du_cache.check_and_clear_update_flag():
            return None


def main():
    """Main function for DiskMan V4."""
    if len(sys.argv) > 1 and sys.argv[1] in ['-v', '--version', 'version']:
        print(f"DiskMan V{__version__}")
        return

    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help', '?']:
        show_help()
        return

    try:
        from lib.updater import check_for_updates
        update_available = check_for_updates()
    except Exception:
        update_available = False

    detect_terminal()
    display_settings = get_optimal_display_settings()
    items_per_page = 20
    
    current_dir = os.getcwd()
    skip_welcome = False

    # CLI command routing
    if len(sys.argv) > 1:
        skip_welcome = True
        command = sys.argv[1].lower()
        
        if command == 'web':
            port = 5001
            if len(sys.argv) > 2 and sys.argv[2].isdigit():
                port = int(sys.argv[2])
            
            current_dir = os.getcwd()
            clear_screen()
            print(f"{Fore.GREEN}🌐 Starting DiskMan Dashboard for: {current_dir}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Press Ctrl+C to stop the server{Style.RESET_ALL}\n")
            
            # Run scan
            list_directory_cached(current_dir)
            from lib.web_server import start_dashboard
            try:
                start_dashboard(du_cache, current_dir, port=port)
            except KeyboardInterrupt:
                pass
            return

        elif command == 'clean':
            print(f"{Fore.CYAN}Starting System Cleaner...{Style.RESET_ALL}")
            show_cache_cleaner()
            return

        elif command in ['dup', 'duplicates', 'top', 'large', 'f', 'search', 'find']:
            current_dir = os.getcwd()
            list_directory_cached(current_dir) 
            
            action = None
            if command in ['dup', 'duplicates']:
                dups = du_cache.find_duplicates(current_dir)
                action = show_duplicates(dups)
            
            elif command in ['top', 'large']:
                limit = 50
                if len(sys.argv) > 2 and sys.argv[2].isdigit():
                    limit = int(sys.argv[2])
                files = du_cache.get_largest_files(current_dir, limit=limit)
                action = show_largest_files(files, current_dir)
            
            elif command in ['f', 'search', 'find']:
                if len(sys.argv) > 2:
                    query = " ".join(sys.argv[2:])
                    results = du_cache.search_files(query, current_dir)
                    action = show_search_results(results, query, current_dir)
                else:
                    print(f"{Fore.RED}Usage: diskman f <query>{Style.RESET_ALL}")
                    return
            
            if action:
                if action[0] == 'goto':
                    current_dir = action[1]
                elif action[0] == 'open':
                    open_file_explorer(action[1])
                elif action[0] == 'delete':
                    path = action[1]
                    details = get_item_details(path)
                    if details and show_delete_confirmation(details, use_trash=True):
                        success, msg = delete_item(path, use_trash=True)
                        if success:
                            print(f"{Fore.GREEN}✓ Deleted: {os.path.basename(path)}{Style.RESET_ALL}")
                            remove_from_cache(path)
                        else:
                            print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")

    # Interactive Loop
    if not skip_welcome:
        start_path = None
        if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
            start_path = os.path.abspath(sys.argv[1])
        
        if start_path:
            current_dir = start_path
        else:
            current_dir = show_welcome_message(version=__version__, update_available=update_available)

    current_page = 0
    force_rescan = False

    while True:
        if not os.path.isdir(current_dir):
            print(f"{Fore.RED}Directory not found: {current_dir}{Style.RESET_ALL}")
            current_dir = os.path.expanduser("~")
            current_page = 0
            force_rescan = True

        items, is_cached = list_directory_cached(current_dir, force_rescan=force_rescan)
        force_rescan = False

        total_items = len(items)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        current_page = max(0, min(current_page, total_pages - 1)) if total_pages > 0 else 0

        display_directory(
            current_dir, items, current_page, items_per_page,
            is_cached=is_cached,
            sort_mode=du_cache.sort_mode,
            show_hidden=du_cache.show_hidden,
            filter_text=du_cache.filter_text
        )
        
        show_navigation_options(current_page, total_pages, du_cache.show_hidden, du_cache.sort_mode)

        # Non-blocking input loop to auto-refresh UI when background scan completes
        choice = get_input_with_auto_refresh(f"\n{Fore.CYAN}> {Fore.YELLOW}")
        print(f"{Style.RESET_ALL}", end="")

        if choice is None:
            # Re-draw trigger because background scan completed
            continue

        if not choice:
            continue

        if choice == 'q':
            print(f"\n{Fore.GREEN}{Style.BRIGHT}Thanks for using DiskMan V4!{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Made with ❤️  by SamSeen{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}☕ Support: {Fore.WHITE}https://buymeacoffee.com/samseen{Style.RESET_ALL}\n")
            break

        elif choice == '?' or choice == 'help':
            show_help()

        elif choice == 'r':
            force_rescan = True

        elif choice == '~':
            current_dir = os.path.expanduser("~")
            current_page = 0

        elif choice == 'h':
            du_cache.toggle_hidden()
            continue

        elif choice == 's':
            du_cache.cycle_sort()
            continue

        elif choice.startswith('f') and not choice.startswith('F'):
            filter_text = choice[1:].strip() if len(choice) > 1 else None
            du_cache.set_filter(filter_text if filter_text else None)
            current_page = 0
            continue

        elif choice.startswith('F ') or choice.startswith('/ '):
            search_text = choice[2:].strip()
            if search_text:
                results = du_cache.search_files(search_text, current_dir)
                action = show_search_results(results, search_text, current_dir)
                if action:
                    if action[0] == 'goto':
                        current_dir = action[1]
                        current_page = 0
                    elif action[0] == 'open':
                        open_file_explorer(action[1], os.path.basename(action[1]))
                        input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice.startswith('l') and choice[1:].strip().isdigit():
            new_limit = int(choice[1:].strip())
            if 5 <= new_limit <= 50:
                items_per_page = new_limit
                current_page = 0
            else:
                print(f"\n{Fore.RED}Limit must be 5-50{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
            continue

        elif choice == '.':
            scan_root = du_cache.get_scan_root()
            if scan_root and os.path.isdir(scan_root):
                current_dir = scan_root
                current_page = 0
            else:
                print(f"\n{Fore.YELLOW}No cached scan root available{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice.startswith('..'):
            levels = 1
            suffix = choice[2:]
            if suffix == '':
                levels = 1
            elif suffix.isdigit():
                levels = int(suffix)
            elif suffix.startswith('/') and suffix[1:].isdigit():
                levels = int(suffix[1:])
            elif suffix.startswith('.'):
                levels = len(choice) - 1
            
            new_dir = current_dir
            for _ in range(levels):
                parent = os.path.dirname(new_dir)
                if parent == new_dir:
                    break
                new_dir = parent
            
            if new_dir != current_dir:
                current_dir = new_dir
                current_page = 0

        elif choice.startswith('g '):
            target = choice[2:].strip()
            if os.path.isdir(target):
                current_dir = os.path.abspath(target)
                current_page = 0
            else:
                print(f"\n{Fore.RED}Not found: {target}{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1

        elif choice.startswith('o ') and choice[2:].strip():
            sel = choice[2:].strip()
            indices = parse_selection(sel, total_items)
            if indices:
                idx = indices[0]
                name = items[idx][0]
                item_path = os.path.join(current_dir, name)
                open_file_explorer(item_path, name)
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice.startswith('d ') and choice[2:].strip():
            sel = choice[2:].strip()
            indices = parse_selection(sel, total_items)
            if indices:
                item_details = []
                for idx in indices:
                    name = items[idx][0]
                    path = os.path.join(current_dir, name)
                    details = get_item_details(path)
                    if details:
                        item_details.append(details)
                
                if item_details and show_delete_confirmation(item_details, use_trash=True):
                    for details in item_details:
                        success, msg = delete_item(details['path'], use_trash=True)
                        if success:
                            print(f"{Fore.GREEN}✓ {details['name']}: {msg}{Style.RESET_ALL}")
                            remove_from_cache(details['path'])
                        else:
                            print(f"{Fore.RED}✗ {details['name']}: {msg}{Style.RESET_ALL}")
                    force_rescan = True
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice.startswith('D ') and choice[2:].strip():
            sel = choice[2:].strip()
            indices = parse_selection(sel, total_items)
            if indices:
                item_details = []
                for idx in indices:
                    name = items[idx][0]
                    path = os.path.join(current_dir, name)
                    details = get_item_details(path)
                    if details:
                        item_details.append(details)
                
                if item_details and show_delete_confirmation(item_details, use_trash=False):
                    for details in item_details:
                        success, msg = delete_item(details['path'], use_trash=False)
                        if success:
                            print(f"{Fore.GREEN}✓ {details['name']}: {msg}{Style.RESET_ALL}")
                            remove_from_cache(details['path'])
                        else:
                            print(f"{Fore.RED}✗ {details['name']}: {msg}{Style.RESET_ALL}")
                    force_rescan = True
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice.startswith('m '):
            parts = choice[2:].strip().split(' ', 1)
            if len(parts) == 2:
                sel, dest = parts
                indices = parse_selection(sel, total_items)
                if indices and os.path.isdir(dest):
                    for idx in indices:
                        name = items[idx][0]
                        path = os.path.join(current_dir, name)
                        success, result = move_item(path, dest)
                        if success:
                            print(f"{Fore.GREEN}✓ Moved {name}{Style.RESET_ALL}")
                            remove_from_cache(path)
                        else:
                            print(f"{Fore.RED}✗ {name}: {result}{Style.RESET_ALL}")
                    force_rescan = True
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Invalid destination.{Style.RESET_ALL}")
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice.startswith('c '):
            parts = choice[2:].strip().split(' ', 1)
            if len(parts) == 2:
                sel, dest = parts
                indices = parse_selection(sel, total_items)
                if indices and os.path.isdir(dest):
                    for idx in indices:
                        name = items[idx][0]
                        path = os.path.join(current_dir, name)
                        success, result = copy_item(path, dest)
                        if success:
                            print(f"{Fore.GREEN}✓ Copied {name}{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}✗ {name}: {result}{Style.RESET_ALL}")
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Invalid destination.{Style.RESET_ALL}")
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice == 'e':
            stats = du_cache.get_extension_stats(current_dir)
            total = sum(stats.values())
            show_extension_stats(stats, total)

        elif choice.startswith('b'):
            if choice == 'b':
                bm_list = list_bookmarks()
                bm_choice = show_bookmarks(bm_list)
                if bm_choice.startswith('b') and bm_choice[1:].isdigit():
                    path = get_bookmark(int(bm_choice[1:]))
                    if path and os.path.isdir(path):
                        current_dir = path
                        current_page = 0
            elif choice == 'b+':
                success, msg = add_bookmark(current_dir)
                print(f"{Fore.GREEN if success else Fore.RED}{msg}{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
            elif choice.startswith('b-') and choice[2:].strip().isdigit():
                idx = int(choice[2:].strip())
                success, msg = remove_bookmark(idx)
                print(f"{Fore.GREEN if success else Fore.RED}{msg}{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
            elif choice[1:].isdigit():
                idx = int(choice[1:])
                path = get_bookmark(idx)
                if path and os.path.isdir(path):
                    current_dir = path
                    current_page = 0
                else:
                    print(f"{Fore.RED}Invalid bookmark.{Style.RESET_ALL}")
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice == 'x':
            success, result = export_report(current_dir, items)
            if success:
                print(f"\n{Fore.GREEN}✓ Exported to: {result}{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.RED}Export failed: {result}{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice == 'dup':
            dups = du_cache.find_duplicates(current_dir)
            action = show_duplicates(dups)
            if action:
                if action[0] == 'goto':
                    current_dir = action[1]
                    current_page = 0
                elif action[0] == 'open':
                    open_file_explorer(action[1], os.path.basename(action[1]))
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice == 'top' or choice.startswith('top '):
            limit = 20
            if choice.startswith('top ') and choice[4:].strip().isdigit():
                limit = min(100, int(choice[4:].strip()))
            
            files = du_cache.get_largest_files(current_dir, limit=limit)
            action = show_largest_files(files, current_dir)
            
            if action:
                if action[0] == 'goto':
                    current_dir = action[1]
                    current_page = 0
                elif action[0] == 'open':
                    open_file_explorer(action[1], os.path.basename(action[1]))
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
                elif action[0] == 'delete':
                    details = get_item_details(action[1])
                    if details and show_delete_confirmation(details, use_trash=True):
                        success, msg = delete_item(action[1], use_trash=True)
                        if success:
                            print(f"{Fore.GREEN}✓ Deleted: {os.path.basename(action[1])}{Style.RESET_ALL}")
                            remove_from_cache(action[1])
                            force_rescan = True
                        else:
                            print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")
                        input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice == 'clean':
            cache_folders = scan_cache_folders()
            action = show_cache_cleaner(cache_folders)
            
            if action:
                if action[0] == 'goto':
                    current_dir = action[1]
                    current_page = 0
                    force_rescan = True
                elif action[0] == 'open':
                    open_file_explorer(action[1], os.path.basename(action[1]))
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
                elif action[0] == 'clear':
                    folder_info = action[1]
                    path, name, desc, size, _ = folder_info
                    
                    print(f"\n{Fore.RED}{Style.BRIGHT}⚠️  CLEAR FOLDER CONTENTS{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}Folder: {path}{Style.RESET_ALL}")
                    print(f"{Fore.WHITE}Size: {humanize.naturalsize(size)}{Style.RESET_ALL}")
                    print(f"\n{Fore.RED}This will delete ALL contents of this folder!{Style.RESET_ALL}")
                    confirm = input(f"{Fore.RED}Type 'yes' to confirm: {Style.RESET_ALL}").strip().lower()
                    
                    if confirm == 'yes':
                        success, msg, freed = clear_folder(path)
                        if success:
                            print(f"\n{Fore.GREEN}✓ {msg} - Freed {humanize.naturalsize(freed)}{Style.RESET_ALL}")
                            if freed > 100 * 1024 * 1024:
                                print(f"{Fore.YELLOW}☕ Support: {Fore.WHITE}buymeacoffee.com/samseen{Style.RESET_ALL}")
                        else:
                            print(f"\n{Fore.RED}✗ {msg}{Style.RESET_ALL}")
                        input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice == 'web' or choice.startswith('web '):
            port = 5001
            if choice.startswith('web ') and choice[4:].strip().isdigit():
                port = int(choice[4:].strip())
            
            from lib.web_server import start_dashboard
            
            print(f"\n{Fore.GREEN}🌐 Starting DiskMan Dashboard...{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Opening: {Fore.WHITE}http://localhost:{port}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Press Ctrl+C to stop and return to CLI{Style.RESET_ALL}\n")
            
            try:
                start_dashboard(du_cache, current_dir, port=port)
            except KeyboardInterrupt:
                pass
            print(f"\n{Fore.GREEN}Dashboard stopped. Returning to CLI...{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < total_items:
                name, _, is_dir, _, _ = items[idx]
                if is_dir:
                    current_dir = os.path.join(current_dir, name)
                    current_page = 0
                else:
                    file_path = os.path.join(current_dir, name)
                    preview = get_file_preview(file_path)
                    show_file_preview(preview, file_path)
            else:
                print(f"\n{Fore.RED}Invalid selection.{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        else:
            print(f"\n{Fore.RED}Unknown command.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.GREEN}Thanks for using DiskMan V4!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}☕ Support: {Fore.WHITE}https://buymeacoffee.com/samseen{Style.RESET_ALL}")
        sys.exit(0)
