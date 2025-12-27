
import os
import subprocess
import sys
import socket
import urllib.request
import json
from colorama import Fore, Style

def is_connected():
    """Check if device is connected to internet."""
    try:
        # Connect to 8.8.8.8 (Google DNS) on port 53 (DNS)
        # Timeout quickly (1.5s) so we don't block startup
        socket.create_connection(("8.8.8.8", 53), timeout=1.5)
        return True
    except OSError:
        pass
    return False

def get_installed_version():
    """Get the currently installed version."""
    try:
        # Import from parent - handles both git and homebrew installs
        import sys
        import os
        # Add parent directory to path if needed
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        
        from DiskMan import __version__
        return __version__
    except:
        return None

def get_latest_version():
    """Get the latest version from GitHub tags."""
    try:
        url = "https://api.github.com/repos/SamSeenX/DiskMan/tags"
        req = urllib.request.Request(url, headers={'User-Agent': 'DiskMan'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data:
                # Find the first tag that looks like a version (v*.*.*)
                import re
                for tag_info in data:
                    tag = tag_info.get('name', '')
                    # Match tags like v3.0.7 or 3.0.7
                    if re.match(r'^v?\d+\.\d+(\.\d+)?$', tag):
                        return tag.lstrip('v')
            return None
    except:
        return None

def compare_versions(v1, v2):
    """Compare two version strings. Returns: 1 if v1 > v2, -1 if v1 < v2, 0 if equal."""
    try:
        parts1 = [int(x) for x in v1.split('.')]
        parts2 = [int(x) for x in v2.split('.')]
        
        # Pad shorter version with zeros
        while len(parts1) < len(parts2):
            parts1.append(0)
        while len(parts2) < len(parts1):
            parts2.append(0)
        
        for a, b in zip(parts1, parts2):
            if a > b:
                return 1
            elif a < b:
                return -1
        return 0
    except:
        return 0

def check_for_updates():
    """
    Check for updates from GitHub releases.
    Works for both git and Homebrew installations.
    
    Returns: True if update is available, False otherwise.
    """
    # Check internet connection first
    if not is_connected():
        return False
    
    print(f"{Fore.CYAN}Checking for updates...{Style.RESET_ALL}", end='\r')
    
    try:
        current = get_installed_version()
        latest = get_latest_version()
        
        if not current or not latest:
            print(" " * 40, end='\r')  # Clear the line
            return False
        
        if compare_versions(latest, current) > 0:
            # New version available
            print(" " * 40, end='\r')  # Clear the line
            return True
        else:
            print(" " * 40, end='\r')  # Clear the line
            return False
            
    except Exception as e:
        print(" " * 40, end='\r')  # Clear the line
        return False

def get_git_revision_hash():
    """Get the current git revision hash (for git installs only)."""
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode('ascii').strip()
    except:
        return None

def is_git_install():
    """Check if running from a git repository."""
    return os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.git'))

def pull_git_updates():
    """Pull updates for git installations. Returns True if updated."""
    if not is_git_install():
        return False
    
    try:
        # Fetch latest changes
        subprocess.check_call(['git', 'fetch'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                            cwd=os.path.dirname(os.path.dirname(__file__)))
        
        # Check if we're behind
        local_hash = get_git_revision_hash()
        remote_hash = subprocess.check_output(['git', 'rev-parse', '@{u}'], 
                                             stderr=subprocess.DEVNULL,
                                             cwd=os.path.dirname(os.path.dirname(__file__))).decode('ascii').strip()
        
        if local_hash != remote_hash:
            # Pull updates
            subprocess.check_call(['git', 'pull'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                cwd=os.path.dirname(os.path.dirname(__file__)))
            print(f"{Fore.GREEN}✓ DiskMan updated! Please restart.{Style.RESET_ALL}")
            return True
    except:
        pass
    
    return False
