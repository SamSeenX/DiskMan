#!/usr/bin/env python3
"""
Utility functions for DiskMan.
"""
import os
import sys
import subprocess
import threading
import time
import itertools
import shutil

# Check if required packages are installed
try:
    import humanize
except ImportError:
    print("The 'humanize' package is required. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "humanize"])
    import humanize

try:
    from colorama import init, Fore, Back, Style
    init(autoreset=True)  # Initialize colorama
except ImportError:
    print("The 'colorama' package is required for colored output. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--break-system-packages", "colorama"])
    from colorama import init, Fore, Back, Style
    init(autoreset=True)  # Initialize colorama

# Global variable to control the spinner
spinner_running = False
spinner_thread = None

def start_spinner(message):
    """Start a spinner with a message."""
    global spinner_running, spinner_thread
    spinner_running = True
    spinner_thread = threading.Thread(target=_show_spinner, args=(message,))
    spinner_thread.daemon = True
    spinner_thread.start()
    return spinner_thread

def stop_spinner():
    """Stop the spinner."""
    global spinner_running, spinner_thread
    if spinner_running:
        spinner_running = False
        if spinner_thread and spinner_thread.is_alive():
            spinner_thread.join(timeout=1.0)  # Add timeout to prevent hanging

def _show_spinner(message):
    """Display a spinner with a message while a task is running."""
    global spinner_running
    spinner_chars = itertools.cycle(['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'])

    # Clear line and show initial message
    sys.stdout.write('\r' + ' ' * 80)  # Clear line
    sys.stdout.write(f"\r{Fore.CYAN}{message} {Fore.YELLOW}")
    sys.stdout.flush()

    while spinner_running:
        char = next(spinner_chars)
        sys.stdout.write(f"\r{Fore.CYAN}{message} {Fore.YELLOW}{char}{Style.RESET_ALL}")
        sys.stdout.flush()
        time.sleep(0.1)

    # Clear spinner when done
    sys.stdout.write('\r' + ' ' * 80)
    sys.stdout.write(f"\r{Fore.GREEN}✓ {message} completed!{Style.RESET_ALL}\n")
    sys.stdout.flush()

def get_size(path):
    """Calculate the size of a file or directory."""
    if os.path.isfile(path):
        return os.path.getsize(path)

    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):  # Skip symbolic links
                try:
                    total_size += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass  # Skip files that can't be accessed
    return total_size

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def is_hidden(path):
    """Check if a file or directory is hidden."""
    name = os.path.basename(path)

    # Unix/Mac hidden files start with a dot
    if name.startswith('.'):
        return True

    # Windows hidden files have the hidden attribute
    if os.name == 'nt':
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
            if attrs != -1:  # -1 is returned on error
                return bool(attrs & 2)  # 2 is the hidden attribute
        except (AttributeError, ImportError, OSError):
            pass

    return False

