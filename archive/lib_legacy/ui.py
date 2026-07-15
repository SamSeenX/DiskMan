#!/usr/bin/env python3
"""
User interface functions for DiskMan.
"""
import os
import time
import humanize
from colorama import Fore, Style
from .utils import clear_screen

def display_directory(directory, items, page=0, items_per_page=20, is_cached=False):
    """Display the directory contents with sizes, paginated."""
    total_items = len(items)
    total_pages = (total_items + items_per_page - 1) // items_per_page  # Ceiling division

    # Ensure page is within valid range
    page = max(0, min(page, total_pages - 1)) if total_pages > 0 else 0

    # Calculate start and end indices for current page
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)

    # Get items for current page
    page_items = items[start_idx:end_idx]

    # Clear screen
    clear_screen()

    # Cache status indicator
    cache_status = f" {Fore.GREEN}(cached){Style.RESET_ALL}" if is_cached else f" {Fore.YELLOW}(fresh scan){Style.RESET_ALL}"

    # Display header with colors
    print(f"\n{Fore.CYAN}{Style.BRIGHT}Current directory: {Fore.YELLOW}{directory}{cache_status}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Showing items {Fore.WHITE}{start_idx + 1}-{end_idx} {Fore.CYAN}of {Fore.WHITE}{total_items} {Fore.CYAN}(Page {Fore.WHITE}{page + 1} {Fore.CYAN}of {Fore.WHITE}{total_pages or 1}{Fore.CYAN}){Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'-' * 100}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{Style.BRIGHT}{'#':<4} {'Name':<40} {'Size':<15} {'%':<8} {'Type':<10}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'-' * 100}{Style.RESET_ALL}")

    total_size = sum(item[1] for item in items) if items else 0

    for i, (name, size, is_dir, is_hidden) in enumerate(page_items, start_idx + 1):
        # Truncate long filenames
        if len(name) > 37:
            display_name = name[:34] + "..."
        else:
            display_name = name

        size_str = humanize.naturalsize(size)

        # Set colors based on item type and if it's hidden
        if is_dir and is_hidden:
            item_type = "Directory"
            name_color = Fore.CYAN  # Cyan for hidden directories (more readable than dimmed blue)
            type_color = Fore.MAGENTA
        elif is_dir:
            item_type = "Directory"
            name_color = Fore.CYAN + Style.BRIGHT  # Bright cyan for normal directories
            type_color = Fore.MAGENTA
        elif is_hidden:
            item_type = "File"
            name_color = Fore.WHITE  # White for hidden files (more readable than dimmed)
            type_color = Fore.YELLOW + Style.DIM  # Slightly dimmed type indicator instead
        else:
            item_type = "File"
            name_color = Fore.WHITE + Style.BRIGHT  # Bright white for normal files
            type_color = Fore.YELLOW

        # Calculate percentage of total size and set color based on percentage
        percentage = (size / total_size * 100) if total_size > 0 else 0
        if percentage > 10:
            percentage_color = Fore.RED
            size_color = Fore.RED
        elif percentage > 5:
            percentage_color = Fore.YELLOW
            size_color = Fore.YELLOW
        else:
            percentage_color = Fore.GREEN
            size_color = Fore.GREEN
        percentage_str = f"{percentage:.1f}%"

        # Print item with colors
        print(f"{Fore.YELLOW}{i:<4} {name_color}{display_name:<40} {size_color}{size_str:<15} {percentage_color}{percentage_str:<8} {type_color}{item_type:<10}{Style.RESET_ALL}")

    print(f"{Fore.BLUE}{'-' * 100}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total size: {Fore.YELLOW}{humanize.naturalsize(total_size)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total items: {Fore.YELLOW}{total_items}{Style.RESET_ALL}")

    # Show pagination info if there are multiple pages
    if total_pages > 1:
        print(f"{Fore.CYAN}Viewing page {Fore.WHITE}{page + 1} {Fore.CYAN}of {Fore.WHITE}{total_pages}{Style.RESET_ALL}")
        if page > 0:
            print(f"{Fore.CYAN}Use '{Fore.WHITE}p{Fore.CYAN}' for previous page{Style.RESET_ALL}")
        if page < total_pages - 1:
            print(f"{Fore.CYAN}Use '{Fore.WHITE}n{Fore.CYAN}' for next page{Style.RESET_ALL}")

