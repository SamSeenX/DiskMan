#!/usr/bin/env python3
"""
DiskMan V4 Curses - Zero-Dependency polished TUI using native curses.
"""
import os
import sys
import curses
import time
import humanize

# Import extracted modules
from lib.theme import THEMES, apply_theme, load_theme_cache, save_theme_cache
from lib.curses_cache import du_cache
from lib.image_compress import (
    is_image_file,
    gather_images,
    get_creation_time,
    check_and_install_pillow,
    compress_single_image
)
from lib.tui_draw import (
    draw_screen,
    show_modal_list,
    get_string_input,
    SPINNER_FRAMES,
    __version__
)

# Import other lib utilities
from lib.utils import open_file_explorer
from lib.file_operations import (
    delete_item,
    copy_item,
    move_item,
    export_report
)
from lib.bookmarks import add_bookmark, list_bookmarks
from lib.system_cache import scan_cache_folders, clear_folder


def curses_main(stdscr):
    # Setup standard locale for Unicode character rendering
    import locale
    locale.setlocale(locale.LC_ALL, '')

    # Setup curses terminal settings
    curses.use_default_colors()
    curses.curs_set(0) # Hide standard cursor block
    stdscr.keypad(True)
    stdscr.timeout(100) # Key read loop timeout in ms (non-blocking updates)

    # Initialize with saved theme from cache file
    theme_index = load_theme_cache()
    apply_theme(theme_index, stdscr)

    current_dir = os.path.realpath(os.getcwd())
    selected_idx = 0
    scroll_offset = 0
    spinner_frame = 0
    status_msg = None
    status_msg_time = 0

    items = du_cache.scan_directory_tree(current_dir)

    while True:
        # Clear status message after 4 seconds
        if status_msg and time.time() - status_msg_time > 4:
            status_msg = None

        # Fetch updates from background task scans
        if du_cache.check_and_clear_update_flag():
            items = du_cache.scan_directory_tree(current_dir)

        # Advance spinner animations
        spinner_frame = (spinner_frame + 1) % len(SPINNER_FRAMES)

        scroll_offset = draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)

        try:
            ch = stdscr.getch()
        except KeyboardInterrupt:
            du_cache.shutdown()
            break

        if ch == ord('q') or ch == ord('Q'):
            du_cache.shutdown()
            break

        elif ch == curses.KEY_DOWN:
            if selected_idx < len(items) - 1:
                selected_idx += 1

        elif ch == curses.KEY_UP:
            if selected_idx > 0:
                selected_idx -= 1

        elif ch in [curses.KEY_ENTER, 10, 13]: # Enter key select
            if len(items) > 0:
                name, _, is_dir, _, _ = items[selected_idx]
                target_path = os.path.realpath(os.path.join(current_dir, name))
                if is_dir:
                    current_dir = target_path
                    items = du_cache.scan_directory_tree(current_dir)
                    selected_idx = 0
                    scroll_offset = 0
                    status_msg = None
                    stdscr.clear() # Hard refresh screen
                else:
                    # Open file explorer/editor natively
                    open_file_explorer(target_path, name)

        elif ch in [curses.KEY_BACKSPACE, 127, 8]: # Backspace (navigate up directory)
            parent = os.path.realpath(os.path.dirname(current_dir))
            if parent != current_dir:
                current_dir = parent
                items = du_cache.scan_directory_tree(current_dir)
                selected_idx = 0
                scroll_offset = 0
                status_msg = None
                stdscr.clear() # Hard refresh screen

        elif ch in [ord('g'), ord('G')]: # Go to folder path
            init_val = current_dir if current_dir.endswith('/') else current_dir + '/'
            dest = get_string_input(stdscr, "Go to folder path:", autocomplete_path=True, initial_value=init_val)
            if dest is None:
                status_msg = "ℹ️ Go-to canceled."
                status_msg_time = time.time()
            elif dest:
                expanded = os.path.realpath(os.path.expanduser(dest))
                if os.path.isdir(expanded):
                    current_dir = expanded
                    items = du_cache.scan_directory_tree(current_dir)
                    selected_idx = 0
                    scroll_offset = 0
                    status_msg = f"📂 Switched to: {expanded}"
                    status_msg_time = time.time()
                    stdscr.clear()
                else:
                    status_msg = "❌ Invalid directory path."
                    status_msg_time = time.time()

        elif ch == ord('r') or ch == ord('R'): # Force Directory Rescan
            items = du_cache.scan_directory_tree(current_dir)
            selected_idx = 0
            scroll_offset = 0
            status_msg = "🔄 Directory rescan triggered."
            status_msg_time = time.time()
            stdscr.clear() # Hard refresh screen

        elif ch in [ord('f'), ord('F'), ord('/')]: # Filter items by text query
            query = get_string_input(stdscr, "Filter query (empty to clear):")
            du_cache.set_filter(query if query else None)
            items = du_cache.scan_directory_tree(current_dir)
            selected_idx = 0
            scroll_offset = 0
            status_msg = f"🔍 Filter set to: '{query}'" if query else "🔍 Filter cleared."
            status_msg_time = time.time()

        elif ch in [ord('a'), ord('A')]: # Bookmark current folder
            success, msg = add_bookmark(current_dir)
            status_msg = f"🔖 {msg}"
            status_msg_time = time.time()

        elif ch in [ord('b'), ord('B')]: # View and manage saved bookmarks list
            bookmarks_data = list_bookmarks()
            if not bookmarks_data:
                status_msg = "🔖 No bookmarks saved. Press 'A' to bookmark current directory."
                status_msg_time = time.time()
            else:
                bookmarks = [path for _, path in bookmarks_data]
                def draw_bg():
                    draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)
                
                sel_idx = show_modal_list(stdscr, "Select Bookmark", bookmarks, draw_bg)
                if sel_idx is not None:
                    target = bookmarks[sel_idx]
                    if os.path.isdir(target):
                        current_dir = target
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = 0
                        scroll_offset = 0
                        status_msg = f"🔖 Jumped to: {target}"
                        status_msg_time = time.time()
                        stdscr.clear() # Hard refresh screen

        elif ch in [ord('s'), ord('S')]: # Cycle sort options
            sort_mode = du_cache.cycle_sort()
            items = du_cache.scan_directory_tree(current_dir)
            selected_idx = 0
            scroll_offset = 0
            status_msg = f"🔀 Sort mode changed to: {sort_mode.upper()}"
            status_msg_time = time.time()

        elif ch in [ord('t'), ord('T')]: # Show largest files in the tree
            files = du_cache.get_largest_files(current_dir, limit=20)
            if not files:
                status_msg = "⚠️ No files found."
                status_msg_time = time.time()
            else:
                options = [f"{humanize.naturalsize(f[2]):<10} │ {f[1]} ({f[5]})" for f in files]
                def draw_bg():
                    draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)
                
                sel_idx = show_modal_list(stdscr, "Largest Files", options, draw_bg)
                if sel_idx is not None:
                    target_file = files[sel_idx][0]
                    target_dir = os.path.dirname(target_file)
                    if os.path.isdir(target_dir):
                        current_dir = os.path.realpath(target_dir)
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = 0
                        for idx, item in enumerate(items):
                            if item[0] == os.path.basename(target_file):
                                selected_idx = idx
                                break
                        scroll_offset = 0
                        stdscr.clear() # Hard refresh screen

        elif ch in [ord('u'), ord('U')]: # Find duplicate files
            dups = du_cache.find_duplicates(current_dir)
            if not dups:
                status_msg = "✅ No duplicates found."
                status_msg_time = time.time()
            else:
                options = [f"{humanize.naturalsize(d['wasted']):<10} wasted │ {d['count']} files of {humanize.naturalsize(d['size'])}" for d in dups]
                def draw_bg():
                    draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)
                
                sel_idx = show_modal_list(stdscr, "Duplicates", options, draw_bg)
                if sel_idx is not None:
                    group = dups[sel_idx]
                    dup_paths = group['files']
                    dup_options = [f"Focus: {os.path.basename(p)} ({os.path.dirname(p)})" for p in dup_paths]
                    
                    sel_path_idx = show_modal_list(stdscr, "Duplicate Group Details", dup_options, draw_bg)
                    if sel_path_idx is not None:
                        target_file = dup_paths[sel_path_idx]
                        target_dir = os.path.dirname(target_file)
                        if os.path.isdir(target_dir):
                            current_dir = os.path.realpath(target_dir)
                            items = du_cache.scan_directory_tree(current_dir)
                            selected_idx = 0
                            for idx, item in enumerate(items):
                                if item[0] == os.path.basename(target_file):
                                    selected_idx = idx
                                    break
                            scroll_offset = 0
                            stdscr.clear() # Hard refresh screen

        elif ch in [ord('w'), ord('W')]: # Wipe System Cache / temp folders
            cache_folders = scan_cache_folders()
            options = [f"{humanize.naturalsize(c[3]):<10} │ {c[2]} ({c[0]})" for c in cache_folders]
            def draw_bg():
                draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg)
            
            sel_idx = show_modal_list(stdscr, "System Cache Cleaner", options, draw_bg)
            if sel_idx is not None:
                folder_info = cache_folders[sel_idx]
                path, name, desc, size, _ = folder_info
                confirm = get_string_input(stdscr, f"Clear all files in {name}? Type 'yes':")
                if confirm.lower() == "yes":
                    success, msg, freed = clear_folder(path)
                    if success:
                        status_msg = f"✅ Freed {humanize.naturalsize(freed)}: {msg}"
                        items = du_cache.scan_directory_tree(current_dir)
                    else:
                        status_msg = f"❌ Error: {msg}"
                    status_msg_time = time.time()

        elif ch == ord('v'): # Cycle color themes forward
            theme_index = (theme_index + 1) % len(THEMES)
            apply_theme(theme_index, stdscr)
            save_theme_cache(theme_index)
            status_msg = f"🎨 Theme changed to: {THEMES[theme_index][0]}"
            status_msg_time = time.time()

        elif ch == ord('V'): # Cycle color themes backward (Shift + V)
            theme_index = (theme_index - 1) % len(THEMES)
            apply_theme(theme_index, stdscr)
            save_theme_cache(theme_index)
            status_msg = f"🎨 Theme changed to: {THEMES[theme_index][0]}"
            status_msg_time = time.time()

        elif ch == ord('x') or ch == ord('X'): # Export directory CSV report
            confirm = get_string_input(stdscr, "Export CSV report? (y/n):")
            if confirm.lower() == 'y':
                success, result = export_report(current_dir, items)
                status_msg = f"📄 Exported CSV to: {result}" if success else f"❌ Export failed: {result}"
                status_msg_time = time.time()

        elif ch == ord('d'): # Delete to Trash
            if len(items) > 0:
                name, _, _, _, _ = items[selected_idx]
                path = os.path.realpath(os.path.join(current_dir, name))
                confirm = get_string_input(stdscr, f"Move '{name}' to Trash? Type 'yes' to confirm:")
                if confirm is None:
                    status_msg = "ℹ️ Delete canceled."
                    status_msg_time = time.time()
                elif confirm.lower() == 'yes':
                    success, msg = delete_item(path, use_trash=True)
                    if success:
                        status_msg = f"🗑️ Moved to Trash: '{name}'"
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = max(0, selected_idx - 1)
                    else:
                        status_msg = f"❌ Error: {msg}"
                    status_msg_time = time.time()

        elif ch == ord('D'): # Permanent delete
            if len(items) > 0:
                name, _, _, _, _ = items[selected_idx]
                path = os.path.realpath(os.path.join(current_dir, name))
                confirm = get_string_input(stdscr, f"PERMANENTLY delete '{name}'? Type 'yes' to confirm:")
                if confirm is None:
                    status_msg = "ℹ️ Delete canceled."
                    status_msg_time = time.time()
                elif confirm.lower() == 'yes':
                    success, msg = delete_item(path, use_trash=False)
                    if success:
                        status_msg = f"💥 Permanently deleted: '{name}'"
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = max(0, selected_idx - 1)
                    else:
                        status_msg = f"❌ Error: {msg}"
                    status_msg_time = time.time()

        elif ch in [ord('m'), ord('M')]: # Move selected item
            if len(items) > 0:
                name, _, _, _, _ = items[selected_idx]
                path = os.path.realpath(os.path.join(current_dir, name))
                dest = get_string_input(stdscr, f"Move '{name}' to folder path:")
                if dest is None:
                    status_msg = "ℹ️ Move canceled."
                    status_msg_time = time.time()
                elif dest and os.path.isdir(dest):
                    success, result = move_item(path, dest)
                    if success:
                        status_msg = f"🚚 Moved '{name}' to '{dest}'"
                        items = du_cache.scan_directory_tree(current_dir)
                        selected_idx = max(0, selected_idx - 1)
                    else:
                        status_msg = f"❌ Error: {result}"
                    status_msg_time = time.time()
                elif dest:
                    status_msg = "❌ Invalid destination path."
                    status_msg_time = time.time()

        elif ch in [ord('c'), ord('C')]: # Copy selected item
            if len(items) > 0:
                name, _, _, _, _ = items[selected_idx]
                path = os.path.realpath(os.path.join(current_dir, name))
                dest = get_string_input(stdscr, f"Copy '{name}' to folder path:")
                if dest is None:
                    status_msg = "ℹ️ Copy canceled."
                    status_msg_time = time.time()
                elif dest and os.path.isdir(dest):
                    success, result = copy_item(path, dest)
                    status_msg = f"📋 Copied '{name}' to '{dest}'" if success else f"❌ Error: {result}"
                    status_msg_time = time.time()
                elif dest:
                    status_msg = "❌ Invalid destination path."
                    status_msg_time = time.time()

        elif ch in [ord('i'), ord('I')]: # Image compression feature
            if not check_and_install_pillow(stdscr, safe_addstr_fn=stdscr.addstr):
                status_msg = "❌ Error: Failed to import/install Pillow library."
                status_msg_time = time.time()
                continue
                
            from PIL import Image

            # Default selections wizard
            scope_input = get_string_input(stdscr, "Compress: [s]elected file, or [f]older?", default_val="f")
            if scope_input is None:
                status_msg = "ℹ️ Compression canceled."
                status_msg_time = time.time()
                continue
            
            scope = scope_input.lower()
            if scope not in ['s', 'f']:
                status_msg = "⚠️ Aborted: Invalid scope selection."
                status_msg_time = time.time()
                continue
                
            target_files = []
            target_root = None
            recursive = False
            
            if scope == 's':
                if len(items) > 0:
                    name, _, is_dir, _, _ = items[selected_idx]
                    path = os.path.realpath(os.path.join(current_dir, name))
                    if is_dir:
                        confirm_dir = get_string_input(stdscr, f"Compress images inside folder '{name}'? ([y]es/[n]o)", default_val="y")
                        if confirm_dir is None:
                            status_msg = "ℹ️ Compression canceled."
                            status_msg_time = time.time()
                            continue
                        if confirm_dir.lower() in ['y', 'yes']:
                            rec_input = get_string_input(stdscr, "Compress recursively? ([y]es/[n]o)", default_val="n")
                            if rec_input is None:
                                status_msg = "ℹ️ Compression canceled."
                                status_msg_time = time.time()
                                continue
                            recursive = rec_input.lower() in ['y', 'yes']
                            target_root = path
                            target_files = gather_images(path, recursive=recursive)
                    else:
                        if is_image_file(path):
                            target_files = [path]
                            target_root = os.path.dirname(path)
                        else:
                            status_msg = "❌ Selected file is not a supported image format."
                            status_msg_time = time.time()
                            continue
            else:
                rec_input = get_string_input(stdscr, "Compress recursively? ([y]es/[n]o)", default_val="n")
                if rec_input is None:
                    status_msg = "ℹ️ Compression canceled."
                    status_msg_time = time.time()
                    continue
                recursive = rec_input.lower() in ['y', 'yes']
                target_root = current_dir
                target_files = gather_images(current_dir, recursive=recursive)
                
            if not target_files:
                status_msg = "⚠️ No matching image files found."
                status_msg_time = time.time()
                continue
                
            out_format_input = get_string_input(stdscr, "Output format ([w]ebp/[j]peg)", default_val="j")
            if out_format_input is None:
                status_msg = "ℹ️ Compression canceled."
                status_msg_time = time.time()
                continue
            
            out_format_raw = out_format_input.lower()
            if out_format_raw in ['w', 'webp']:
                out_format = 'webp'
            elif out_format_raw in ['j', 'jpeg']:
                out_format = 'jpeg'
            else:
                status_msg = "⚠️ Aborted: Unsupported output format."
                status_msg_time = time.time()
                continue
                
            quality_str = get_string_input(stdscr, "Compression quality (1-100)", default_val="69")
            if quality_str is None:
                status_msg = "ℹ️ Compression canceled."
                status_msg_time = time.time()
                continue
            try:
                quality = int(quality_str)
                if not (1 <= quality <= 100):
                    quality = 69
            except ValueError:
                quality = 69
 
            save_style_input = get_string_input(stdscr, "Save: [o]riginals in subfolder, or [c]ompressed in subfolder? (o/c)", default_val="c")
            if save_style_input is None:
                status_msg = "ℹ️ Compression canceled."
                status_msg_time = time.time()
                continue
            
            save_style_raw = save_style_input.lower()
            if save_style_raw in ['o', 'originals']:
                save_style = 'o'
            elif save_style_raw in ['c', 'compressed']:
                save_style = 'c'
            else:
                status_msg = "⚠️ Aborted: Invalid save style option."
                status_msg_time = time.time()
                continue
            
            compression_root = None
            if recursive and save_style == 'o':
                backup_loc_input = get_string_input(stdscr, "Save originals in: [r]oot directory or [e]ach relative directory? (r/e)", default_val="e")
                if backup_loc_input is None:
                    status_msg = "ℹ️ Compression canceled."
                    status_msg_time = time.time()
                    continue
                backup_loc_raw = backup_loc_input.lower()
                if backup_loc_raw in ['r', 'root']:
                    compression_root = target_root
                elif backup_loc_raw in ['e', 'each', 'relative']:
                    compression_root = None
                else:
                    status_msg = "⚠️ Aborted: Invalid backup location option."
                    status_msg_time = time.time()
                    continue
                
            # Sort chronologically by birthtime/mtime to preserve timeline order
            target_files.sort(key=get_creation_time)
            
            total_images = len(target_files)
            compressed_count = 0
            total_saved = 0
            
            for idx, filepath in enumerate(target_files):
                # Live status indicator
                progress_msg = f"⚙️ Compressing image {idx+1}/{total_images}... ({os.path.basename(filepath)})"
                draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, progress_msg)
                
                success, saved_bytes = compress_single_image(filepath, out_format, quality, save_style=save_style, compression_root=compression_root)
                if success:
                    compressed_count += 1
                    total_saved += saved_bytes
                    
            if compressed_count > 0:
                status_msg = f"✅ Done! Compressed {compressed_count}/{total_images} images. Saved {humanize.naturalsize(total_saved)}."
                items = du_cache.scan_directory_tree(current_dir)
            else:
                status_msg = "ℹ️ Done. Original files were already smaller than compressed versions."
            status_msg_time = time.time()

        elif ch == curses.KEY_RESIZE: # Dynamically handles terminal window resizing
            stdscr.clear()


def print_exit_message():
    """Prints a beautiful, colored goodbye message upon exit."""
    try:
        from colorama import Fore, Style, init
        init(autoreset=True)
        print(f"\n{Fore.GREEN}{Style.BRIGHT}Thanks for using DiskMan V4!{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Made with ❤️  by {Fore.YELLOW}{Style.BRIGHT}SamSeen{Style.RESET_ALL}")
        print(f"{Fore.MAGENTA}☕ If you found this useful: {Fore.BLUE}{Style.BRIGHT}https://buymeacoffee.com/samseen{Style.RESET_ALL}\n")
    except ImportError:
        # Fallback if colorama is not installed in runtime environment
        print("\nThanks for using DiskMan V4!")
        print("Made with ❤️  by SamSeen")
        print("☕ If you found this useful: https://buymeacoffee.com/samseen\n")


def main():
    try:
        curses.wrapper(curses_main)
    except KeyboardInterrupt:
        pass
    finally:
        du_cache.shutdown()
    print_exit_message()
    sys.exit(0)


if __name__ == "__main__":
    main()
