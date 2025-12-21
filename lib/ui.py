#!/usr/bin/env python3
"""
Enhanced UI for DiskMan V2.
"""
import os
import time
import humanize
from datetime import datetime
from colorama import Fore, Style, Back
from .utils import clear_screen
from .cache import get_cache


def display_directory(directory, items, page=0, items_per_page=20, is_cached=False, 
                      sort_mode='size', show_hidden=True, filter_text=None):
    """Display directory contents with enhanced information."""
    total_items = len(items)
    total_pages = (total_items + items_per_page - 1) // items_per_page
    page = max(0, min(page, total_pages - 1)) if total_pages > 0 else 0
    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, total_items)
    page_items = items[start_idx:end_idx]

    clear_screen()
    
    # Title bar - calculate widths carefully
    width = 105
    cache_icon = "●" if is_cached else "○"
    cache_color = Fore.GREEN if is_cached else Fore.YELLOW
    sort_char = sort_mode[0].upper()
    hidden_icon = "👁" if show_hidden else "◌"
    
    # Build title line content (without colors for length calculation)
    # Emoji take 2 terminal columns but count as 1 in len()
    title_content = f"DISKMAN V2  {cache_icon}  [{sort_char}] {hidden_icon}"
    emoji_adjustment = 1  # 👁 takes 2 spaces
    if filter_text:
        title_content += f"  🔍 {filter_text}"
        emoji_adjustment += 1  # 🔍 takes 2 spaces
    title_padding = width - 2 - len(title_content) - emoji_adjustment
    
    # Build path line (truncate if needed)
    path_display = directory[:width-8] if len(directory) > width-8 else directory
    path_padding = width - 5 - len(path_display) - 1  # -1 for 📁 emoji
    
    print(f"\n{Fore.CYAN}╔{'═' * (width-2)}╗{Style.RESET_ALL}")
    
    # Title line with colors
    if filter_text:
        print(f"{Fore.CYAN}║{Style.RESET_ALL} {Fore.WHITE}{Style.BRIGHT}DISKMAN V2{Style.RESET_ALL}  {cache_color}{cache_icon}{Style.RESET_ALL}  {Fore.YELLOW}[{sort_char}]{Style.RESET_ALL} {hidden_icon}  {Fore.MAGENTA}🔍 {filter_text}{Style.RESET_ALL}{' ' * title_padding}{Fore.CYAN}║{Style.RESET_ALL}")
    else:
        print(f"{Fore.CYAN}║{Style.RESET_ALL} {Fore.WHITE}{Style.BRIGHT}DISKMAN V2{Style.RESET_ALL}  {cache_color}{cache_icon}{Style.RESET_ALL}  {Fore.YELLOW}[{sort_char}]{Style.RESET_ALL} {hidden_icon}{' ' * title_padding}{Fore.CYAN}║{Style.RESET_ALL}")
    
    print(f"{Fore.CYAN}╠{'═' * (width-2)}╣{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{Style.RESET_ALL} {Fore.GREEN}📁{Style.RESET_ALL} {Fore.WHITE}{Style.BRIGHT}{path_display}{Style.RESET_ALL}{' ' * path_padding}{Fore.CYAN}║{Style.RESET_ALL}")
    print(f"{Fore.CYAN}╚{'═' * (width-2)}╝{Style.RESET_ALL}")
    
    # Column headers
    print(f"{Fore.GREEN}{Style.BRIGHT}{'#':<4} {'Name':<38} {'Size':<12} {'%':<6} {'Type':<8} {'Age':<8}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * width}{Style.RESET_ALL}")

    total_size = sum(item[1] for item in items) if items else 0
    cache = get_cache()

    for i, item in enumerate(page_items, start_idx + 1):
        name, size, is_dir, is_hid, mtime = item
        
        # Truncate name
        if len(name) > 35:
            display_name = name[:32] + "..."
        else:
            display_name = name

        size_str = humanize.naturalsize(size)
        
        # Colors based on type and visibility
        if is_dir and is_hid:
            name_color = Fore.CYAN + Style.DIM
            type_str = "📁"
        elif is_dir:
            name_color = Fore.CYAN + Style.BRIGHT
            type_str = "📁"
        elif is_hid:
            name_color = Fore.WHITE + Style.DIM
            type_str = "📄"
        else:
            name_color = Fore.WHITE + Style.BRIGHT
            type_str = "📄"

        # Percentage and color
        percentage = (size / total_size * 100) if total_size > 0 else 0
        if percentage > 10:
            pct_color = Fore.RED
            size_color = Fore.RED
        elif percentage > 5:
            pct_color = Fore.YELLOW
            size_color = Fore.YELLOW
        else:
            pct_color = Fore.GREEN
            size_color = Fore.GREEN
        pct_str = f"{percentage:.1f}%"

        # Age indicator
        age_cat = cache.get_age_color(mtime)
        if age_cat == 'old':
            age_str = f"{Fore.RED}◉ old{Style.RESET_ALL}"
        elif age_cat == 'medium':
            age_str = f"{Fore.YELLOW}◉ mid{Style.RESET_ALL}"
        else:
            age_str = f"{Fore.GREEN}◉ new{Style.RESET_ALL}"

        print(f"{Fore.YELLOW}{i:<4} {name_color}{display_name:<38}{Style.RESET_ALL} "
              f"{size_color}{size_str:<12}{Style.RESET_ALL} {pct_color}{pct_str:<6}{Style.RESET_ALL} "
              f"{type_str:<8} {age_str}")

    print(f"{Fore.BLUE}{'─' * 105}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total: {Fore.YELLOW}{humanize.naturalsize(total_size)}{Fore.CYAN} │ "
          f"Items: {Fore.WHITE}{total_items}{Fore.CYAN} │ "
          f"Page: {Fore.WHITE}{page + 1}/{total_pages or 1}{Style.RESET_ALL}")


