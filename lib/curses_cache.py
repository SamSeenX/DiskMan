import os
import sys
import shutil
import threading
import subprocess
import queue
import time
from .cache import DirectoryCache

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
    return calculate_dir_size_python(path)


class CursesDirectoryCache(DirectoryCache):
    """DuDirectoryCache that calculates subdirectory sizes one-by-one with request deduplication."""
    def __init__(self):
        super().__init__()
        self.scanned_directories = set()
        self.queue = queue.Queue()
        self.cache_updated = False
        # Use RLock (Reentrant Lock) to prevent self-deadlocks
        self.cache_updated_lock = threading.RLock()
        self.calculating_dirs_lock = threading.RLock()
        self.calculating_dirs = set()
        self.scan_start_time = None
        
        # Start worker threads
        self.workers = []
        for _ in range(4):
            t = threading.Thread(target=self._worker, daemon=True)
            t.start()
            self.workers.append(t)
            
    def _worker(self):
        while True:
            try:
                task = self.queue.get()
                if task is None:
                    break
                task()
            except Exception:
                pass
            finally:
                self.queue.task_done()
                
    def submit(self, fn):
        self.queue.put(fn)

    def shutdown(self):
        # Clear queue and stop workers
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                break
        for _ in self.workers:
            self.queue.put(None)

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
                                    if self.scan_start_time is None:
                                        self.scan_start_time = time.time()
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
                        if not self.calculating_dirs:
                            self.scan_start_time = None
                    
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
            
            self.submit(make_task(path))

        return self._apply_filters_and_sort(self.cache[self.scan_root])


du_cache = CursesDirectoryCache()
