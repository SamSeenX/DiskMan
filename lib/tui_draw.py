import os
import curses
import time
import humanize
from datetime import datetime
from .curses_cache import du_cache, get_single_dir_size
from .theme import THEMES
from .image_compress import get_funny_loading_message

SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
__version__ = "4.2.3-curses"


def get_string_input(stdscr, prompt, default_val=None, autocomplete_path=False, initial_value=""):
    """Safely reads string input from user in the curses footer line with optional default fallback. Supports ESC key to cancel and TAB autocompletion."""
    height, width = stdscr.getmaxyx()
    display_prompt = prompt
    if default_val is not None:
        display_prompt = f"{prompt} [{default_val}]: "
    elif not (prompt.endswith(":") or prompt.endswith("?")):
        display_prompt = f"{prompt}: "

    # Block waiting for keys during input loop
    stdscr.timeout(-1)
    curses.curs_set(1) # Enable cursor visibility
    
    input_str = initial_value
    start_x = 2 + len(display_prompt)
    max_len = 80
    candidates_display = ""
    
    while True:
        # Clear typing row first
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(height - 3, 2, " " * (width - 4), curses.color_pair(4))
        # Clear the matches line above the input prompt
        stdscr.addstr(height - 4, 2, " " * (width - 4), curses.color_pair(2))
        
        # Draw prompt text
        stdscr.addstr(height - 3, 2, display_prompt, curses.color_pair(4))
        stdscr.attroff(curses.A_BOLD)
        
        # Draw candidates if any
        if candidates_display:
            stdscr.addstr(height - 4, 2, candidates_display[:width-4], curses.color_pair(3))
            
        # Draw typed content so far
        stdscr.addstr(height - 3, start_x, input_str, curses.color_pair(2))
        
        # Position flashing terminal cursor at end of text
        stdscr.move(height - 3, start_x + len(input_str))
        stdscr.refresh()
        
        ch = stdscr.getch()
        
        # Clear matches display on any normal keypress except TAB
        if ch != 9:
            candidates_display = ""
            
        if ch == 27: # ESCAPE key (cancel)
            input_str = None
            break
        elif ch in [10, 13]: # ENTER key (accept)
            break
        elif ch in [curses.KEY_BACKSPACE, 127, 8]: # Backspace key triggers
            if len(input_str) > 0:
                input_str = input_str[:-1]
        elif ch == 9: # TAB key (autocompletion)
            if autocomplete_path and input_str:
                path_expanded = os.path.expanduser(input_str)
                if input_str.endswith('/') or os.path.isdir(path_expanded):
                    dir_part = path_expanded
                    base_part = ""
                else:
                    dir_part = os.path.dirname(path_expanded)
                    base_part = os.path.basename(path_expanded)
                
                try:
                    if not dir_part:
                        dir_part = "."
                    dirs = []
                    for name in os.listdir(dir_part):
                        full_path = os.path.join(dir_part, name)
                        if os.path.isdir(full_path) and not name.startswith('.'):
                            if name.lower().startswith(base_part.lower()):
                                dirs.append(name)
                    
                    if len(dirs) == 1:
                        completed = dirs[0]
                        input_str = (input_str[:-len(base_part)] if base_part else input_str) + completed + "/"
                    elif len(dirs) > 1:
                        common = os.path.commonprefix(dirs)
                        if common and len(common) > len(base_part):
                            input_str = (input_str[:-len(base_part)] if base_part else input_str) + common
                        candidates_display = "Matches: " + "  ".join([d + "/" for d in sorted(dirs)])
                except Exception:
                    pass
        elif 32 <= ch <= 126: # Regular printable text characters
            if len(input_str) < max_len:
                input_str += chr(ch)
                
    curses.curs_set(0) # Hide cursor
    stdscr.timeout(100) # Restore standard non-blocking timeout
    
    if input_str is None:
        return None # Explicitly canceled
    if not input_str and default_val is not None:
        return str(default_val)
    return input_str


