#!/usr/bin/env python3
"""
DiskMan V3 - Enhanced Disk Space Analyzer by SamSeen

A powerful tool to visualize and manage disk space usage with advanced features.
"""
import os
import sys
import time
import humanize
from colorama import Fore, Style

__version__ = "3.0.5"

# Import V2 modules
from lib.utils import (
    open_file_explorer, 
    set_terminal_size, 
    clear_screen,
    optimize_terminal_view,
    get_optimal_display_settings,
    detect_terminal
)
from lib.file_operations import (
    list_directory_cached,
    delete_item,
    get_item_details,
    remove_from_cache,
    invalidate_cache,
    copy_item,
    move_item,
    parse_selection,
    export_report,
    get_file_preview
)
from lib.ui import (
    display_directory,
    show_navigation_options,
    show_welcome_message,
    show_delete_confirmation,
    show_extension_stats,
    show_bookmarks,
    show_duplicates,
    show_file_preview,
    show_help,
    show_search_results,
    show_largest_files,
    show_cache_cleaner
)
from lib.system_cache import scan_cache_folders, clear_folder
from lib.cache import get_cache
from lib.bookmarks import (
    add_bookmark,
    remove_bookmark,
    get_bookmark,
    list_bookmarks
)

try:
    import readline
except ImportError:
    pass