def show_navigation_options(current_page, total_pages, show_hidden=True, sort_mode='size'):
    """Display compact V2 navigation options."""
    h = "👁" if show_hidden else "◌"
    s = sort_mode[0].upper()
    
    # Line 1: Navigation & View
    print(f"\n{Fore.BLUE}─{Style.RESET_ALL} {Fore.YELLOW}#{Style.RESET_ALL}=enter {Fore.YELLOW}.{Style.RESET_ALL}=root {Fore.YELLOW}..{Style.RESET_ALL}=up {Fore.YELLOW}~{Style.RESET_ALL}=home {Fore.YELLOW}g{Style.RESET_ALL}=goto │ {Fore.YELLOW}f{Style.RESET_ALL}=filter {Fore.YELLOW}F{Style.RESET_ALL}=search {Fore.YELLOW}h{Style.RESET_ALL}={h} {Fore.YELLOW}s{Style.RESET_ALL}=[{s}] {Fore.YELLOW}l{Style.RESET_ALL}=limit", end="")
    
    # Pagination inline
    if total_pages > 1:
        if current_page > 0:
            print(f" {Fore.YELLOW}p{Style.RESET_ALL}=prev", end="")
        if current_page < total_pages - 1:
            print(f" {Fore.YELLOW}n{Style.RESET_ALL}=next", end="")
    print()
    
    # Line 2: Actions
    print(f"{Fore.BLUE}─{Style.RESET_ALL} {Fore.YELLOW}o{Style.RESET_ALL}=open {Fore.YELLOW}d{Style.RESET_ALL}=del {Fore.YELLOW}D{Style.RESET_ALL}=perm {Fore.YELLOW}m{Style.RESET_ALL}=move {Fore.YELLOW}c{Style.RESET_ALL}=copy │ {Fore.YELLOW}b{Style.RESET_ALL}=bookmarks {Fore.YELLOW}e{Style.RESET_ALL}=stats {Fore.YELLOW}x{Style.RESET_ALL}=export")
    
    # Line 3: Tools & System
    print(f"{Fore.BLUE}─{Style.RESET_ALL} {Fore.YELLOW}top{Style.RESET_ALL} {Fore.YELLOW}dup{Style.RESET_ALL} {Fore.YELLOW}clean{Style.RESET_ALL} {Fore.YELLOW}r{Style.RESET_ALL}=rescan {Fore.CYAN}?{Style.RESET_ALL}=help {Fore.RED}q{Style.RESET_ALL}=quit")


