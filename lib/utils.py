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
spinner_current_folder = ""
spinner_folder_count = 0

# Time-based sarcastic messages
SPINNER_MESSAGES = [
    (0, "Starting up..."),
    (3, "Counting your files... 🧛"),
    (6, "Still working... 😊"),
    (10, "This folder is bigger than expected..."),
    (15, "Wow, you really have a lot of stuff..."),
    (20, "Did you ever delete anything? 🤔"),
    (30, "I've seen smaller hard disks..."),
    (45, "Making coffee while we wait..."),
    (60, "Maybe time for a snack break?"),
    (90, "I'm not stuck, it's just... you have too many files! 🤔"),
    (120, "Still going... you might want to sit down"),
    (180, "This is taking forever. Literally."),
    (300, "I'm starting to question my life choices..."),
    (600, "We're still friends, right?"),
]

def update_spinner_folder(folder_path):
    """Update the current folder being scanned."""
    global spinner_current_folder, spinner_folder_count
    spinner_current_folder = folder_path
    spinner_folder_count += 1

def start_spinner(message):
    """Start a spinner with a message."""
    global spinner_running, spinner_thread, spinner_current_folder, spinner_folder_count
    spinner_running = True
    spinner_current_folder = ""
    spinner_folder_count = 0
    spinner_thread = threading.Thread(target=_show_spinner, args=(message,))
    spinner_thread.daemon = True
    spinner_thread.start()
    return spinner_thread

def stop_spinner():
    """Stop the spinner."""
    global spinner_running, spinner_thread, spinner_folder_count
    if spinner_running:
        spinner_running = False
        if spinner_thread and spinner_thread.is_alive():
            spinner_thread.join(timeout=1.0)  # Add timeout to prevent hanging
    spinner_folder_count = 0

