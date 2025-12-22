
import os
import subprocess
import sys
import socket
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

def get_git_revision_hash():
    """Get the current git revision hash."""
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL).decode('ascii').strip()
    except:
        return None

def check_for_updates():
    """
    Check for updates and pull if available.
    Returns True if updated, False otherwise.
    """
    # 1. Check if we are in a git repo
    if not os.path.exists('.git'):
        return False

    # 2. Check internet connection
    if not is_connected():
        return False

    print(f"{Fore.CYAN}Checking for updates...{Style.RESET_ALL}", end='\r')
    
    try:
        # 3. Fetch latest changes
        subprocess.check_call(['git', 'fetch'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 4. Check status
        # HEAD vs @{upstream}
        local_hash = get_git_revision_hash()
        remote_hash = subprocess.check_output(['git', 'rev-parse', '@{u}'], stderr=subprocess.DEVNULL).decode('ascii').strip()
        
        if local_hash != remote_hash:
            # Check if we are behind
            # git merge-base --is-ancestor HEAD @{u}
            # Returns 0 if HEAD is ancestor of @{u} (i.e. we are behind)
            is_behind = subprocess.call(['git', 'merge-base', '--is-ancestor', 'HEAD', '@{u}'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
            
            if is_behind:
                print(f"{Fore.GREEN}Update available! Installing...{Style.RESET_ALL}   ")
                # 5. Pull updates
                subprocess.check_call(['git', 'pull'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"{Fore.GREEN}✓ DiskMan updated successfully!{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}Please restart the application to apply changes.{Style.RESET_ALL}")
                return True
    except Exception as e:
        # Fail silently on update errors to not block usage
        # print(f"Update check failed: {e}")
        pass
        
    return False
