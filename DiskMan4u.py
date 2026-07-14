#!/usr/bin/env python3
"""
DiskMan V4 Urwid - TUI prototype using the urwid library.
"""
import os
import sys
import platform
import subprocess
import threading
import shutil
import humanize
from concurrent.futures import ThreadPoolExecutor

# Try to import urwid, auto-install if missing
try:
    import urwid
except ImportError:
    print("⚠️  'urwid' library is missing. Attempting to install automatically...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "urwid"], check=True)
        import urwid
        print("✅ 'urwid' successfully installed!")
    except Exception as e:
        print(f"❌ Failed to install urwid automatically: {e}")
        print("Please run: pip install urwid manually.")
        sys.exit(1)

# Import cache & modules
from lib.cache import DirectoryCache
import lib.cache

# Detect du
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


class UrwidDirectoryCache(DirectoryCache):
    """DuDirectoryCache adapted for Urwid Loop updates."""
    def __init__(self, on_update_callback=None):
        super().__init__()
        self.scanned_directories = set()
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.on_update_callback = on_update_callback

    def run_du_command(self, directory):
        sizes = {}
        try:
            cmd = ['du', '-k', '-d', '1', directory]
            if platform.system() == 'Linux':
                cmd = ['du', '-k', '--max-depth=1', directory]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    parts = line.strip().split('\t', 1)
                    if len(parts) == 2:
                        size_kb, p = parts
                        try:
                            sizes[os.path.realpath(p)] = int(size_kb) * 1024
                        except ValueError:
                            pass
        except Exception:
            pass
        return sizes

    def run_python_walk_sizes(self, directory):
        sizes = {}
        try:
            subdirs = []
            for entry in os.scandir(directory):
                if entry.is_dir(follow_symlinks=False):
                    subdirs.append(os.path.realpath(entry.path))
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

        if needs_size_calc:
            def bg_scan():
                if HAS_DU:
                    sizes = self.run_du_command(self.scan_root)
                else:
                    sizes = self.run_python_walk_sizes(self.scan_root)
                
                updated_items = []
                for name, size, is_dir, is_hid, mtime in self.cache.get(self.scan_root, []):
                    path = os.path.realpath(os.path.join(self.scan_root, name))
                    if is_dir and size < 0:
                        new_size = sizes.get(path, 0)
                        self.sizes[path] = new_size
                        updated_items.append((name, new_size, is_dir, is_hid, mtime))
                    else:
                        updated_items.append((name, size, is_dir, is_hid, mtime))
                
                self.cache[self.scan_root] = self._apply_filters_and_sort(updated_items)
                self.sizes[self.scan_root] = sum(item[1] for item in updated_items if item[1] >= 0)
                
                if self.on_update_callback:
                    self.on_update_callback()

            self.executor.submit(bg_scan)

        return self._apply_filters_and_sort(self.cache[self.scan_root])


class SelectableRow(urwid.WidgetWrap):
    """A focusable row representing a file or directory."""
    def __init__(self, idx, name, size, is_dir, on_select):
        self.name = name
        self.is_dir = is_dir
        self.on_select = on_select
        
        # Format sizes nicely
        if size == -1:
            size_str = "Calculating..."
        else:
            size_str = humanize.naturalsize(size)
            
        type_str = "📁" if is_dir else "📄"
        
        text = f"{idx:<4} {name:<40} {size_str:<12} {type_str}"
        self.widget = urwid.Text(text)
        
        # AttrMap handles styling and selection highlights
        color_tag = 'directory' if is_dir else 'file'
        self.main_widget = urwid.AttrMap(self.widget, color_tag, 'highlight')
        super().__init__(self.main_widget)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == 'enter':
            self.on_select(self.name, self.is_dir)
            return None
        return key


class DiskManUrwidApp:
    def __init__(self):
        self.current_dir = os.path.realpath(os.getcwd())
        self.cache = UrwidDirectoryCache(on_update_callback=self.trigger_refresh)
        
        # Monkey patch cache singleton reference
        lib.cache._directory_cache = self.cache
        
        self.palette = [
            ('header', 'white,bold', 'dark cyan'),
            ('footer', 'yellow', 'dark blue'),
            ('directory', 'light cyan', 'black'),
            ('file', 'white', 'black'),
            ('highlight', 'black', 'light cyan'),
            ('status', 'light green', 'black')
        ]
        
        self.header_text = urwid.Text("", align='left')
        self.header = urwid.AttrMap(self.header_text, 'header')
        
        self.list_walker = urwid.SimpleFocusListWalker([])
        self.list_box = urwid.ListBox(self.list_walker)
        
        self.footer_text = urwid.Text("ENTER: Enter/Open │ ESC/Backspace: Go Up │ R: Rescan │ Q: Quit")
        self.footer = urwid.AttrMap(self.footer_text, 'footer')
        
        self.status_text = urwid.Text("")
        self.status = urwid.AttrMap(self.status_text, 'status')
        
        # Assemble frame structure
        self.view = urwid.Frame(
            body=self.list_box,
            header=urwid.Pile([self.header, urwid.Divider('─')]),
            footer=urwid.Pile([self.status, self.footer])
        )
        
        self.loop = None
        self.load_directory()

    def load_directory(self):
        self.header_text.set_text(f" DISKMAN V4 URWID │ Directory: {self.current_dir}")
        items = self.cache.scan_directory_tree(self.current_dir)
        
        # Build selectable rows
        rows = []
        for i, item in enumerate(items):
            name, size, is_dir, _, _ = item
            row = SelectableRow(i+1, name, size, is_dir, self.handle_selection)
            rows.append(row)
            
        self.list_walker.clear()
        self.list_walker.extend(rows)
        
        # Compute total stats
        total_size = sum(item[1] for item in items if item[1] >= 0)
        self.status_text.set_text(f" Total size: {humanize.naturalsize(total_size)} │ Items: {len(items)}")

    def handle_selection(self, name, is_dir):
        if is_dir:
            self.current_dir = os.path.realpath(os.path.join(self.current_dir, name))
            self.load_directory()

    def trigger_refresh(self):
        """Callback from background thread when sizing completes."""
        if self.loop:
            # Urwid's main loop supports asynchronous updates via draw_screen
            self.loop.set_alarm_in(0, lambda *args: self.load_directory())

    def unhandled_input(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()
        elif key in ('r', 'R'):
            self.load_directory()
        elif key in ('esc', 'backspace'):
            parent = os.path.realpath(os.path.dirname(self.current_dir))
            if parent != self.current_dir:
                self.current_dir = parent
                self.load_directory()

    def run(self):
        self.loop = urwid.MainLoop(self.view, self.palette, unhandled_input=self.unhandled_input)
        self.loop.run()


if __name__ == "__main__":
    app = DiskManUrwidApp()
    app.run()
