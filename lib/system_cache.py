#!/usr/bin/env python3
"""
System cache detection for DiskMan V2.
Detects common cache/temp folders based on OS.
"""
import os
import sys
import shutil
from .utils import get_size, start_spinner, stop_spinner, is_hidden

# macOS cache locations
MACOS_CACHE_PATHS = [
    ("~/Library/Caches", "App Caches - Application cache data"),
    ("~/Library/Logs", "System Logs - Application log files"),
    ("~/Library/Application Support/Google/Chrome/Default/Cache", "Chrome Cache"),
    ("~/Library/Application Support/Firefox/Profiles", "Firefox Cache/Profiles"),
    ("~/Library/Safari", "Safari Data"),
    ("~/Library/Containers/com.apple.Safari/Data/Library/Caches", "Safari Cache"),
    ("~/.npm", "NPM Cache - Node.js packages"),
    ("~/.yarn/cache", "Yarn Cache - Node.js packages"),
    ("~/Library/Developer/Xcode/DerivedData", "Xcode Derived Data - Build artifacts"),
    ("~/Library/Developer/Xcode/Archives", "Xcode Archives - Old app builds"),
    ("~/Library/Developer/CoreSimulator/Caches", "iOS Simulator Cache"),
    ("~/.gradle/caches", "Gradle Cache - Java/Android builds"),
    ("~/.m2/repository", "Maven Cache - Java dependencies"),
    ("~/Library/Application Support/Code/Cache", "VS Code Cache"),
    ("~/Library/Application Support/Slack/Cache", "Slack Cache"),
    ("~/Library/Application Support/Discord/Cache", "Discord Cache"),
    ("~/Library/Application Support/Spotify/PersistentCache", "Spotify Cache"),
    ("~/.docker", "Docker Data"),
    ("/tmp", "System Temp - Temporary files"),
    ("~/Downloads", "Downloads Folder"),
    ("~/.Trash", "Trash - Files pending deletion"),
]

# Windows cache locations
WINDOWS_CACHE_PATHS = [
    ("%TEMP%", "User Temp - Temporary files"),
    ("%LOCALAPPDATA%\\Temp", "Local Temp"),
    ("%LOCALAPPDATA%\\Microsoft\\Windows\\INetCache", "Internet Cache"),
    ("%LOCALAPPDATA%\\Google\\Chrome\\User Data\\Default\\Cache", "Chrome Cache"),
    ("%LOCALAPPDATA%\\Mozilla\\Firefox\\Profiles", "Firefox Cache"),
    ("%LOCALAPPDATA%\\npm-cache", "NPM Cache"),
    ("%APPDATA%\\Code\\Cache", "VS Code Cache"),
    ("%USERPROFILE%\\Downloads", "Downloads Folder"),
    ("C:\\Windows\\Temp", "System Temp"),
]

# Linux cache locations
LINUX_CACHE_PATHS = [
    ("~/.cache", "User Cache - Application cache data"),
    ("~/.local/share/Trash", "Trash - Files pending deletion"),
    ("/tmp", "System Temp - Temporary files"),
    ("/var/tmp", "Var Temp - Persistent temp files"),
    ("~/.npm", "NPM Cache"),
    ("~/.yarn/cache", "Yarn Cache"),
    ("~/.gradle/caches", "Gradle Cache"),
    ("~/.m2/repository", "Maven Cache"),
    ("~/.config/google-chrome/Default/Cache", "Chrome Cache"),
    ("~/.mozilla/firefox", "Firefox Data"),
    ("~/.config/Code/Cache", "VS Code Cache"),
    ("~/Downloads", "Downloads Folder"),
]


def get_cache_paths():
    """Get cache paths for current OS."""
    if sys.platform == 'darwin':
        return MACOS_CACHE_PATHS
    elif sys.platform == 'win32':
        return WINDOWS_CACHE_PATHS
    else:
        return LINUX_CACHE_PATHS


def expand_path(path):
    """Expand path with environment variables and home directory."""
    path = os.path.expandvars(path)
    path = os.path.expanduser(path)
    return path


def scan_cache_folders():
    """Scan system cache folders and return sizes.
    
    Returns: list of (path, name, description, size, exists)
    """
    start_spinner("Scanning system cache folders...")
    
    results = []
    paths = get_cache_paths()
    
    for path_template, description in paths:
        path = expand_path(path_template)
        name = os.path.basename(path) or path
        
        if os.path.exists(path):
            try:
                size = get_size(path)
                results.append((path, name, description, size, True))
            except (OSError, PermissionError):
                results.append((path, name, description, 0, True))
        else:
            results.append((path, name, description, 0, False))
    
    # Sort by size (largest first), only existing folders
    results = [r for r in results if r[4]]  # Only existing
    results.sort(key=lambda x: x[3], reverse=True)
    
    stop_spinner()
    return results


def clear_folder(path, keep_folder=True):
    """Clear contents of a folder.
    
    Args:
        path: Folder path to clear
        keep_folder: If True, delete contents but keep the folder itself
    
    Returns:
        tuple: (success, message, bytes_freed)
    """
    try:
        if not os.path.exists(path):
            return False, "Folder not found", 0
        
        if not os.path.isdir(path):
            return False, "Not a directory", 0
        
        bytes_freed = 0
        errors = []
        
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            try:
                item_size = get_size(item_path)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
                bytes_freed += item_size
            except (OSError, PermissionError) as e:
                errors.append(f"{item}: {e}")
        
        if errors:
            return True, f"Cleared with {len(errors)} errors", bytes_freed
        return True, "Cleared successfully", bytes_freed
    
    except Exception as e:
        return False, str(e), 0