def main():
    """Main function for DiskMan V3."""
    # Version check (must be first - before any output)
    if len(sys.argv) > 1 and sys.argv[1] in ['-v', '--version', 'version']:
        print(f"DiskMan V{__version__}")
        return

    # Help/Usage check
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help', '?']:
        show_help()
        return

    # Auto-update check
    from lib.updater import check_for_updates
    if check_for_updates():
        # Optional: Auto-restart or exit?
        # For now, we just notified the user. To be safe, we can wait a moment.
        time.sleep(1)

    # Optimize terminal for best viewing experience
    terminal_type = detect_terminal()
    
    # Try to set optimal terminal settings
    opt_result = optimize_terminal_view(
        target_cols=130, 
        target_rows=45, 
        preferred_font_size=12
    )

    # Dynamic items per page
    display_settings = get_optimal_display_settings()
    items_per_page = 20
    
    # Initialize current_dir early (may be overridden by commands/welcome)
    current_dir = os.getcwd()

    skip_welcome = False

    # --- CLI COMMAND HANDLING ---
    if len(sys.argv) > 1:
        # Check for skip_welcome globally if we are running any command
        skip_welcome = True
        
        command = sys.argv[1].lower()
        
        # 1. WEB DASHBOARD
        if command == 'web':
            port = 5001
            if len(sys.argv) > 2 and sys.argv[2].isdigit():
                port = int(sys.argv[2])
            
            # We need a cache for the web dashboard, scanning current dir
            # We need a cache for the web dashboard, scanning current dir
            current_dir = os.getcwd()
            clear_screen()
            print(f"{Fore.GREEN}🌐 Starting DiskMan Dashboard for: {current_dir}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Press Ctrl+C to stop the server{Style.RESET_ALL}\n")
            
            cache = get_cache()
            # Initial scan if needed (web server handles it, but good to ensure root)
            list_directory_cached(current_dir) # Ensure cache is populated for web
            from lib.web_server import start_dashboard
            try:
                start_dashboard(cache, current_dir, port=port)
            except KeyboardInterrupt:
                pass
            return

        # 2. CLEANER
        elif command == 'clean':
            print(f"{Fore.CYAN}Starting System Cleaner...{Style.RESET_ALL}")
            show_cache_cleaner()
            return

        # 3. DIRECT ACTION COMMANDS (dup, top, f)
        elif command in ['dup', 'duplicates', 'top', 'large', 'f', 'search', 'find']:
            current_dir = os.getcwd()
            cache = get_cache()
            
            # Scan current directory
            list_directory_cached(current_dir) 
            
            action = None
            
            # execute command
            if command in ['dup', 'duplicates']:
                dups = cache.find_duplicates(current_dir)
                action = show_duplicates(dups)
            
            elif command in ['top', 'large']:
                limit = 50
                if len(sys.argv) > 2 and sys.argv[2].isdigit():
                    limit = int(sys.argv[2])
                files = cache.get_largest_files(current_dir, limit=limit)
                scan_root = cache.get_scan_root() or current_dir
                action = show_largest_files(files, scan_root)
            
            elif command in ['f', 'search', 'find']:
                if len(sys.argv) > 2:
                    query = " ".join(sys.argv[2:])
                    results = cache.search_files(query, current_dir)
                    action = show_search_results(results, query, current_dir)
                else:
                    print(f"{Fore.RED}Usage: diskman f <query>{Style.RESET_ALL}")
                    return
            
            # Handle Result Action
            if action:
                if action[0] == 'goto':
                    # SWITCH TO INTERACTIVE MODE AT THIS PATH
                    current_dir = action[1]
                    # skip_welcome is already True
                
                elif action[0] == 'open':
                    # Open and STAY in app (fall through)
                    path = action[1]
                    open_file_explorer(path)
                    
                elif action[0] == 'delete':
                    # Delete and STAY in app (fall through)
                    path = action[1]
                    details = get_item_details(path)
                    if details and show_delete_confirmation(details, use_trash=True):
                        success, msg = delete_item(path, use_trash=True)
                        if success:
                            print(f"{Fore.GREEN}✓ Deleted: {os.path.basename(path)}{Style.RESET_ALL}")
                            # Force rescan since we deleted something
                            # Since we fall through to while True loop:
                            # We can set force_rescan=True if we can access it?
                            # Actually, force_rescan is local to main, but initialized AFTER this block.
                            # We need to make sure delete invalidates cache properly.
                            remove_from_cache(path)
                        else:
                            print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")
            
            # FALL THROUGH TO INTERACTIVE MODE
            # We removed the 'else: return' and 'return' statements.
            # Program continues to '--- INTERACTIVE MODE ---' below.

    # --- INTERACTIVE MODE ---
    
    if not skip_welcome: # Don't show terminal tips if we skipped welcome
        if not opt_result['size_changed']:
            print(f"{Fore.YELLOW}Tip: For best experience, use iTerm2 or resize terminal to 130x45.{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Detected terminal: {terminal_type}{Style.RESET_ALL}")
            # Only pause if we didn't just run a command
            if len(sys.argv) < 2: 
                input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
            clear_screen()
        
        time.sleep(0.3)

    # Welcome and get starting directory
    # If using skip_welcome, current_dir is already set by the action
    if not skip_welcome:
        start_path = None
        if len(sys.argv) > 1 and os.path.isdir(sys.argv[1]):
            start_path = os.path.abspath(sys.argv[1])
        
        if start_path:
            current_dir = start_path
        else:
            current_dir = show_welcome_message()
    
    # State
    current_page = 0
    force_rescan = False
    cache = get_cache()

    while True:
        # Validate directory
        if not os.path.isdir(current_dir):
            print(f"{Fore.RED}Directory not found: {current_dir}{Style.RESET_ALL}")
            current_dir = os.path.expanduser("~")
            current_page = 0
            force_rescan = True

        # Get directory contents
        items, is_cached = list_directory_cached(current_dir, force_rescan=force_rescan)
        force_rescan = False

        # Pagination
        total_items = len(items)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        current_page = max(0, min(current_page, total_pages - 1)) if total_pages > 0 else 0

        # Display
        display_directory(
            current_dir, items, current_page, items_per_page,
            is_cached=is_cached,
            sort_mode=cache.sort_mode,
            show_hidden=cache.show_hidden,
            filter_text=cache.filter_text
        )
        
        show_navigation_options(current_page, total_pages, cache.show_hidden, cache.sort_mode)

        # Get input
        choice = input(f"\n{Fore.CYAN}> {Fore.YELLOW}").strip()
        print(f"{Style.RESET_ALL}", end="")

        if not choice:
            continue

        # --- QUIT ---
        if choice == 'q':
            print(f"\n{Fore.GREEN}{Style.BRIGHT}Thanks for using DiskMan V3!{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Made with ❤️  by SamSeen{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}☕ If you found this useful: {Fore.WHITE}https://buymeacoffee.com/samseen{Style.RESET_ALL}\n")
            break

        # --- HELP ---
        elif choice == '?' or choice == 'help':
            show_help()

        # --- RESCAN ---
        elif choice == 'r':
            force_rescan = True

        # --- HOME ---
        elif choice == '~':
            current_dir = os.path.expanduser("~")
            current_page = 0

        # --- TOGGLE HIDDEN ---
        elif choice == 'h':
            new_state = cache.toggle_hidden()
            # Refresh view without rescan
            continue

        # --- SORT CYCLE ---
        elif choice == 's':
            new_mode = cache.cycle_sort()
            continue

        # --- FILTER ---
        elif choice.startswith('f') and not choice.startswith('F'):
            filter_text = choice[1:].strip() if len(choice) > 1 else None
            cache.set_filter(filter_text if filter_text else None)
            current_page = 0
            continue

        # --- DEEP SEARCH ---
        elif choice.startswith('F ') or choice.startswith('/ '):
            search_text = choice[2:].strip()
            if search_text:
                results = cache.search_files(search_text)
                scan_root = cache.get_scan_root() or current_dir
                action = show_search_results(results, search_text, scan_root)
                if action:
                    if action[0] == 'goto':
                        current_dir = action[1]
                        current_page = 0
                    elif action[0] == 'open':
                        open_file_explorer(action[1], os.path.basename(action[1]))
                        input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- ITEMS PER PAGE ---
        elif choice.startswith('l') and choice[1:].strip().isdigit():
            new_limit = int(choice[1:].strip())
            if 5 <= new_limit <= 50:
                items_per_page = new_limit
                current_page = 0
            else:
                print(f"\n{Fore.RED}Limit must be 5-50{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
            continue

        # --- GO TO SCAN ROOT ---
        elif choice == '.':
            scan_root = cache.get_scan_root()
            if scan_root and os.path.isdir(scan_root):
                current_dir = scan_root
                current_page = 0
            else:
                print(f"\n{Fore.YELLOW}No cached scan root available{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- GO UP ---
        elif choice.startswith('..'):
            levels = 1
            suffix = choice[2:]
            if suffix == '':
                levels = 1
            elif suffix.isdigit():
                levels = int(suffix)
            elif suffix.startswith('/') and suffix[1:].isdigit():
                levels = int(suffix[1:])
            elif suffix.startswith('.'):
                levels = len(choice) - 1
            
            new_dir = current_dir
            for _ in range(levels):
                parent = os.path.dirname(new_dir)
                if parent == new_dir:
                    break
                new_dir = parent
            
            if new_dir != current_dir:
                current_dir = new_dir
                current_page = 0

        # --- GO TO DIRECTORY ---
        elif choice.startswith('g '):
            target = choice[2:].strip()
            if os.path.isdir(target):
                current_dir = os.path.abspath(target)
                current_page = 0
            else:
                print(f"\n{Fore.RED}Not found: {target}{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- PAGINATION ---
        elif choice == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1

        # --- OPEN IN FINDER ---
        elif choice.startswith('o ') and choice[2:].strip():
            sel = choice[2:].strip()
            indices = parse_selection(sel, total_items)
            if indices:
                idx = indices[0]
                name = items[idx][0]
                item_path = os.path.join(current_dir, name)
                open_file_explorer(item_path, name)
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- DELETE (to Trash) ---
        elif choice.startswith('d ') and choice[2:].strip():
            sel = choice[2:].strip()
            indices = parse_selection(sel, total_items)
            if indices:
                item_details = []
                for idx in indices:
                    name = items[idx][0]
                    path = os.path.join(current_dir, name)
                    details = get_item_details(path)
                    if details:
                        item_details.append(details)
                
                if item_details and show_delete_confirmation(item_details, use_trash=True):
                    for details in item_details:
                        success, msg = delete_item(details['path'], use_trash=True)
                        if success:
                            print(f"{Fore.GREEN}✓ {details['name']}: {msg}{Style.RESET_ALL}")
                            remove_from_cache(details['path'])
                        else:
                            print(f"{Fore.RED}✗ {details['name']}: {msg}{Style.RESET_ALL}")
                    force_rescan = True
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- PERMANENT DELETE ---
        elif choice.startswith('D ') and choice[2:].strip():
            sel = choice[2:].strip()
            indices = parse_selection(sel, total_items)
            if indices:
                item_details = []
                for idx in indices:
                    name = items[idx][0]
                    path = os.path.join(current_dir, name)
                    details = get_item_details(path)
                    if details:
                        item_details.append(details)
                
                if item_details and show_delete_confirmation(item_details, use_trash=False):
                    for details in item_details:
                        success, msg = delete_item(details['path'], use_trash=False)
                        if success:
                            print(f"{Fore.GREEN}✓ {details['name']}: {msg}{Style.RESET_ALL}")
                            remove_from_cache(details['path'])
                        else:
                            print(f"{Fore.RED}✗ {details['name']}: {msg}{Style.RESET_ALL}")
                    force_rescan = True
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- MOVE ---
        elif choice.startswith('m '):
            parts = choice[2:].strip().split(' ', 1)
            if len(parts) == 2:
                sel, dest = parts
                indices = parse_selection(sel, total_items)
                if indices and os.path.isdir(dest):
                    for idx in indices:
                        name = items[idx][0]
                        path = os.path.join(current_dir, name)
                        success, result = move_item(path, dest)
                        if success:
                            print(f"{Fore.GREEN}✓ Moved {name}{Style.RESET_ALL}")
                            remove_from_cache(path)
                        else:
                            print(f"{Fore.RED}✗ {name}: {result}{Style.RESET_ALL}")
                    force_rescan = True
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Invalid destination.{Style.RESET_ALL}")
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- COPY ---
        elif choice.startswith('c '):
            parts = choice[2:].strip().split(' ', 1)
            if len(parts) == 2:
                sel, dest = parts
                indices = parse_selection(sel, total_items)
                if indices and os.path.isdir(dest):
                    for idx in indices:
                        name = items[idx][0]
                        path = os.path.join(current_dir, name)
                        success, result = copy_item(path, dest)
                        if success:
                            print(f"{Fore.GREEN}✓ Copied {name}{Style.RESET_ALL}")
                        else:
                            print(f"{Fore.RED}✗ {name}: {result}{Style.RESET_ALL}")
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}Invalid destination.{Style.RESET_ALL}")
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- EXTENSION STATS ---
        elif choice == 'e':
            stats = cache.get_extension_stats(current_dir)
            total = sum(stats.values())
            show_extension_stats(stats, total)

        # --- BOOKMARKS ---
        elif choice.startswith('b'):
            if choice == 'b':
                # Show bookmarks
                bm_list = list_bookmarks()
                bm_choice = show_bookmarks(bm_list)
                if bm_choice.startswith('b') and bm_choice[1:].isdigit():
                    path = get_bookmark(int(bm_choice[1:]))
                    if path and os.path.isdir(path):
                        current_dir = path
                        current_page = 0
            elif choice == 'b+':
                success, msg = add_bookmark(current_dir)
                print(f"{Fore.GREEN if success else Fore.RED}{msg}{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
            elif choice.startswith('b-') and choice[2:].strip().isdigit():
                idx = int(choice[2:].strip())
                success, msg = remove_bookmark(idx)
                print(f"{Fore.GREEN if success else Fore.RED}{msg}{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
            elif choice[1:].isdigit():
                idx = int(choice[1:])
                path = get_bookmark(idx)
                if path and os.path.isdir(path):
                    current_dir = path
                    current_page = 0
                else:
                    print(f"{Fore.RED}Invalid bookmark.{Style.RESET_ALL}")
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- EXPORT ---
        elif choice == 'x':
            success, result = export_report(current_dir, items)
            if success:
                print(f"\n{Fore.GREEN}✓ Exported to: {result}{Style.RESET_ALL}")
            else:
                print(f"\n{Fore.RED}Export failed: {result}{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- DUPLICATES ---
        elif choice == 'dup':
            dups = cache.find_duplicates(current_dir)
            action = show_duplicates(dups)
            if action:
                if action[0] == 'goto':
                    current_dir = action[1]
                    current_page = 0
                elif action[0] == 'open':
                    open_file_explorer(action[1], os.path.basename(action[1]))
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- LARGEST FILES (BigTree functionality) ---
        elif choice == 'top' or choice.startswith('top '):
            # Parse optional limit (default 20)
            limit = 20
            if choice.startswith('top ') and choice[4:].strip().isdigit():
                limit = min(100, int(choice[4:].strip()))
            
            files = cache.get_largest_files(limit=limit)
            scan_root = cache.get_scan_root() or current_dir
            action = show_largest_files(files, scan_root)
            
            if action:
                if action[0] == 'goto':
                    current_dir = action[1]
                    current_page = 0
                elif action[0] == 'open':
                    open_file_explorer(action[1], os.path.basename(action[1]))
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
                elif action[0] == 'delete':
                    details = get_item_details(action[1])
                    if details and show_delete_confirmation(details, use_trash=True):
                        success, msg = delete_item(action[1], use_trash=True)
                        if success:
                            print(f"{Fore.GREEN}✓ Deleted: {os.path.basename(action[1])}{Style.RESET_ALL}")
                            remove_from_cache(action[1])
                            force_rescan = True
                        else:
                            print(f"{Fore.RED}✗ {msg}{Style.RESET_ALL}")
                        input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- SYSTEM CACHE CLEANER ---
        elif choice == 'clean':
            cache_folders = scan_cache_folders()
            action = show_cache_cleaner(cache_folders)
            
            if action:
                if action[0] == 'goto':
                    current_dir = action[1]
                    current_page = 0
                    force_rescan = True
                elif action[0] == 'open':
                    open_file_explorer(action[1], os.path.basename(action[1]))
                    input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")
                elif action[0] == 'clear':
                    folder_info = action[1]
                    path, name, desc, size, _ = folder_info
                    
                    # Confirm clear
                    print(f"\n{Fore.RED}{Style.BRIGHT}⚠️  CLEAR FOLDER CONTENTS{Style.RESET_ALL}")
                    print(f"{Fore.YELLOW}Folder: {path}{Style.RESET_ALL}")
                    print(f"{Fore.WHITE}Size: {humanize.naturalsize(size)}{Style.RESET_ALL}")
                    print(f"\n{Fore.RED}This will delete ALL contents of this folder!{Style.RESET_ALL}")
                    confirm = input(f"{Fore.RED}Type 'yes' to confirm: {Style.RESET_ALL}").strip().lower()
                    
                    if confirm == 'yes':
                        success, msg, freed = clear_folder(path)
                        if success:
                            print(f"\n{Fore.GREEN}✓ {msg} - Freed {humanize.naturalsize(freed)}{Style.RESET_ALL}")
                            if freed > 100 * 1024 * 1024:  # > 100MB freed
                                print(f"{Fore.YELLOW}☕ Glad DiskMan helped! Support: {Fore.WHITE}buymeacoffee.com/samseen{Style.RESET_ALL}")
                        else:
                            print(f"\n{Fore.RED}✗ {msg}{Style.RESET_ALL}")
                        input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- WEB DASHBOARD ---
        elif choice == 'web' or choice.startswith('web '):
            # Parse optional port
            port = 5001
            if choice.startswith('web ') and choice[4:].strip().isdigit():
                port = int(choice[4:].strip())
            
            from lib.web_server import start_dashboard
            
            print(f"\n{Fore.GREEN}🌐 Starting DiskMan Dashboard...{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Opening: {Fore.WHITE}http://localhost:{port}{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Press Ctrl+C to stop and return to CLI{Style.RESET_ALL}\n")
            
            try:
                start_dashboard(cache, current_dir, port=port)
            except KeyboardInterrupt:
                pass
            print(f"\n{Fore.GREEN}Dashboard stopped. Returning to CLI...{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        # --- NAVIGATE TO ITEM ---
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < total_items:
                name, _, is_dir, _, _ = items[idx]
                if is_dir:
                    current_dir = os.path.join(current_dir, name)
                    current_page = 0
                else:
                    # Show file preview
                    file_path = os.path.join(current_dir, name)
                    preview = get_file_preview(file_path)
                    show_file_preview(preview, file_path)
            else:
                print(f"\n{Fore.RED}Invalid selection.{Style.RESET_ALL}")
                input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")

        else:
            print(f"\n{Fore.RED}Unknown command.{Style.RESET_ALL}")
            input(f"{Fore.CYAN}Press Enter...{Style.RESET_ALL}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.GREEN}Thanks for using DiskMan V3!{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}☕ Support: {Fore.WHITE}https://buymeacoffee.com/samseen{Style.RESET_ALL}")
        sys.exit(0)