def show_help():
    """Display full help/tutorial page."""
    clear_screen()
    
    print(f"""
{Fore.CYAN}{Style.BRIGHT}╔══════════════════════════════════════════════════════════════════════════════╗
║                         DISKMAN V2 - FULL HELP                               ║
╚══════════════════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}

{Fore.GREEN}{Style.BRIGHT}NAVIGATION{Style.RESET_ALL}
{Fore.YELLOW}  #         {Style.RESET_ALL}Enter a folder by its number (e.g., '3' to enter item 3)
{Fore.YELLOW}  .         {Style.RESET_ALL}Jump to scan root (top folder of cached tree)
{Fore.YELLOW}  ..        {Style.RESET_ALL}Go up one directory level
{Fore.YELLOW}  ..3       {Style.RESET_ALL}Go up 3 levels (works with any number)
{Fore.YELLOW}  ~         {Style.RESET_ALL}Jump to home directory
{Fore.YELLOW}  g <path>  {Style.RESET_ALL}Go to a specific path (e.g., 'g /Users/Downloads')
{Fore.YELLOW}  p / n     {Style.RESET_ALL}Previous / Next page (when paginated)

{Fore.GREEN}{Style.BRIGHT}FILE ACTIONS{Style.RESET_ALL}
{Fore.YELLOW}  o #       {Style.RESET_ALL}Open item in Finder (e.g., 'o 1')
{Fore.YELLOW}  d #       {Style.RESET_ALL}Delete to Trash (e.g., 'd 3' or 'd 1,3,5' or 'd 1-5')
{Fore.YELLOW}  D #       {Style.RESET_ALL}Permanently delete (DANGEROUS - no undo!)
{Fore.YELLOW}  m # path  {Style.RESET_ALL}Move item(s) to path (e.g., 'm 1,2 /tmp')
{Fore.YELLOW}  c # path  {Style.RESET_ALL}Copy item(s) to path (e.g., 'c 3 ~/Desktop')

{Fore.GREEN}{Style.BRIGHT}VIEW OPTIONS{Style.RESET_ALL}
{Fore.YELLOW}  f <text>  {Style.RESET_ALL}Filter current folder by name (e.g., 'f .mp4'). Just 'f' to clear.
{Fore.YELLOW}  F <text>  {Style.RESET_ALL}Deep search ALL subfolders (e.g., 'F video' or '/ video')
{Fore.YELLOW}  h         {Style.RESET_ALL}Toggle hidden files (show/hide dotfiles)
{Fore.YELLOW}  s         {Style.RESET_ALL}Cycle sort mode: Size → Name → Date
{Fore.YELLOW}  l <num>   {Style.RESET_ALL}Set items per page (e.g., 'l 25'). Range: 5-50
{Fore.YELLOW}  r         {Style.RESET_ALL}Rescan current directory (refresh data)

{Fore.GREEN}{Style.BRIGHT}TOOLS{Style.RESET_ALL}
{Fore.YELLOW}  b         {Style.RESET_ALL}Manage bookmarks (save favorite folders)
{Fore.YELLOW}  b+        {Style.RESET_ALL}Add current folder to bookmarks
{Fore.YELLOW}  b1, b2... {Style.RESET_ALL}Jump to bookmark #1, #2, etc.
{Fore.YELLOW}  e         {Style.RESET_ALL}Show extension statistics (size by file type)
{Fore.YELLOW}  top       {Style.RESET_ALL}Show top 20 LARGEST FILES in entire cache
{Fore.YELLOW}  top 100   {Style.RESET_ALL}Show top 100 largest files
{Fore.YELLOW}  dup       {Style.RESET_ALL}Find duplicate files (by size + hash)
{Fore.YELLOW}  clean     {Style.RESET_ALL}Show system cache/temp folders to free space
{Fore.YELLOW}  x         {Style.RESET_ALL}Export current directory to CSV report

{Fore.GREEN}{Style.BRIGHT}DISPLAY ICONS{Style.RESET_ALL}
{Fore.GREEN}  ●{Style.RESET_ALL} = Cached (fast)    {Fore.YELLOW}●{Style.RESET_ALL} = Fresh scan
  👁 = Hidden files ON   ◌ = Hidden files OFF
  [S] = Sort by Size   [N] = Name   [D] = Date
  {Fore.GREEN}◉ new{Style.RESET_ALL} = <3 months   {Fore.YELLOW}◉ mid{Style.RESET_ALL} = 3-12 months   {Fore.RED}◉ old{Style.RESET_ALL} = >1 year

{Fore.GREEN}{Style.BRIGHT}MULTI-SELECT{Style.RESET_ALL}
  Use commas or ranges for multiple items:
  {Fore.WHITE}d 1,3,5     {Style.RESET_ALL}Delete items 1, 3, and 5
  {Fore.WHITE}d 1-5       {Style.RESET_ALL}Delete items 1 through 5
  {Fore.WHITE}m 1-3,7 /tmp{Style.RESET_ALL}Move items 1, 2, 3, and 7 to /tmp

{Fore.CYAN}{'─' * 78}{Style.RESET_ALL}
{Fore.RED}  q         {Style.RESET_ALL}Quit DiskMan

{Fore.BLUE}{'─' * 78}{Style.RESET_ALL}
{Fore.WHITE}Made with ❤️  by SamSeen{Style.RESET_ALL}
{Fore.YELLOW}☕ Support: {Fore.WHITE}https://buymeacoffee.com/samseen{Style.RESET_ALL}
""")
    
    input(f"{Fore.CYAN}Press Enter to return...{Style.RESET_ALL}")


