#!/usr/bin/env python3
"""
Bookmarks system for DiskMan V2.
"""
import os
import json

BOOKMARKS_FILE = os.path.expanduser('~/.diskman_bookmarks.json')


def load_bookmarks():
    """Load bookmarks from file."""
    try:
        if os.path.exists(BOOKMARKS_FILE):
            with open(BOOKMARKS_FILE, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return []


def save_bookmarks(bookmarks):
    """Save bookmarks to file."""
    try:
        with open(BOOKMARKS_FILE, 'w') as f:
            json.dump(bookmarks, f, indent=2)
        return True
    except IOError:
        return False


def add_bookmark(path):
    """Add a directory to bookmarks."""
    bookmarks = load_bookmarks()
    abs_path = os.path.abspath(path)
    
    if abs_path in bookmarks:
        return False, "Already bookmarked"
    
    bookmarks.append(abs_path)
    if save_bookmarks(bookmarks):
        return True, f"Bookmark #{len(bookmarks)} added"
    return False, "Failed to save bookmark"


def remove_bookmark(index):
    """Remove a bookmark by index (1-based)."""
    bookmarks = load_bookmarks()
    
    if 1 <= index <= len(bookmarks):
        removed = bookmarks.pop(index - 1)
        save_bookmarks(bookmarks)
        return True, f"Removed: {os.path.basename(removed)}"
    return False, "Invalid bookmark number"


def get_bookmark(index):
    """Get bookmark path by index (1-based)."""
    bookmarks = load_bookmarks()
    
    if 1 <= index <= len(bookmarks):
        return bookmarks[index - 1]
    return None


def list_bookmarks():
    """Get all bookmarks with their indices."""
    bookmarks = load_bookmarks()
    return [(i + 1, path) for i, path in enumerate(bookmarks)]