def show_navigation_options(current_page, total_pages, is_cached=False):
    """Display navigation options."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}Navigation options:{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}number{Fore.CYAN}: Navigate to item by number (1, 2, 3, ...){Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}o number{Fore.CYAN}: Open parent folder and highlight item (e.g., 'o 1'){Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}d number{Fore.CYAN}: Delete file or folder with smart confirmation (e.g., 'd 1'){Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}g path{Fore.CYAN} : Go to specific directory (e.g., 'g /Users/Documents'){Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}..{Fore.CYAN}    : Go up one level (or {Fore.YELLOW}..3{Fore.CYAN} to go up 3 levels){Style.RESET_ALL}")
    if current_page > 0:
        print(f"  {Fore.YELLOW}p{Fore.CYAN}     : Previous page{Style.RESET_ALL}")
    if current_page < total_pages - 1:
        print(f"  {Fore.YELLOW}n{Fore.CYAN}     : Next page{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}r{Fore.CYAN}     : Rescan current directory (refresh data){Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}q{Fore.CYAN}     : Quit{Style.RESET_ALL}")

def show_welcome_message():
    """Display a welcome message when the program starts."""
    # Clear screen
    clear_screen()

    # Get current directory
    current_dir = os.getcwd()

    # ASCII art logo for DiskMan
    logo = [

"    ___ _     _                       ",
"   /   (_)___| | __ /\/\   __ _ _ __  ",
"  / /\ / / __| |/ //    \ / _` | '_ \ ",
" / /_//| \__ \   </ /\/\ \ (_| | | | |",
"/___,' |_|___/_|\_\/    \/\__,_|_| |_|",


        "                                ",
        " .---.       .---.              ",
        " |o_o |     /     \\     .--------------------.",
        " |:_/ |    /  / \\  \\   /|                    |\\",
        "//    \\ \\ /  / | \\  \\ / |    DISK SPACE      | \\",
        "(|     | /  /  |  \\  \\  |     ANALYZER       |  )",
        "/'\\_   _/  /   |   \\  \\ |    by SamSeen      | /",
        "\\___)=(___/    |    \\__\\|____________________|/"
    ]

    # Display logo with colors
    print("\n")
    # First part - DiskMan text logo in cyan
    for i in range(5):
        print(f"{Fore.CYAN}{Style.BRIGHT}{logo[i]}{Style.RESET_ALL}")

    # Second part - Disk graphic with multiple colors
    print(f"{Fore.WHITE}{logo[5]}{Style.RESET_ALL}")  # Empty line
    print(f"{Fore.GREEN}{Style.BRIGHT}{logo[6]}{Style.RESET_ALL}")  # Computer top
    print(f"{Fore.GREEN}{Style.BRIGHT}{logo[7]}{Style.RESET_ALL}")  # Computer face
    print(f"{Fore.GREEN}{Style.BRIGHT}{logo[8]}{Style.RESET_ALL}")  # Computer middle

    # For the disk part, use a different color to make it stand out
    disk_text_line = logo[9]
    text_part1 = disk_text_line[:25]  # start
    text_part2 = disk_text_line[25:39]  # mid
    text_part3 = disk_text_line[39:]  # end
    print(f"{Fore.GREEN}{Style.BRIGHT}{text_part1}{Fore.MAGENTA}{Style.BRIGHT}{text_part2}{Fore.GREEN}{Style.BRIGHT}{text_part3}{Style.RESET_ALL}")

    # For the text inside the disk, use a different color
    disk_text_line = logo[10]
    text_part1 = disk_text_line[:25]  # start
    text_part2 = disk_text_line[25:39]  # mid
    text_part3 = disk_text_line[39:]  # end
    print(f"{Fore.GREEN}{Style.BRIGHT}{text_part1}{Fore.MAGENTA}{Style.BRIGHT}{text_part2}{Fore.GREEN}{Style.BRIGHT}{text_part3}{Style.RESET_ALL}")

    # For the analyzer text line
    disk_text_line = logo[11]
    text_part1 = disk_text_line[:25]  # start
    text_part2 = disk_text_line[25:39]  # mid
    text_part3 = disk_text_line[39:]  # end
    print(f"{Fore.GREEN}{Style.BRIGHT}{text_part1}{Fore.MAGENTA}{Style.BRIGHT}{text_part2}{Fore.GREEN}{Style.BRIGHT}{text_part3}{Style.RESET_ALL}")

    # For the SamSeen line
    samseen_line = logo[12]
    samseen_part1 = samseen_line[:60]  # Computer part
    samseen_part2 = samseen_line[60:]  # "by SamSeen" part
    print(f"{Fore.GREEN}{Style.BRIGHT}{samseen_part1}{Fore.MAGENTA}{Style.BRIGHT}{samseen_part2}{Style.RESET_ALL}")  # Computer base

    # Display welcome message
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}{'Welcome to DiskMan (Disk Manager) by SamSeen':^60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}")
    print(f"\n{Fore.WHITE}DiskMan helps you visualize and manage disk space usage.{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Features:{Style.RESET_ALL}")
    print(f"{Fore.GREEN}• {Fore.WHITE}View file and folder sizes sorted by largest first{Style.RESET_ALL}")
    print(f"{Fore.GREEN}• {Fore.WHITE}Navigate through directories and explore your file system{Style.RESET_ALL}")
    print(f"{Fore.GREEN}• {Fore.WHITE}Open files and folders directly from the program{Style.RESET_ALL}")
    print(f"{Fore.GREEN}• {Fore.WHITE}Paginated display for better navigation{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}")

    # Ask for starting directory
    print(f"\n{Fore.CYAN}Enter a directory path to start, or press Enter to use current directory:{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Current directory: {Fore.YELLOW}{current_dir}{Style.RESET_ALL}")
    user_dir = input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()

    if user_dir:
        # User provided a directory
        if os.path.isdir(user_dir):
            return os.path.abspath(user_dir)
        else:
            print(f"\n{Fore.RED}Directory not found: {user_dir}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Using current directory instead.{Style.RESET_ALL}")
            time.sleep(1.5)  # Give user time to read the message
            return current_dir
    else:
        # Use current directory
        return current_dir

def clean_text_for_confirmation(text):
    """Clean text for confirmation by removing special characters and converting to lowercase.

    Args:
        text (str): The text to clean

    Returns:
        str: Cleaned text (lowercase with no spaces or special characters)
    """
    import re
    # Convert to lowercase and remove spaces and special characters
    return re.sub(r'[^a-z0-9]', '', text.lower())

def show_delete_confirmation(item_details):
    """Display a confirmation screen for deleting a file or folder.

    Args:
        item_details (dict): Dictionary containing item details

    Returns:
        bool: True if user confirms deletion, False otherwise
    """
    if not item_details:
        print(f"{Fore.RED}Error: No item details provided.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        return False

    # Clear screen
    clear_screen()

    # Get item information
    original_name = item_details['name']  # Store the original name
    path = item_details['path']
    size = item_details['size']
    is_dir = item_details['is_dir']
    created = item_details['created']
    modified = item_details['modified']
    accessed = item_details['accessed']

    # Display warning header
    print(f"\n{Fore.RED}{Style.BRIGHT}{'!' * 80}{Style.RESET_ALL}")
    print(f"{Fore.RED}{Style.BRIGHT}{'WARNING: PERMANENT DELETION':^80}{Style.RESET_ALL}")
    print(f"{Fore.RED}{Style.BRIGHT}{'!' * 80}{Style.RESET_ALL}")

    # Display item information
    print(f"\n{Fore.RED}{Style.BRIGHT}You are about to delete the following {Fore.WHITE}{'DIRECTORY' if is_dir else 'FILE'}{Fore.RED}:{Style.RESET_ALL}")
    print(f"\n{Fore.YELLOW}{Style.BRIGHT}{original_name}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'-' * 80}{Style.RESET_ALL}")

    # Display detailed information
    print(f"{Fore.CYAN}Path:           {Fore.WHITE}{path}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Size:           {Fore.WHITE}{humanize.naturalsize(size)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Type:           {Fore.WHITE}{'Directory' if is_dir else 'File'}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Created:        {Fore.WHITE}{created.strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Last Modified:  {Fore.WHITE}{modified.strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Last Accessed:  {Fore.WHITE}{accessed.strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}")

    # If it's a directory, show contents
    if is_dir and 'contents' in item_details:
        contents = item_details['contents']
        item_count = item_details.get('item_count', len(contents))

        print(f"\n{Fore.CYAN}Directory contains {Fore.WHITE}{item_count}{Fore.CYAN} items:{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'-' * 80}{Style.RESET_ALL}")

        for i, item in enumerate(contents):
            if isinstance(item, str):
                # This is the "more items not shown" message
                print(f"{Fore.YELLOW}{item}{Style.RESET_ALL}")
            else:
                # This is a file/directory entry
                name = item['name']
                is_subdir = item['is_dir']
                size = item['size']

                # Truncate long filenames
                if len(name) > 40:
                    display_name = name[:37] + "..."
                else:
                    display_name = name

                # Set colors based on item type
                if is_subdir:
                    name_color = Fore.CYAN + Style.BRIGHT
                    type_str = "Directory"
                else:
                    name_color = Fore.WHITE + Style.BRIGHT
                    type_str = "File"

                print(f"{Fore.YELLOW}{i+1:<4} {name_color}{display_name:<40} {Fore.GREEN}{humanize.naturalsize(size):<15} {Fore.MAGENTA}{type_str}{Style.RESET_ALL}")

    # Display warning message
    print(f"\n{Fore.RED}{Style.BRIGHT}{'!' * 80}{Style.RESET_ALL}")
    print(f"{Fore.RED}{Style.BRIGHT}WARNING: This action is {Fore.WHITE}PERMANENT{Fore.RED} and {Fore.WHITE}CANNOT BE UNDONE{Fore.RED}!{Style.RESET_ALL}")
    print(f"{Fore.RED}{Style.BRIGHT}All data in this {'directory' if is_dir else 'file'} will be permanently lost.{Style.RESET_ALL}")
    print(f"{Fore.RED}{Style.BRIGHT}{'!' * 80}{Style.RESET_ALL}")

    # Get raw confirmation string (first 10 chars of original_name or all if shorter)
    raw_confirm_str = original_name[:10] if len(original_name) >= 10 else original_name

    # Clean the confirmation string (lowercase, no spaces or special characters)
    confirm_str = clean_text_for_confirmation(raw_confirm_str)

    # Ask for confirmation
    print(f"\n{Fore.YELLOW}To confirm deletion, type {Fore.RED}{Style.BRIGHT}\"{confirm_str}\"{Style.RESET_ALL}{Fore.YELLOW} (lowercase with no spaces or special characters):{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}(or type '{Fore.WHITE}c{Fore.YELLOW}' to abort){Style.RESET_ALL}")

    # Get user input
    user_input = input(f"{Fore.RED}> {Style.RESET_ALL}").strip()

    # Check if user wants to cancel
    if user_input.lower() == 'c':
        print(f"\n{Fore.GREEN}Deletion cancelled.{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        return False

    # Clean the user input for comparison
    cleaned_user_input = clean_text_for_confirmation(user_input)

    # Check if confirmation matches
    if cleaned_user_input == confirm_str:
        return True
    else:
        print(f"\n{Fore.RED}Confirmation failed. Deletion cancelled.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}You entered: {Fore.WHITE}{user_input}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Expected: {Fore.WHITE}{confirm_str}{Style.RESET_ALL}")
        input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        return False

def display_big_tree(directory, files, page=0, items_per_page=20, current_filter=None):
    """Display the list of large files, paginated."""
    total_items = len(files)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    page = max(0, min(page, total_pages - 1)) if total_pages > 0 else 0
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    page_files = files[start_idx:end_idx]

    clear_screen()
    print(f"\n{Fore.CYAN}{Style.BRIGHT}Scanned directory: {Fore.YELLOW}{directory}{Style.RESET_ALL}")
    if current_filter:
        print(f"{Fore.CYAN}Current filter: {Fore.YELLOW}{current_filter}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Showing files {Fore.WHITE}{start_idx + 1}-{end_idx} {Fore.CYAN}of {Fore.WHITE}{total_items} {Fore.CYAN}(Page {Fore.WHITE}{page + 1} {Fore.CYAN}of {Fore.WHITE}{total_pages or 1}{Fore.CYAN}){Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'-' * 110}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{Style.BRIGHT}{'#':<4} {'File Name':<40} {'Size':<15} {'Subfolder'}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'-' * 110}{Style.RESET_ALL}")

    for i, (file_path, name, size) in enumerate(page_files, start_idx + 1):
        if len(name) <= 37:
            display_name = name
        else:
            name_without_ext, ext = os.path.splitext(name)
            if ext: # If there is an extension
                ext_len = len(ext)
                max_base_len = 37 - ext_len - 3 # 3 for "..."
                if max_base_len < 0: # If extension + ellipsis is already too long
                    display_name = "..." + ext[-34:] # Show part of extension
                else:
                    truncated_base = name_without_ext[:max_base_len]
                    display_name = truncated_base + "..." + ext
            else: # No extension, just truncate the name
                display_name = name[:34] + "..."
        size_str = humanize.naturalsize(size)
        subfolder = os.path.dirname(file_path).replace(directory, '.', 1)

        size_color = Fore.GREEN
        if size > 1024 * 1024 * 1024: # 1 GB
            size_color = Fore.RED
        elif size > 1024 * 1024 * 100: # 100 MB
            size_color = Fore.YELLOW

        print(f"{Fore.YELLOW}{i:<4} {Fore.WHITE}{display_name:<40} {size_color}{size_str:<15} {Fore.CYAN}{subfolder}{Style.RESET_ALL}")

    print(f"{Fore.BLUE}{'-' * 110}{Style.RESET_ALL}")
    total_size = sum(f[2] for f in files)
    print(f"{Fore.CYAN}Total size of all files: {Fore.YELLOW}{humanize.naturalsize(total_size)}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total number of files: {Fore.YELLOW}{total_items}{Style.RESET_ALL}")

def show_welcome_message_big_tree():
    """Display a welcome message for BigTree."""
    clear_screen()
    logo = [
        " ____  _  _  ____                    ",
        "(_  _)(_)(_)(_  _)                   ",
        "  )(   _  _   )(   ____  ____  ____ ",
        " (__) (_)(_) (__) (____)(_  _)(_  _)",
        "                                    ",
        "        Large File Finder           ",
    ]
    for line in logo:
        print(f"{Fore.GREEN}{Style.BRIGHT}{line}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}{'Welcome to BigTree by SamSeen':^60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'=' * 60}{Style.RESET_ALL}")
    print(f"\n{Fore.WHITE}BigTree helps you find the largest files in a directory and its subdirectories.{Style.RESET_ALL}")
    
    current_dir = os.getcwd()
    print(f"\n{Fore.CYAN}Enter a directory path to scan, or press Enter to use current directory:{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Current directory: {Fore.YELLOW}{current_dir}{Style.RESET_ALL}")
    user_dir = input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()

    if user_dir and os.path.isdir(user_dir):
        return os.path.abspath(user_dir)
    return current_dir

def show_navigation_options_big_tree(current_page, total_pages):
    """Display navigation options for BigTree."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}Navigation options:{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}f <text>{Fore.CYAN}: Filter by file name (e.g., 'f .mp4' or 'f final'). 'f' to clear.{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}o <index>{Fore.CYAN}: Open file location in Finder (e.g., 'o 1'){Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}g <path>{Fore.CYAN} : Go to specific directory (e.g., 'g /Users/Documents'){Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}..{Fore.CYAN}    : Go up one level{Style.RESET_ALL}")
    if current_page > 0:
        print(f"  {Fore.YELLOW}p{Fore.CYAN}     : Previous page{Style.RESET_ALL}")
    if current_page < total_pages - 1:
        print(f"  {Fore.YELLOW}n{Fore.CYAN}     : Next page{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}m <indices>{Fore.CYAN}: Move files to a new directory (e.g., 'm 1,3,5 /path/to/dest' or 'm 1-5 /path/to/dest'){Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}q{Fore.CYAN}     : Quit{Style.RESET_ALL}")