def show_welcome_message():
    """Display V2 welcome message."""
    clear_screen()
    
    logo = f"""
{Fore.CYAN}{Style.BRIGHT}
    ____  _      __   __  ___            
   / __ \\(_)____/ /__/  |/  /___ _____   
  / / / / / ___/ //_/ /|_/ / __ `/ __ \\  
 / /_/ / (__  ) ,< / /  / / /_/ / / / /  
/_____/_/____/_/|_/_/  /_/\\__,_/_/ /_/   
                                    V2
{Style.RESET_ALL}"""
    
    print(logo)
    print(f"{Fore.GREEN}{Style.BRIGHT}{'═' * 60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}{'DiskMan V2 - Enhanced Disk Space Analyzer':^60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{Style.BRIGHT}{'═' * 60}{Style.RESET_ALL}")
    
    features = [
        "✨ Smart caching for instant navigation",
        "🔍 Filter and search files",
        "📊 Extension statistics",
        "🔖 Directory bookmarks",
        "🗑️ Safe trash deletion",
        "📋 Export reports to CSV"
    ]
    
    print(f"\n{Fore.WHITE}New in V2:{Style.RESET_ALL}")
    for feature in features:
        print(f"  {Fore.GREEN}{feature}{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}{'─' * 60}{Style.RESET_ALL}")
    
    current_dir = os.getcwd()
    print(f"\n{Fore.CYAN}Enter directory path (or press Enter for current):{Style.RESET_ALL}")
    print(f"{Fore.WHITE}{current_dir}{Style.RESET_ALL}")
    user_dir = input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()
    
    if user_dir:
        if os.path.isdir(user_dir):
            return os.path.abspath(user_dir)
        else:
            print(f"\n{Fore.RED}Not found: {user_dir}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}Using current directory.{Style.RESET_ALL}")
            time.sleep(1)
            return current_dir
    return current_dir