def set_terminal_size(width, height):
    """Set the terminal size to the specified width and height.

    Args:
        width (int): The desired width of the terminal in characters
        height (int): The desired height of the terminal in characters

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # For Windows
        if os.name == 'nt':
            try:
                # Try using powershell to resize the window
                powershell_cmd = f'powershell -command "$host.UI.RawUI.WindowSize = New-Object System.Management.Automation.Host.Size({width}, {height})"'
                subprocess.run(powershell_cmd, shell=True, check=False)

                # Also try the traditional mode command
                os.system(f'mode con: cols={width} lines={height}')
                return True
            except Exception:
                # Fallback to mode command only
                os.system(f'mode con: cols={width} lines={height}')
                return True

        # For macOS
        elif sys.platform == 'darwin':
            try:
                # Try using escape sequences first (works in iTerm2 and many modern terminals)
                # ESC]1337;ReportColumns=width;ReportRows=height ESC\
                sys.stdout.write(f"\033]1337;ReportColumns={width};ReportRows={height}\007")
                sys.stdout.flush()

                # Try using AppleScript to resize the Terminal window
                # This works for Terminal.app
                applescript_terminal = f'''
                tell application "Terminal"
                    if it is running then
                        set bounds of front window to {{50, 50, {50 + width * 7}, {50 + height * 14}}}
                    end if
                end tell
                '''
                subprocess.run(['osascript', '-e', applescript_terminal], check=False)

                # Try for iTerm2 as well
                applescript_iterm = f'''
                tell application "iTerm"
                    if it is running then
                        tell current window
                            set columns to {width}
                            set rows to {height}
                        end tell
                    end if
                end tell
                '''
                subprocess.run(['osascript', '-e', applescript_iterm], check=False)

                # Also try the traditional stty command for terminal dimensions
                subprocess.run(['stty', 'columns', str(width), 'rows', str(height)], check=False)

                # Try using ANSI escape sequence for xterm-compatible terminals
                sys.stdout.write(f"\x1b[8;{height};{width}t")
                sys.stdout.flush()

                return True
            except Exception:
                # Try just the stty command
                try:
                    subprocess.run(['stty', 'columns', str(width), 'rows', str(height)], check=False)
                    return True
                except Exception:
                    pass

        # For Linux and other Unix-like systems
        else:
            # Try using printf with escape sequences (works in many terminals)
            try:
                # ESC[8;{height};{width}t sequence to resize the window
                sys.stdout.write(f"\x1b[8;{height};{width}t")
                sys.stdout.flush()

                # Also try stty for good measure
                subprocess.run(['stty', 'columns', str(width), 'rows', str(height)], check=False)
                return True
            except Exception:
                pass

            # Try using resize command
            try:
                subprocess.run(['resize', '-s', str(height), str(width)], check=False)
                return True
            except (subprocess.SubprocessError, FileNotFoundError):
                pass

            # Try using xterm escape sequences
            try:
                sys.stdout.write(f"\x1b[4;{height};{width}t")
                sys.stdout.flush()
                return True
            except Exception:
                pass

        # If we get here, none of the methods worked
        # Instead of showing an error, let's just print a message to the console
        # that will be visible when the program runs
        print(f"{Fore.YELLOW}Note: For best experience, please resize your terminal window to at least {width}x{height} characters.{Style.RESET_ALL}")
        return False
    except Exception as e:
        # Don't show the error, just return False
        return False

def open_file_explorer(item_path, name):
    """Open the file explorer and highlight the selected item."""
    try:
        # Use the appropriate command based on the OS
        if sys.platform == 'darwin':  # macOS
            # On macOS, we can use the -R flag to reveal the item in Finder
            subprocess.run(['open', '-R', item_path])
            print(f"\n{Fore.GREEN}Opened parent folder with {Fore.YELLOW}{name}{Fore.GREEN} highlighted in Finder{Style.RESET_ALL}")
        elif sys.platform == 'win32':  # Windows
            # On Windows, we can use explorer /select to highlight the item
            subprocess.run(['explorer', '/select,', item_path])
            print(f"\n{Fore.GREEN}Opened parent folder with {Fore.YELLOW}{name}{Fore.GREEN} highlighted in Explorer{Style.RESET_ALL}")
        else:  # Linux and others
            # For Linux, we'll just open the parent directory
            # Most file managers don't have a standard way to highlight items
            parent_dir = os.path.dirname(item_path)
            subprocess.run(['xdg-open', parent_dir])
            print(f"\n{Fore.GREEN}Opened parent folder of {Fore.YELLOW}{name}{Fore.GREEN} in file manager{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Note: {Fore.WHITE}You'll need to locate {Fore.YELLOW}{name}{Fore.WHITE} manually{Style.RESET_ALL}")

        # Add a small delay to make sure the file/folder opens
        print(f"{Fore.CYAN}The file explorer should now be open.{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"\n{Fore.RED}Error opening parent folder: {e}{Style.RESET_ALL}")
        return False