def show_modal_list(stdscr, title, options, draw_bg_fn):
    """Draws an interactive modal selection overlay dialog."""
    selected = 0
    height, width = stdscr.getmaxyx()
    
    if not options:
        options = ["<No items>"]
        is_empty = True
    else:
        is_empty = False
        
    while True:
        draw_bg_fn() # Draw current background
        
        # Modal dims sizing
        modal_w = min(width - 10, 60)
        modal_h = min(height - 6, len(options) + 4)
        start_y = (height - modal_h) // 2
        start_x = (width - modal_w) // 2
        
        border_attr = curses.color_pair(4) | curses.A_BOLD
        
        # Fill dialog background space with clean spaces
        for y in range(start_y, start_y + modal_h):
            for x in range(start_x, start_x + modal_w):
                try:
                    stdscr.addch(y, x, ' ', curses.color_pair(2))
                except curses.error:
                    pass
                
        # Draw framing boxes
        try:
            stdscr.addstr(start_y, start_x, '┌' + '─' * (modal_w - 2) + '┐', border_attr)
            for y in range(start_y + 1, start_y + modal_h - 1):
                stdscr.addstr(y, start_x, '│', border_attr)
                stdscr.addstr(y, start_x + modal_w - 1, '│', border_attr)
            stdscr.addstr(start_y + modal_h - 1, start_x, '└' + '─' * (modal_w - 2) + '┘', border_attr)
        except curses.error:
            pass
        
        # Title
        title_str = f" {title} "
        stdscr.addstr(start_y, start_x + (modal_w - len(title_str)) // 2, title_str, curses.color_pair(1) | curses.A_BOLD)
        
        # Draw selectable items inside frame
        list_h = modal_h - 3
        for i in range(list_h):
            idx = i
            if idx >= len(options):
                break
            opt = options[idx]
            
            # Selection Highlight
            attr = curses.A_REVERSE | curses.A_BOLD if idx == selected and not is_empty else curses.A_NORMAL
            color = curses.color_pair(1) if idx == selected else curses.color_pair(2)
            
            opt_str = str(opt)
            display_opt = opt_str[:modal_w - 6]
            try:
                stdscr.addstr(start_y + 2 + i, start_x + 3, f"{display_opt:<{modal_w-6}}", color | attr)
            except curses.error:
                pass
                
        stdscr.refresh()
        ch = stdscr.getch()
        
        if ch in [curses.KEY_ENTER, 10, 13]: # ENTER select
            if is_empty:
                return None
            return selected
        elif ch in [27, ord('q'), ord('Q')]: # Cancel
            return None
        elif ch == curses.KEY_UP:
            if selected > 0:
                selected -= 1
        elif ch == curses.KEY_DOWN:
            if selected < len(options) - 1:
                selected += 1


def draw_screen(stdscr, current_dir, items, selected_idx, scroll_offset, spinner_frame, status_msg=None):
    stdscr.erase()
    height, width = stdscr.getmaxyx()

    # Minimum terminal size check
    if height < 15 or width < 70:
        stdscr.addstr(0, 0, "Terminal too small!", curses.color_pair(5) | curses.A_BOLD)
        stdscr.addstr(1, 0, f"Current: {width}x{height}. Minimum: 70x15.", curses.color_pair(2))
        stdscr.refresh()
        return scroll_offset

    # Border attribute (Dimmed Border color pair)
    border_attr = curses.color_pair(6) | curses.A_DIM

    # Split Column calculation (Left pane is 70% width)
    split_col = int(width * 0.70)

    # Safe drawing helper wrapper to suppress curses ERR code when writing to the bottom-right character
    def safe_addstr(y, x, s, attr=curses.A_NORMAL):
        try:
            stdscr.addstr(y, x, s, attr)
        except curses.error:
            pass

    # Draw horizontal borders
    safe_addstr(0, 0, '┌' + '─' * (width - 2) + '┐', border_attr)
    # Row 5 becomes a full-width divider separator, giving padding space below the column headers
    safe_addstr(3, 0, '├' + '─' * (split_col - 1) + '┬' + '─' * (width - split_col - 2) + '┤', border_attr)
    safe_addstr(5, 0, '├' + '─' * (split_col - 1) + '┼' + '─' * (width - split_col - 2) + '┤', border_attr)
    safe_addstr(height - 4, 0, '├' + '─' * (split_col - 1) + '┴' + '─' * (width - split_col - 2) + '┤', border_attr)
    safe_addstr(height - 1, 0, '└' + '─' * (width - 2) + '┘', border_attr)

    # Draw vertical border columns
    safe_addstr(1, 0, '│', border_attr)
    safe_addstr(1, width - 1, '│', border_attr)
    safe_addstr(2, 0, '│', border_attr)
    safe_addstr(2, width - 1, '│', border_attr)

    for y in range(4, height - 4):
        safe_addstr(y, 0, '│', border_attr)
        safe_addstr(y, split_col, '│', border_attr)
        safe_addstr(y, width - 1, '│', border_attr)

    safe_addstr(height - 3, 0, '│', border_attr)
    safe_addstr(height - 3, width - 1, '│', border_attr)
    safe_addstr(height - 2, 0, '│', border_attr)
    safe_addstr(height - 2, width - 1, '│', border_attr)

    # Top Header Box
    stdscr.attron(curses.A_BOLD)
    safe_addstr(1, 2, f" DISKMAN V4 CURSES  (V{__version__}) │ Sort: {du_cache.sort_mode.upper()} ", curses.color_pair(1))
    stdscr.attroff(curses.A_BOLD)

    # Check if there are active calculating directories in cache
    is_scanning = False
    with du_cache.calculating_dirs_lock:
        if du_cache.calculating_dirs:
            is_scanning = True

    spinner_char = SPINNER_FRAMES[spinner_frame]
    status_text = f"[ {spinner_char} SCANNING... ]" if is_scanning else "[ ✓ SCAN COMPLETE ]"
    status_color = curses.color_pair(4) if is_scanning else curses.color_pair(3)

    status_x = width - len(status_text) - 3
    if status_x > 35: # Make sure it doesn't overlap title on very narrow screens
        safe_addstr(1, status_x, status_text, status_color | curses.A_BOLD)
    
    # Path line inside header box
    safe_addstr(2, 2, "📁 ", curses.color_pair(1))
    max_path_len = width - 8
    path_display = current_dir
    if len(path_display) > max_path_len:
        path_display = "..." + path_display[-max_path_len+3:]
    safe_addstr(2, 5, path_display, curses.color_pair(2) | curses.A_BOLD)

    # Draw funny loading easter egg message if scanning
    if is_scanning and du_cache.scan_start_time is not None:
        funny_msg = get_funny_loading_message(du_cache.scan_start_time)
        if funny_msg:
            funny_x = width - len(funny_msg) - 3
            path_end_x = 5 + len(path_display)
            if funny_x > path_end_x + 3:
                safe_addstr(2, funny_x, funny_msg, curses.color_pair(4))

    # Headers for columns (Drawn at row 4, with line separation at row 5)
    col_idx_w = 4
    col_size_w = 11
    col_bar_w = 16
    col_type_w = 6
    col_name_w = split_col - col_idx_w - col_size_w - col_bar_w - col_type_w - 4 # Spacing padding


    headers = (
        f"{'#':<{col_idx_w}} "
        f"{'Name':<{col_name_w}} "
        f"{'Ratio Bar':<{col_bar_w}} "
        f"{'Size':<{col_size_w}} "
        f"{'Type':<{col_type_w}}"
    )
    safe_addstr(4, 2, headers[:split_col - 3], curses.color_pair(1) | curses.A_BOLD)

    # Draw Left Pane: directory items scrolling table list
    total_items = len(items)
    max_visible_rows = height - 10 # Rows 6 to height-5
    
    # Adjust scroll offset dynamically based on selected index
    if selected_idx < scroll_offset:
        scroll_offset = selected_idx
    elif selected_idx >= scroll_offset + max_visible_rows:
        scroll_offset = selected_idx - max_visible_rows + 1

    # Extract max size for ratio visualization bar calculations
    max_size = 1
    for name, size, is_dir, is_hid, mtime in items:
        if size > max_size:
            max_size = size

    for i in range(max_visible_rows):
        item_idx = scroll_offset + i
        if item_idx >= total_items:
            break
            
        name, size, is_dir, is_hid, mtime = items[item_idx]
        
        # Format sizes humanly
        if size >= 0:
            size_str = humanize.naturalsize(size)
        else:
            size_str = "Calculating..."
            
        # Draw visual ratio bar charts
        bar_len = 8
        if max_size > 0 and size > 0:
            ratio = size / max_size
            filled = int(ratio * bar_len)
        else:
            ratio = 0
            filled = 0
            
        filled = max(0, min(bar_len, filled))
        bar_str = "[" + "■" * filled + " " * (bar_len - filled) + "]"
        pct_str = f"{int(ratio * 100):>3}%"
        
        if ratio > 0.70:
            pct_color = curses.color_pair(5) # Red
        elif ratio > 0.35:
            pct_color = curses.color_pair(4) # Yellow
        else:
            pct_color = curses.color_pair(3) # Green

        type_str = "📁" if is_dir else "📄"
        
        # Draw columns sequentially with formatting constraints (Starts at row 6 now)
        y_pos = 6 + i
        safe_addstr(y_pos, 2, f"{item_idx+1:<{col_idx_w}}", curses.color_pair(4))
        
        # Highlights selection row
        row_attr = curses.A_REVERSE | curses.A_BOLD if item_idx == selected_idx else curses.A_NORMAL
        item_color = curses.color_pair(1) if is_dir else curses.color_pair(2)
        if item_idx == selected_idx:
            item_color = curses.color_pair(1) # selected style
        
        display_name = name[:col_name_w - 2]
        safe_addstr(y_pos, 2 + col_idx_w + 1, f"{display_name:<{col_name_w}}", item_color | row_attr)
        
        # Progress Bar and details columns
        bar_col = 2 + col_idx_w + 1 + col_name_w + 1
        safe_addstr(y_pos, bar_col, bar_str, border_attr)
        safe_addstr(y_pos, bar_col + bar_len + 3, pct_str, pct_color)
        
        size_col = bar_col + col_bar_w + 1
        safe_addstr(y_pos, size_col, f"{size_str:<{col_size_w}}", pct_color)
        
        type_col = size_col + col_size_w + 1
        safe_addstr(y_pos, type_col, f"{type_str:<{col_type_w}}", item_color)

    # Right Pane: Detailed Metadata Inspector Panel
    right_pane_width = width - split_col - 3
    right_pane_x = split_col + 2

    # Draw Pane Header (Drawn at row 4, with divider at row 5)
    safe_addstr(4, right_pane_x, " INSPECTOR ", curses.color_pair(1) | curses.A_BOLD)

    if total_items > 0 and selected_idx < total_items:
        name, size, is_dir, is_hid, mtime = items[selected_idx]
        full_path = os.path.realpath(os.path.join(current_dir, name))

        # Visual lines inside inspector panel (Formatted compactly on a single line per attribute, starting at row 6)
        lines = [
            ("Name", name, curses.color_pair(1) if is_dir else curses.color_pair(2)),
            ("Type", "Directory 📁" if is_dir else "File 📄", curses.color_pair(4)),
            ("Size", humanize.naturalsize(size) if size >= 0 else "Calculating...", curses.color_pair(3)),
            ("Bytes", f"{size:,} B" if size >= 0 else "Computing...", curses.color_pair(3)),
            ("Modified", datetime.fromtimestamp(mtime).strftime('%y-%m-%d %H:%M') if mtime > 0 else "Unknown", curses.color_pair(2))
        ]

        # Render stats metadata (Starts at row 6 now)
        current_y = 6
        for label, val, val_color in lines:
            if current_y >= height - 4:
                break
            safe_addstr(current_y, right_pane_x, f"{label}:", curses.color_pair(4) | curses.A_BOLD)
            
            val_display = str(val)
            val_x = right_pane_x + len(label) + 2
            max_val_w = right_pane_width - len(label) - 3
            if len(val_display) > max_val_w:
                val_display = val_display[:max_val_w - 3] + "..."
            
            safe_addstr(current_y, val_x, val_display, val_color)
            current_y += 1

        # Get and display top subfolders if it's a directory
        subfolders = []
        if is_dir:
            try:
                for entry in os.scandir(full_path):
                    if entry.is_dir(follow_symlinks=False):
                        if not du_cache.show_hidden and entry.name.startswith('.'):
                            continue
                        sub_path = os.path.realpath(entry.path)
                        sub_size = du_cache.sizes.get(sub_path, -1)
                        
                        # Trigger background calculation if size is unknown and not already in progress
                        if sub_size < 0:
                            with du_cache.calculating_dirs_lock:
                                if sub_path not in du_cache.calculating_dirs:
                                    du_cache.calculating_dirs.add(sub_path)
                                    def make_bg_task(p):
                                        def task():
                                            sz = get_single_dir_size(p)
                                            du_cache.sizes[p] = sz
                                            with du_cache.calculating_dirs_lock:
                                                if p in du_cache.calculating_dirs:
                                                    du_cache.calculating_dirs.remove(p)
                                                if not du_cache.calculating_dirs:
                                                    du_cache.scan_start_time = None
                                            du_cache.set_update_flag()
                                        return task
                                    du_cache.submit(make_bg_task(sub_path))
                        
                        subfolders.append((entry.name, sub_size))
            except Exception:
                pass
            
            # Sort subfolders by size descending (putting "Calculating..." at bottom)
            subfolders.sort(key=lambda x: (x[1] >= 0, x[1]), reverse=True)

        if is_dir and subfolders:
            if current_y + 4 < height - 4:
                # Draw divider line
                line = '├' + '─' * (width - split_col - 2) + '┤'
                safe_addstr(current_y, split_col, line, border_attr)
                current_y += 1
                
                safe_addstr(current_y, right_pane_x, " TOP SUBFOLDERS ", curses.color_pair(1) | curses.A_BOLD)
                current_y += 1
                
                # Draw divider under title
                safe_addstr(current_y, right_pane_x, '─' * (right_pane_width), border_attr)
                current_y += 1
                
                # Show up to 10 subfolders
                for sf_name, sf_sz in subfolders[:10]:
                    if current_y >= height - 4:
                        break
                    
                    sz_str = humanize.naturalsize(sf_sz) if sf_sz >= 0 else "Calculating..."
                    sz_color = curses.color_pair(3) if sf_sz >= 0 else curses.color_pair(4)
                    
                    # Truncate subfolder name if it exceeds pane width
                    max_name_w = right_pane_width - len(sz_str) - 6
                    if max_name_w < 5:
                        max_name_w = 5
                    
                    disp_name = sf_name
                    if len(disp_name) > max_name_w:
                        disp_name = disp_name[:max_name_w - 3] + "..."
                    
                    safe_addstr(current_y, right_pane_x, f"• {disp_name}", curses.color_pair(1))
                    safe_addstr(current_y, right_pane_x + right_pane_width - len(sz_str) - 1, sz_str, sz_color)
                    current_y += 1

        # Draw Divider Line and Help Card below metadata
        help_y = current_y + 1
        if help_y + 8 < height - 4:
            # Draw panel crossing horizontal line connecting vertical dividers (aligned on row)
            line = '├' + '─' * (width - split_col - 2) + '┤'
            safe_addstr(help_y, split_col, line, border_attr)
            
            safe_addstr(help_y + 1, right_pane_x, " SHORTCUTS CARD ", curses.color_pair(1) | curses.A_BOLD)
            
            # Sub-separator line under Shortcuts title
            safe_addstr(help_y + 2, right_pane_x, '─' * (right_pane_width), border_attr)
            
            shortcuts = [
                ("UP/DN", "Move cursor selection"),
                ("ENTER", "Go inside / Open file"),
                ("BKSP", "Go to parent folder"),
                ("G", "Go to folder path"),
                ("F / /", "Filter items in view"),
                ("A / B", "Add / Open Bookmarks"),
                ("T / U", "Top files / Duplicates"),
                ("W / X", "Clean Cache / Export CSV"),
                ("C / M", "Copy / Move items"),
                ("I", "Compress images"),
                ("S", "Cycle sort (Size/Name/Date)"),
                ("d / D", "Delete / Permanent Del"),
                ("V", "Cycle Color Themes"),
                ("R / Q", "Rescan Folder / Quit")
            ]
            
            for idx, (key, desc) in enumerate(shortcuts):
                row_y = help_y + 3 + idx
                if row_y >= height - 4:
                    break
                # Align shortcut key columns inside card
                safe_addstr(row_y, right_pane_x, f"{key:<6}", curses.color_pair(4) | curses.A_BOLD)
                safe_addstr(row_y, right_pane_x + 7, desc[:right_pane_width - 8], curses.color_pair(2))
    else:
        # Fallback empty folder notice inside pane
        safe_addstr(6, right_pane_x, "Empty folder", curses.color_pair(2) | curses.A_DIM)

    # Render dynamic CLI Status Alerts and actions hint footer rows (drawn at row height-3 and height-2)
    if status_msg:
        safe_addstr(height - 3, 2, status_msg[:width-4], curses.color_pair(4) | curses.A_BOLD)
    else:
        status_text = "Press '?' or 'H' to show help manual overlay"
        safe_addstr(height - 3, 2, status_text[:width-4], curses.color_pair(3))
        
    actions_2 = "G: Go │ D: Del │ M: Move │ C: Copy │ I: Compress │ S: Sort │ X: Export │ T: Largest │ U: Dups │ W: Clean │ V: Theme │ Q: Quit"
    safe_addstr(height - 2, 2, actions_2[:width-4], curses.color_pair(4) | curses.A_BOLD)

    stdscr.refresh()
    return scroll_offset