def show_extension_stats(stats, total_size):
    """Display extension breakdown."""
    clear_screen()
    print(f"\n{Fore.CYAN}{Style.BRIGHT}📊 Extension Statistics{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{Style.BRIGHT}{'Extension':<20} {'Size':<15} {'%':>8}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")
    
    for ext, size in stats.items():
        pct = (size / total_size * 100) if total_size > 0 else 0
        
        if pct > 20:
            color = Fore.RED
        elif pct > 10:
            color = Fore.YELLOW
        else:
            color = Fore.GREEN
        
        bar_len = int(pct / 2)
        bar = "█" * bar_len
        
        print(f"{Fore.WHITE}{ext:<20} {color}{humanize.naturalsize(size):<15} "
              f"{pct:>6.1f}% {bar}{Style.RESET_ALL}")
    
    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total: {Fore.YELLOW}{humanize.naturalsize(total_size)}{Style.RESET_ALL}")
    input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")


def show_bookmarks(bookmarks):
    """Display bookmarks list."""
    clear_screen()
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🔖 Bookmarks{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")
    
    if not bookmarks:
        print(f"{Fore.YELLOW}No bookmarks yet. Use 'b+' to add current directory.{Style.RESET_ALL}")
    else:
        for idx, path in bookmarks:
            name = os.path.basename(path) or path
            print(f"  {Fore.YELLOW}{idx}{Fore.CYAN}: {Fore.WHITE}{name}{Style.RESET_ALL}")
            print(f"      {Fore.WHITE}{Style.DIM}{path}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}Commands: {Fore.YELLOW}b#=jump  b+=add  b- #=remove{Style.RESET_ALL}")
    return input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()


def show_duplicates(duplicates):
    """Display duplicate files found with actions.
    
    Returns: action tuple or None
    """
    clear_screen()
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 DUPLICATE FILES{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    if not duplicates:
        print(f"\n{Fore.GREEN}✓ No duplicates found! Your files are unique.{Style.RESET_ALL}")
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        return None
    
    # Calculate totals
    total_wasted = sum(d.get('wasted', d['size'] * (len(d['files']) - 1)) for d in duplicates)
    total_groups = len(duplicates)
    
    print(f"{Fore.RED}{Style.BRIGHT}Found {total_groups} duplicate groups  •  Potential savings: {humanize.naturalsize(total_wasted)}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    # Show header
    print(f"{Fore.GREEN}{Style.BRIGHT}{'#':<4} {'Wasted':<12} {'Each':<12} {'Copies':<8} {'Filename'}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    # Show top duplicates (limit to 15)
    display_dups = duplicates[:15]
    for i, dup in enumerate(display_dups, 1):
        size = dup['size']
        files = dup['files']
        count = dup.get('count', len(files))
        wasted = dup.get('wasted', size * (count - 1))
        
        # Get filename (they're all the same name for true duplicates)
        filename = os.path.basename(files[0])
        if len(filename) > 40:
            filename = filename[:37] + "..."
        
        # Color based on wasted space
        if wasted > 100 * 1024 * 1024:  # > 100MB
            waste_color = Fore.RED + Style.BRIGHT
        elif wasted > 10 * 1024 * 1024:  # > 10MB
            waste_color = Fore.YELLOW
        else:
            waste_color = Fore.WHITE
        
        print(f"{Fore.YELLOW}{i:<4}{Style.RESET_ALL} "
              f"{waste_color}{humanize.naturalsize(wasted):<12}{Style.RESET_ALL} "
              f"{Fore.WHITE}{humanize.naturalsize(size):<12}{Style.RESET_ALL} "
              f"{Fore.CYAN}{count:<8}{Style.RESET_ALL} "
              f"{Fore.WHITE}{filename}{Style.RESET_ALL}")
    
    if len(duplicates) > 15:
        print(f"\n{Fore.WHITE}{Style.DIM}... and {len(duplicates) - 15} more groups{Style.RESET_ALL}")
    
    print(f"\n{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Commands:{Style.RESET_ALL} {Fore.YELLOW}#{Style.RESET_ALL}=view details  {Fore.WHITE}Enter{Style.RESET_ALL}=back")
    
    choice = input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()
    
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(display_dups):
            return show_duplicate_detail(display_dups[idx])
    
    return None


def show_duplicate_detail(dup):
    """Show detailed view of a duplicate group with actions."""
    clear_screen()
    size = dup['size']
    files = dup['files']
    wasted = dup.get('wasted', size * (len(files) - 1))
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}📋 DUPLICATE GROUP DETAILS{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    print(f"{Fore.WHITE}File size: {Fore.YELLOW}{humanize.naturalsize(size)}{Style.RESET_ALL}  •  "
          f"{Fore.WHITE}Copies: {Fore.CYAN}{len(files)}{Style.RESET_ALL}  •  "
          f"{Fore.WHITE}Wasted: {Fore.RED}{humanize.naturalsize(wasted)}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}{'#':<4} {'Location'}{Style.RESET_ALL}")
    
    for i, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        dirname = os.path.dirname(filepath)
        if len(dirname) > 80:
            dirname = "..." + dirname[-77:]
        print(f"{Fore.YELLOW}{i:<4}{Style.RESET_ALL} {Fore.WHITE}{filename}{Style.RESET_ALL}")
        print(f"     {Fore.WHITE}{Style.DIM}{dirname}{Style.RESET_ALL}")
    
    print(f"\n{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Commands:{Style.RESET_ALL} {Fore.YELLOW}#{Style.RESET_ALL}=go to folder  {Fore.YELLOW}o #{Style.RESET_ALL}=open in Finder  {Fore.WHITE}Enter{Style.RESET_ALL}=back")
    
    choice = input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()
    
    if choice.startswith('o ') and choice[2:].isdigit():
        idx = int(choice[2:]) - 1
        if 0 <= idx < len(files):
            return ('open', files[idx])
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            return ('goto', os.path.dirname(files[idx]))
    
    return None


def show_cache_cleaner(cache_folders):
    """Display system cache folders with sizes.
    
    Returns: action tuple or None
    """
    clear_screen()
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🧹 SYSTEM CACHE CLEANER{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Common cache/temp folders on your system:{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    if not cache_folders:
        print(f"\n{Fore.YELLOW}No cache folders found.{Style.RESET_ALL}")
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        return None
    
    total_size = sum(f[3] for f in cache_folders)
    
    print(f"{Fore.GREEN}{Style.BRIGHT}{'#':<3} {'Size':<12} {'Folder':<30} {'Description'}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    for i, (path, name, description, size, exists) in enumerate(cache_folders, 1):
        size_str = humanize.naturalsize(size)
        
        # Size color
        if size > 1024 * 1024 * 1024:  # > 1GB
            size_color = Fore.RED + Style.BRIGHT
        elif size > 100 * 1024 * 1024:  # > 100MB
            size_color = Fore.YELLOW
        elif size > 10 * 1024 * 1024:  # > 10MB
            size_color = Fore.GREEN
        else:
            size_color = Fore.WHITE
        
        # Truncate description
        if len(description) > 35:
            desc_display = description[:32] + "..."
        else:
            desc_display = description
        
        # Truncate name
        if len(name) > 28:
            name_display = name[:25] + "..."
        else:
            name_display = name
        
        print(f"{Fore.YELLOW}{i:<3} {size_color}{size_str:<12}{Style.RESET_ALL} "
              f"{Fore.CYAN}{name_display:<30}{Style.RESET_ALL} {Fore.WHITE}{desc_display}{Style.RESET_ALL}")
    
    print(f"\n{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total cache: {Fore.YELLOW}{Style.BRIGHT}{humanize.naturalsize(total_size)}{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}Commands:{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}#{Style.RESET_ALL}=navigate  {Fore.YELLOW}o #{Style.RESET_ALL}=open in Finder  {Fore.RED}c #{Style.RESET_ALL}=CLEAR folder  {Fore.WHITE}Enter{Style.RESET_ALL}=back")
    
    choice = input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()
    
    if choice.startswith('o ') and choice[2:].isdigit():
        idx = int(choice[2:]) - 1
        if 0 <= idx < len(cache_folders):
            return ('open', cache_folders[idx][0])
    elif choice.startswith('c ') and choice[2:].isdigit():
        idx = int(choice[2:]) - 1
        if 0 <= idx < len(cache_folders):
            return ('clear', cache_folders[idx])
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(cache_folders):
            return ('goto', cache_folders[idx][0])
    
    return None


def show_largest_files(files, scan_root):
    """Display largest files across all cached subfolders.
    
    Returns: action tuple or None
    """
    clear_screen()
    print(f"\n{Fore.CYAN}{Style.BRIGHT}📊 LARGEST FILES{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Scanning: {scan_root}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    if not files:
        print(f"\n{Fore.YELLOW}No files found in cache.{Style.RESET_ALL}")
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        return None
    
    total_size = sum(f[2] for f in files)
    
    print(f"{Fore.GREEN}{Style.BRIGHT}{'#':<4} {'Name':<35} {'Size':<12} {'%':<6} {'Location'}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    for i, (full_path, name, size, is_hid, mtime, rel_path) in enumerate(files, 1):
        # Truncate name
        if len(name) > 32:
            display_name = name[:29] + "..."
        else:
            display_name = name
        
        size_str = humanize.naturalsize(size)
        pct = (size / total_size * 100) if total_size > 0 else 0
        
        # Size color
        if pct > 10:
            size_color = Fore.RED
        elif pct > 5:
            size_color = Fore.YELLOW
        else:
            size_color = Fore.GREEN
        
        # Truncate path
        if len(rel_path) > 35:
            rel_path = "..." + rel_path[-32:]
        
        print(f"{Fore.YELLOW}{i:<4} {Fore.WHITE}{display_name:<35}{Style.RESET_ALL} "
              f"{size_color}{size_str:<12}{Style.RESET_ALL} {size_color}{pct:>5.1f}%{Style.RESET_ALL} "
              f"{Fore.WHITE}{rel_path}{Style.RESET_ALL}")
    
    print(f"\n{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Top {len(files)} files: {Fore.YELLOW}{humanize.naturalsize(total_size)}{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}Commands: {Fore.YELLOW}#{Style.RESET_ALL}=go to folder  {Fore.YELLOW}o #{Style.RESET_ALL}=open  {Fore.YELLOW}d #{Style.RESET_ALL}=delete  {Fore.WHITE}Enter{Style.RESET_ALL}=back")
    
    choice = input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()
    
    if choice.startswith('o ') and choice[2:].isdigit():
        idx = int(choice[2:]) - 1
        if 0 <= idx < len(files):
            return ('open', files[idx][0])
    elif choice.startswith('d ') and choice[2:].isdigit():
        idx = int(choice[2:]) - 1
        if 0 <= idx < len(files):
            return ('delete', files[idx][0])
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(files):
            return ('goto', os.path.dirname(files[idx][0]))
    
    return None


def show_search_results(results, search_text, scan_root):
    """Display deep search results.
    
    Returns: selected path to navigate to, or None
    """
    clear_screen()
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🔍 Search Results for '{search_text}'{Style.RESET_ALL}")
    print(f"{Fore.WHITE}Searching in: {scan_root}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    if not results:
        print(f"\n{Fore.YELLOW}No files found matching '{search_text}'{Style.RESET_ALL}")
        input(f"\n{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
        return None
    
    print(f"{Fore.GREEN}{Style.BRIGHT}{'#':<4} {'Name':<35} {'Size':<12} {'Location'}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    
    # Show up to 20 results
    display_results = results[:20]
    
    for i, (full_path, name, size, is_dir, is_hid, mtime, rel_path) in enumerate(display_results, 1):
        # Truncate name
        if len(name) > 32:
            display_name = name[:29] + "..."
        else:
            display_name = name
        
        size_str = humanize.naturalsize(size)
        
        # Color based on type
        if is_dir:
            name_color = Fore.CYAN + Style.BRIGHT
            type_icon = "📁"
        else:
            name_color = Fore.WHITE + Style.BRIGHT
            type_icon = "📄"
        
        # Truncate path
        if len(rel_path) > 40:
            rel_path = "..." + rel_path[-37:]
        
        print(f"{Fore.YELLOW}{i:<4} {type_icon} {name_color}{display_name:<32}{Style.RESET_ALL} "
              f"{Fore.GREEN}{size_str:<12}{Style.RESET_ALL} {Fore.WHITE}{rel_path}{Style.RESET_ALL}")
    
    if len(results) > 20:
        print(f"\n{Fore.YELLOW}... and {len(results) - 20} more results{Style.RESET_ALL}")
    
    print(f"\n{Fore.BLUE}{'─' * 100}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}Total: {Fore.WHITE}{len(results)} matches{Style.RESET_ALL}")
    print(f"\n{Fore.CYAN}Enter # to go to folder, 'o #' to open in Finder, or press Enter to cancel:{Style.RESET_ALL}")
    
    choice = input(f"{Fore.YELLOW}> {Style.RESET_ALL}").strip()
    
    if choice.startswith('o ') and choice[2:].isdigit():
        idx = int(choice[2:]) - 1
        if 0 <= idx < len(display_results):
            return ('open', display_results[idx][0])
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(display_results):
            # Return parent directory of the selected item
            return ('goto', os.path.dirname(display_results[idx][0]))
    
    return None


def show_delete_confirmation(item_details, use_trash=True):
    """Show deletion confirmation for single or multiple items."""
    clear_screen()
    
    items = item_details if isinstance(item_details, list) else [item_details]
    
    action = "Move to Trash" if use_trash else "PERMANENTLY DELETE"
    color = Fore.YELLOW if use_trash else Fore.RED
    
    print(f"\n{color}{Style.BRIGHT}{'!' * 60}{Style.RESET_ALL}")
    print(f"{color}{Style.BRIGHT}{action:^60}{Style.RESET_ALL}")
    print(f"{color}{Style.BRIGHT}{'!' * 60}{Style.RESET_ALL}")
    
    total_size = 0
    for item in items:
        name = item['name']
        size = item['size']
        total_size += size
        is_dir = item['is_dir']
        
        icon = "📁" if is_dir else "📄"
        print(f"\n  {icon} {Fore.YELLOW}{Style.BRIGHT}{name}{Style.RESET_ALL}")
        print(f"     {Fore.WHITE}Size: {humanize.naturalsize(size)}{Style.RESET_ALL}")
    
    print(f"\n{Fore.CYAN}Total: {Fore.YELLOW}{humanize.naturalsize(total_size)}{Style.RESET_ALL}")
    
    if not use_trash:
        print(f"\n{Fore.RED}{Style.BRIGHT}⚠️  This action CANNOT be undone!{Style.RESET_ALL}")
    
    confirm = input(f"\n{color}Type 'yes' to confirm: {Style.RESET_ALL}").strip().lower()
    return confirm == 'yes'


def show_file_preview(preview_data, file_path):
    """Display file preview."""
    clear_screen()
    name = os.path.basename(file_path)
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}📄 {name}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")
    
    ptype = preview_data.get('type', 'unknown')
    
    if ptype == 'text':
        lines = preview_data.get('content', [])
        for line in lines:
            print(f"{Fore.WHITE}{line}{Style.RESET_ALL}")
    elif ptype == 'image':
        print(f"{Fore.GREEN}Image: {preview_data.get('format', 'Unknown')}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}Size: {humanize.naturalsize(preview_data.get('size', 0))}{Style.RESET_ALL}")
    elif ptype == 'video':
        print(f"{Fore.GREEN}Video: {preview_data.get('format', 'Unknown')}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}Size: {humanize.naturalsize(preview_data.get('size', 0))}{Style.RESET_ALL}")
    elif ptype == 'audio':
        print(f"{Fore.GREEN}Audio: {preview_data.get('format', 'Unknown')}{Style.RESET_ALL}")
        print(f"{Fore.WHITE}Size: {humanize.naturalsize(preview_data.get('size', 0))}{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}Binary file: {humanize.naturalsize(preview_data.get('size', 0))}{Style.RESET_ALL}")
    
    print(f"{Fore.BLUE}{'─' * 60}{Style.RESET_ALL}")
    input(f"{Fore.CYAN}Press Enter to continue...{Style.RESET_ALL}")
