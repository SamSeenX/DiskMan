#!/usr/bin/env python3
"""
Enhanced directory cache for DiskMan V2.
Provides efficient caching with filtering, sorting, and analysis capabilities.
"""
import os
import hashlib
from datetime import datetime, timedelta
from .utils import is_hidden, start_spinner, stop_spinner, update_spinner_folder


class DirectoryCache:
    """Cache for directory contents with hierarchical size calculation and analysis."""
    
    def __init__(self):
        self.scan_root = None
        self.cache = {}        # {directory_path: [(name, size, is_dir, is_hidden, mtime), ...]}
        self.sizes = {}        # {path: size}
        self.mtimes = {}       # {path: modification_time}
        self.show_hidden = True
        self.sort_mode = 'size'  # 'size', 'name', 'date'
        self.filter_text = None
    
    def scan_directory_tree(self, root_path):
        """Deep scan from root, caching all directories with metadata."""
        self.cache = {}
        self.sizes = {}
        self.mtimes = {}
        self.scan_root = os.path.abspath(root_path)
        
        start_spinner(f"Deep scanning {os.path.basename(root_path)}...")
        
        dir_contents = {}
        
        try:
            for dirpath, dirnames, filenames in os.walk(self.scan_root):
                # Update spinner with current folder
                update_spinner_folder(dirpath)
                
                dir_contents[dirpath] = []
                
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        if not os.path.islink(file_path):
                            stat = os.stat(file_path)
                            self.sizes[file_path] = stat.st_size
                            self.mtimes[file_path] = stat.st_mtime
                        else:
                            self.sizes[file_path] = 0
                            self.mtimes[file_path] = 0
                    except (OSError, PermissionError):
                        self.sizes[file_path] = 0
                        self.mtimes[file_path] = 0
                    dir_contents[dirpath].append((filename, file_path, False))
                
                for dirname in dirnames:
                    dir_path = os.path.join(dirpath, dirname)
                    dir_contents[dirpath].append((dirname, dir_path, True))
        except (OSError, PermissionError):
            pass
        
        # Calculate directory sizes bottom-up
        sorted_dirs = sorted(dir_contents.keys(), key=lambda x: x.count(os.sep), reverse=True)
        
        for dirpath in sorted_dirs:
            dir_size = 0
            dir_mtime = 0
            items = []
            
            for name, item_path, is_dir in dir_contents[dirpath]:
                try:
                    if is_dir:
                        size = self.sizes.get(item_path, 0)
                        mtime = self.mtimes.get(item_path, 0)
                    else:
                        size = self.sizes.get(item_path, 0)
                        mtime = self.mtimes.get(item_path, 0)
                    
                    is_hidden_item = is_hidden(item_path)
                    items.append((name, size, is_dir, is_hidden_item, mtime))
                    dir_size += size
                    dir_mtime = max(dir_mtime, mtime)
                except (OSError, PermissionError):
                    pass
            
            self.sizes[dirpath] = dir_size
            self.mtimes[dirpath] = dir_mtime
            self.cache[dirpath] = items
        
        stop_spinner()
        return self._apply_filters_and_sort(self.cache.get(self.scan_root, []))
    
    def _apply_filters_and_sort(self, items):
        """Apply current filter and sort settings to items."""
        result = list(items)
        
        # Filter hidden files
        if not self.show_hidden:
            result = [item for item in result if not item[3]]
        
        # Filter by text
        if self.filter_text:
            filter_lower = self.filter_text.lower()
            result = [item for item in result if filter_lower in item[0].lower()]
        
        # Sort
        if self.sort_mode == 'size':
            result.sort(key=lambda x: x[1], reverse=True)
        elif self.sort_mode == 'name':
            result.sort(key=lambda x: x[0].lower())
        elif self.sort_mode == 'date':
            result.sort(key=lambda x: x[4], reverse=True)
        
        return result
    
    def get_directory(self, dir_path):
        """Get cached directory contents with filters applied."""
        abs_path = os.path.abspath(dir_path)
        raw_items = self.cache.get(abs_path)
        if raw_items is None:
            return None
        return self._apply_filters_and_sort(raw_items)
    
    def is_in_scope(self, dir_path):
        """Check if path is within the scan root."""
        if self.scan_root is None:
            return False
        abs_path = os.path.abspath(dir_path)
        return abs_path == self.scan_root or abs_path.startswith(self.scan_root + os.sep)
    
    def invalidate(self):
        """Clear the cache."""
        self.cache = {}
        self.sizes = {}
        self.mtimes = {}
        self.scan_root = None
    
    def remove_item(self, item_path):
        """Remove a specific item from cache."""
        abs_path = os.path.abspath(item_path)
        item_size = self.sizes.get(abs_path, 0)
        parent_dir = os.path.dirname(abs_path)
        item_name = os.path.basename(abs_path)
        
        if abs_path in self.sizes:
            del self.sizes[abs_path]
        if abs_path in self.mtimes:
            del self.mtimes[abs_path]
        if abs_path in self.cache:
            del self.cache[abs_path]
        
        if parent_dir in self.cache:
            self.cache[parent_dir] = [
                item for item in self.cache[parent_dir] 
                if item[0] != item_name
            ]
        
        current = parent_dir
        while current and self.is_in_scope(current):
            if current in self.sizes:
                self.sizes[current] -= item_size
            current = os.path.dirname(current)
            if current == os.path.dirname(current):
                break
    
    def set_filter(self, text):
        """Set filter text (None to clear)."""
        self.filter_text = text
    
    def toggle_hidden(self):
        """Toggle showing hidden files."""
        self.show_hidden = not self.show_hidden
        return self.show_hidden
    
    def cycle_sort(self):
        """Cycle through sort modes."""
        modes = ['size', 'name', 'date']
        current_idx = modes.index(self.sort_mode)
        self.sort_mode = modes[(current_idx + 1) % len(modes)]
        return self.sort_mode
    
    def get_extension_stats(self, dir_path=None):
        """Get breakdown of sizes by file extension."""
        target = dir_path or self.scan_root
        if not target:
            return {}
        
        ext_sizes = {}
        for path, size in self.sizes.items():
            if path.startswith(target) and os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower() or 'no extension'
                ext_sizes[ext] = ext_sizes.get(ext, 0) + size
        
        # Sort by size
        return dict(sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True)[:15])
    
    def get_age_color(self, mtime):
        """Get age category based on modification time."""
        if mtime == 0:
            return 'unknown'
        
        age = datetime.now() - datetime.fromtimestamp(mtime)
        if age > timedelta(days=365):
            return 'old'      # > 1 year
        elif age > timedelta(days=90):
            return 'medium'   # 3-12 months
        else:
            return 'recent'   # < 3 months
    
    def find_duplicates(self, dir_path=None):
        """Find potential duplicate files by size, then verify with hash."""
        target = dir_path or self.scan_root
        if not target:
            return []
        
        start_spinner("Scanning for duplicates...")
        
        # Group by size
        size_groups = {}
        for path, size in self.sizes.items():
            if path.startswith(target) and os.path.isfile(path) and size > 0:
                if size not in size_groups:
                    size_groups[size] = []
                size_groups[size].append(path)
        
        # Only keep groups with duplicates
        potential_dups = {k: v for k, v in size_groups.items() if len(v) > 1}
        
        duplicates = []
        for size, paths in potential_dups.items():
            # Hash first 64KB of each file
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
                    duplicates.append({
                        'size': size,
                        'files': hash_paths
                    })
        
        stop_spinner()
        return duplicates
    
    def search_files(self, search_text, dir_path=None):
        """Search for files by name across all cached subdirectories.
        
        Returns list of tuples: (full_path, name, size, is_dir, mtime, relative_path)
        """
        target = dir_path or self.scan_root
        if not target or not search_text:
            return []
        
        start_spinner(f"Searching for '{search_text}'...")
        
        search_lower = search_text.lower()
        results = []
        
        # Search through all cached paths
        for path, size in self.sizes.items():
            if not path.startswith(target):
                continue
            
            name = os.path.basename(path)
            if search_lower in name.lower():
                is_dir = os.path.isdir(path)
                mtime = self.mtimes.get(path, 0)
                is_hid = is_hidden(path)
                # Get relative path from target
                rel_path = os.path.dirname(path).replace(target, '.', 1)
                results.append((path, name, size, is_dir, is_hid, mtime, rel_path))
        
        # Sort by size (largest first)
        results.sort(key=lambda x: x[2], reverse=True)
        
        stop_spinner()
        return results[:100]  # Limit to 100 results
    
    def get_largest_files(self, dir_path=None, limit=50):
        """Get the largest files in the cached tree, sorted by size.
        
        Returns list of tuples: (full_path, name, size, mtime, relative_path)
        """
        target = dir_path or self.scan_root
        if not target:
            return []
        
        start_spinner("Finding largest files...")
        
        results = []
        
        # Get all files from cache
        for path, size in self.sizes.items():
            if not path.startswith(target):
                continue
            # Only include files, not directories
            if not os.path.isdir(path):
                name = os.path.basename(path)
                mtime = self.mtimes.get(path, 0)
                is_hid = is_hidden(path)
                rel_path = os.path.dirname(path).replace(target, '.', 1)
                results.append((path, name, size, is_hid, mtime, rel_path))
        
        # Sort by size (largest first)
        results.sort(key=lambda x: x[2], reverse=True)
        
        stop_spinner()
        return results[:limit]
    
    def get_scan_root(self):
        """Get the current scan root path."""
        return self.scan_root


# Global cache instance
_directory_cache = DirectoryCache()


def get_cache():
    """Get the global directory cache instance."""
    return _directory_cache