def _show_spinner(message):
    """Display a spinner with time-based messages and current folder."""
    global spinner_running, spinner_current_folder, spinner_folder_count
    spinner_chars = itertools.cycle(['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷'])
    start_time = time.time()
    last_message_idx = 0

    # Clear line and show initial message
    sys.stdout.write('\r' + ' ' * 100)
    sys.stdout.flush()

    while spinner_running:
        char = next(spinner_chars)
        elapsed = time.time() - start_time
        
        # Get appropriate message based on elapsed time
        current_message = message
        for threshold, msg in SPINNER_MESSAGES:
            if elapsed >= threshold:
                current_message = msg
        
        # Get abbreviated folder name (last 25 chars)
        folder_display = ""
        if spinner_current_folder:
            folder_name = os.path.basename(spinner_current_folder) or spinner_current_folder
            if len(folder_name) > 25:
                folder_name = "..." + folder_name[-22:]
            folder_display = f" {Fore.WHITE}[{folder_name}]{Style.RESET_ALL}"
        
        # Build status line
        count_display = f" {Fore.GREEN}({spinner_folder_count}){Style.RESET_ALL}" if spinner_folder_count > 0 else ""
        
        # Format time display (Xm Ys for >90s, amber color)
        if elapsed > 90:
            mins = int(elapsed) // 60
            secs = int(elapsed) % 60
            time_display = f" {Fore.YELLOW}{mins}m {secs}s{Style.RESET_ALL}"
        elif elapsed > 5:
            time_display = f" {Fore.WHITE}{int(elapsed)}s{Style.RESET_ALL}"
        else:
            time_display = ""
        
        status = f"\r{Fore.CYAN}{current_message}{Style.RESET_ALL}{time_display}{folder_display}{count_display} {Fore.YELLOW}{char}{Style.RESET_ALL}"
        
        # Pad to clear previous content
        sys.stdout.write('\r' + ' ' * 100)
        sys.stdout.write(status)
        sys.stdout.flush()
        time.sleep(0.1)

    # Clear spinner when done
    elapsed = time.time() - start_time
    sys.stdout.write('\r' + ' ' * 100)
    if elapsed > 10:
        sys.stdout.write(f"\r{Fore.GREEN}✓ Done! Scanned {spinner_folder_count} folders in {elapsed:.1f}s{Style.RESET_ALL}\n")
    else:
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
                tell application "iTerm2"
                    if it is running then
                        tell current session of current window
                            set columns to {width}
                            set rows to {height}
                        end tell
                    end if
                end tell
                '''
                subprocess.run(['osascript', '-e', applescript_iterm], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # Also try the traditional stty command for terminal dimensions
                subprocess.run(['stty', 'columns', str(width), 'rows', str(height)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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


def detect_terminal():
    """Detect which terminal emulator is being used.
    
    Returns:
        str: 'iterm2', 'terminal', 'vscode', 'kitty', 'alacritty', or 'unknown'
    """
    # Check for iTerm2
    if os.environ.get('ITERM_SESSION_ID'):
        return 'iterm2'
    
    # Check for VS Code integrated terminal
    if os.environ.get('TERM_PROGRAM') == 'vscode':
        return 'vscode'
    
    # Check for Apple Terminal
    if os.environ.get('TERM_PROGRAM') == 'Apple_Terminal':
        return 'terminal'
    
    # Check for Kitty
    if os.environ.get('KITTY_WINDOW_ID'):
        return 'kitty'
    
    # Check for Alacritty
    if 'alacritty' in os.environ.get('TERM', '').lower():
        return 'alacritty'
    
    return 'unknown'


def set_iterm_font_size(size):
    """Set font size in iTerm2 using AppleScript.
    
    Args:
        size (int): Font size in points
    
    Returns:
        bool: True if successful
    """
    if detect_terminal() != 'iterm2':
        return False
    
    try:
        applescript = f'''
        tell application "iTerm2"
            tell current session of current window
                set font size to {size}
            end tell
        end tell
        '''
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def optimize_terminal_view(target_cols=120, target_rows=40, preferred_font_size=12):
    """Optimize terminal for best DiskMan viewing experience.
    
    Attempts to:
    1. Detect terminal type
    2. Set font size (iTerm2 only)
    3. Resize window to desired dimensions
    
    Args:
        target_cols: Desired number of columns
        target_rows: Desired number of rows
        preferred_font_size: Font size for iTerm2
    
    Returns:
        dict: Results of optimization attempts
    """
    results = {
        'terminal': detect_terminal(),
        'font_changed': False,
        'size_changed': False
    }
    
    terminal = results['terminal']
    
    # iTerm2 - can control font size
    if terminal == 'iterm2':
        results['font_changed'] = set_iterm_font_size(preferred_font_size)
        time.sleep(0.2)  # Give time for font change to take effect
    
    # Resize window
    results['size_changed'] = set_terminal_size(target_cols, target_rows)
    
    return results


def get_optimal_display_settings():
    """Get optimal display settings based on current terminal size.
    
    Returns:
        dict: Recommended items_per_page and column widths
    """
    try:
        size = shutil.get_terminal_size((120, 40))
        cols, rows = size.columns, size.lines
    except Exception:
        cols, rows = 120, 40
    
    # Calculate optimal items per page (leave room for header/footer)
    header_lines = 6
    footer_lines = 8
    items_per_page = max(5, rows - header_lines - footer_lines)
    
    # Adjust name column width based on terminal width
    if cols >= 140:
        name_width = 50
    elif cols >= 120:
        name_width = 40
    elif cols >= 100:
        name_width = 30
    else:
        name_width = 25
    
    return {
        'items_per_page': items_per_page,
        'name_width': name_width,
        'terminal_cols': cols,
        'terminal_rows': rows
    }

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

def get_file_metadata(filepath):
    """Extract metadata for various file types (Images, Audio, PDF, Text, Executables, Archives)."""
    meta = {}
    if not filepath or not os.path.isfile(filepath):
        return meta
        
    ext = os.path.splitext(filepath)[1].lower()
    
    # Images
    if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff'):
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            with Image.open(filepath) as img:
                meta['Format'] = img.format
                meta['Dimensions'] = f"{img.width}x{img.height}"
                meta['Color Mode'] = img.mode
                
                # Check for resolution (DPI)
                dpi = img.info.get('dpi')
                if dpi:
                    meta['Resolution'] = f"{int(dpi[0])} DPI"
                    
                # Check for animation frames
                if getattr(img, 'is_animated', False):
                    meta['Frames'] = str(getattr(img, 'n_frames', 1))
                
                exif_data = img.getexif()
                if exif_data:
                    exif_interesting = {
                        'Make': 'Maker',
                        'Model': 'Model',
                        'DateTime': 'Captured',
                        'Software': 'Software',
                        'ExposureTime': 'Exposure',
                        'FNumber': 'Aperture',
                        'ISOSpeedRatings': 'ISO',
                        'LensModel': 'Lens',
                        'FocalLength': 'Focal Len',
                        'Flash': 'Flash',
                        'Orientation': 'Orientation'
                    }
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        if tag_name in exif_interesting:
                            if tag_name == 'ExposureTime' and isinstance(value, tuple) and len(value) == 2:
                                value = f"{value[0]}/{value[1]}s"
                            elif tag_name == 'FocalLength':
                                if isinstance(value, tuple) and len(value) == 2:
                                    value = f"{value[0]/value[1]:.1f}mm"
                                else:
                                    value = f"{float(value):.1f}mm"
                            elif tag_name == 'Flash':
                                try:
                                    value = "Fired" if (int(value) & 1) else "Did not fire"
                                except Exception:
                                    pass
                            elif tag_name == 'Orientation':
                                orient_map = {
                                    1: 'Horizontal',
                                    2: 'Mirror horizontal',
                                    3: 'Rotate 180',
                                    4: 'Mirror vertical',
                                    5: 'Mirror horiz + rot 270 CW',
                                    6: 'Rotate 90 CW',
                                    7: 'Mirror horiz + rot 90 CW',
                                    8: 'Rotate 270 CW'
                                }
                                value = orient_map.get(value, str(value))
                            meta[exif_interesting[tag_name]] = str(value)
                            
                    # Decode GPS info if available (Tag ID: 34853)
                    gps_info = exif_data.get(34853)
                    if gps_info:
                        try:
                            # 1=LatRef, 2=Lat, 3=LonRef, 4=Lon, 6=Alt
                            lat_ref = gps_info.get(1)
                            lat = gps_info.get(2)
                            lon_ref = gps_info.get(3)
                            lon = gps_info.get(4)
                            
                            def to_dec(coord, ref):
                                if not coord or not ref:
                                    return None
                                def to_f(v):
                                    if isinstance(v, tuple) and len(v) == 2:
                                        return v[0] / v[1]
                                    return float(v)
                                try:
                                    d = to_f(coord[0])
                                    m = to_f(coord[1])
                                    s = to_f(coord[2])
                                    dec = d + (m / 60.0) + (s / 3600.0)
                                    if ref in ('S', 'W'):
                                        dec = -dec
                                    return dec
                                except Exception:
                                    return None
                            
                            lat_dec = to_dec(lat, lat_ref)
                            lon_dec = to_dec(lon, lon_ref)
                            if lat_dec is not None and lon_dec is not None:
                                meta['GPS'] = f"{lat_dec:.4f}, {lon_dec:.4f}"
                                
                            alt = gps_info.get(6)
                            if alt:
                                def to_f(v):
                                    if isinstance(v, tuple) and len(v) == 2:
                                        return v[0] / v[1]
                                    return float(v)
                                meta['Altitude'] = f"{to_f(alt):.1f}m"
                        except Exception:
                            pass
        except Exception:
            pass
            
    # Audio (WAV)
    elif ext == '.wav':
        try:
            import wave
            with wave.open(filepath, 'rb') as w:
                ch = w.getnchannels()
                rate = w.getframerate()
                frames = w.getnframes()
                dur = frames / float(rate)
                meta['Type'] = 'WAV Audio'
                meta['Channels'] = 'Stereo' if ch == 2 else 'Mono' if ch == 1 else str(ch)
                meta['Sample Rate'] = f"{rate / 1000.0:.1f} kHz"
                meta['Duration'] = f"{dur:.2f}s"
        except Exception:
            pass
            
    # PDF
    elif ext == '.pdf':
        try:
            with open(filepath, 'rb') as f:
                content = f.read(1024)
                f.seek(0, 2)
                file_size = f.tell()
                if file_size > 1024:
                    f.seek(max(0, file_size - 4096))
                    content += f.read()
                text = content.decode('latin-1', errors='ignore')
                
                import re
                pages_match = re.search(r'/Count\s+(\d+)', text)
                if pages_match:
                    meta['Pages'] = pages_match.group(1)
                    
                title_match = re.search(r'/Title\s*\((.*?)\)', text)
                if title_match:
                    meta['Title'] = title_match.group(1)[:25]
                author_match = re.search(r'/Author\s*\((.*?)\)', text)
                if author_match:
                    meta['Author'] = author_match.group(1)[:25]
        except Exception:
            pass
            
    # Executables / Binaries
    elif ext in ('.exe', '.dll', '.so', '.dylib', '', '.bin'):
        try:
            with open(filepath, 'rb') as f:
                magic = f.read(4)
                if magic.startswith(b'\x7fELF'):
                    meta['Type'] = 'ELF Binary'
                    elf_class = f.read(1)
                    meta['Arch'] = '64-bit' if elf_class == b'\x02' else '32-bit'
                elif magic.startswith(b'MZ'):
                    meta['Type'] = 'PE Binary'
                elif magic in (b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf'):
                    meta['Type'] = 'Mach-O 64-bit'
                elif magic in (b'\xce\xfa\xed\xfe', b'\xfe\xed\xfa\xce'):
                    meta['Type'] = 'Mach-O 32-bit'
        except Exception:
            pass
            
    # Archives
    elif ext in ('.zip', '.tar', '.gz', '.tgz'):
        try:
            import zipfile
            import tarfile
            if zipfile.is_zipfile(filepath):
                with zipfile.ZipFile(filepath) as z:
                    meta['Type'] = 'ZIP Archive'
                    meta['Files'] = str(len(z.namelist()))
            elif tarfile.is_tarfile(filepath):
                with tarfile.open(filepath) as t:
                    meta['Type'] = 'TAR Archive'
                    meta['Files'] = str(len(t.getnames()))
        except Exception:
            pass
            
    # Code / Text files
    elif ext in ('.txt', '.py', '.js', '.ts', '.html', '.css', '.json', '.yaml', '.yml', '.md', '.csv', '.xml', '.sh', '.bat'):
        try:
            with open(filepath, 'r', errors='ignore') as f:
                lines = f.readlines()
                meta['Lines'] = str(len(lines))
                meta['Chars'] = str(sum(len(l) for l in lines))
        except Exception:
            pass
            
    return meta
