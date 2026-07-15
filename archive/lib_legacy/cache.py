#!/usr/bin/env python3
"""
Directory cache for DiskMan.
Provides efficient caching of directory scans to avoid redundant os.walk() calls.
"""
import os
from .utils import is_hidden, start_spinner, stop_spinner


class DirectoryCache:
    """Cache for directory contents with hierarchical size calculation."""
    
    def __init__(self):
        self.scan_root = None  # The root directory we scanned from
        self.cache = {}        # {directory_path: [(name, size, is_dir, is_hidden), ...]}
        self.sizes = {}        # {path: size} for all files and directories
    
    def scan_directory_tree(self, root_path):
        """
        Deep scan from root, caching all directories and calculating sizes efficiently.
        Uses a single os.walk() pass with bottom-up size aggregation.
        """
        self.cache = {}
        self.sizes = {}
        self.scan_root = os.path.abspath(root_path)
        
        start_spinner(f"Deep scanning {os.path.basename(root_path)}...")
        
        # First pass: collect all file sizes and directory structure
        dir_contents = {}  # {dir_path: [(name, path, is_dir), ...]}
        
        try:
            for dirpath, dirnames, filenames in os.walk(self.scan_root):
                dir_contents[dirpath] = []
                
                # Add files
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        if not os.path.islink(file_path):
                            self.sizes[file_path] = os.path.getsize(file_path)
                        else:
                            self.sizes[file_path] = 0
                    except (OSError, PermissionError):
                        self.sizes[file_path] = 0
                    dir_contents[dirpath].append((filename, file_path, False))
                
                # Add directories (sizes calculated later)
                for dirname in dirnames:
                    dir_path = os.path.join(dirpath, dirname)
                    dir_contents[dirpath].append((dirname, dir_path, True))
        except (OSError, PermissionError):
            pass
        
        # Second pass: calculate directory sizes bottom-up
        # Sort by depth (deepest first) to ensure children are processed before parents
        sorted_dirs = sorted(dir_contents.keys(), key=lambda x: x.count(os.sep), reverse=True)
        
        for dirpath in sorted_dirs:
            dir_size = 0
            items = []
            
            for name, item_path, is_dir in dir_contents[dirpath]:
                try:
                    if is_dir:
                        # Size should already be calculated (bottom-up)
                        size = self.sizes.get(item_path, 0)
                    else:
                        size = self.sizes.get(item_path, 0)
                    
                    is_hidden_item = is_hidden(item_path)
                    items.append((name, size, is_dir, is_hidden_item))
                    dir_size += size
                except (OSError, PermissionError):
                    pass
            
            # Store directory size
            self.sizes[dirpath] = dir_size
            
            # Sort by size (largest first) and cache
            items.sort(key=lambda x: x[1], reverse=True)
            self.cache[dirpath] = items
        
        stop_spinner()
        return self.cache.get(self.scan_root, [])
    
    def get_directory(self, dir_path):
        """
        Get cached directory contents.
        Returns None if not cached (caller should trigger rescan).
        """
        abs_path = os.path.abspath(dir_path)
        return self.cache.get(abs_path)
    
    def is_in_scope(self, dir_path):
        """
        Check if path is within the scan root.
        Returns True if we can use cached data.
        """
        if self.scan_root is None:
            return False
        
        abs_path = os.path.abspath(dir_path)
        # Path is in scope if it's the scan root or a subdirectory of it
        return abs_path == self.scan_root or abs_path.startswith(self.scan_root + os.sep)
    
    def invalidate(self):
        """Clear the cache completely."""
        self.cache = {}
        self.sizes = {}
        self.scan_root = None
    
    def remove_item(self, item_path):
        """
        Remove a specific item from cache and update parent sizes.
        More efficient than full rescan after delete.
        """
        abs_path = os.path.abspath(item_path)
        item_size = self.sizes.get(abs_path, 0)
        parent_dir = os.path.dirname(abs_path)
        item_name = os.path.basename(abs_path)
        
        # Remove from sizes
        if abs_path in self.sizes:
            del self.sizes[abs_path]
        
        # Remove from cache if it's a directory
        if abs_path in self.cache:
            del self.cache[abs_path]
        
        # Remove from parent's cached contents
        if parent_dir in self.cache:
            self.cache[parent_dir] = [
                item for item in self.cache[parent_dir] 
                if item[0] != item_name
            ]
        
        # Update parent sizes up the tree
        current = parent_dir
        while current and self.is_in_scope(current):
            if current in self.sizes:
                self.sizes[current] -= item_size
            current = os.path.dirname(current)
            if current == os.path.dirname(current):  # Reached root
                break
    
    def get_scan_root(self):
        """Get the current scan root path."""
        return self.scan_root


# Global cache instance
_directory_cache = DirectoryCache()


def get_cache():
    """Get the global directory cache instance."""
    return _directory_cache
