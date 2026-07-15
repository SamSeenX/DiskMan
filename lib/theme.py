import os
import curses

# Pastel Color Definitions (Used when terminal supports changing color settings)
# Scale in curses is 0 to 1000.
PASTEL_RED = 10
PASTEL_GREEN = 11
PASTEL_YELLOW = 12
PASTEL_BLUE = 13
PASTEL_MAGENTA = 14
PASTEL_CYAN = 15
PASTEL_BG_DARK = 16
PASTEL_BG_LIGHT = 17
PASTEL_TEXT = 18

def init_pastel_colors():
    """Initializes soft, low-luminosity pastel colors in terminals that support it."""
    if not curses.has_colors():
        return
    if hasattr(curses, 'can_change_color') and curses.can_change_color():
        try:
            curses.init_color(PASTEL_RED, 500, 300, 300)      # Faded Brick Red
            curses.init_color(PASTEL_GREEN, 300, 500, 380)    # Faded Sage Green
            curses.init_color(PASTEL_YELLOW, 550, 480, 320)   # Faded Dusty Amber
            curses.init_color(PASTEL_BLUE, 300, 400, 550)     # Faded Slate Blue
            curses.init_color(PASTEL_MAGENTA, 550, 350, 480)  # Faded Dusty Lavender
            curses.init_color(PASTEL_CYAN, 350, 500, 500)     # Faded Dusty Teal
            curses.init_color(PASTEL_BG_DARK, 90, 100, 110)   # Faded Deep Slate Background
            curses.init_color(PASTEL_BG_LIGHT, 720, 700, 650) # Muted Warm Sand Background (Faded/Muted)
            curses.init_color(PASTEL_TEXT, 700, 700, 720)     # Faded Soft Gray Text (Not blinding white)
        except Exception:
            pass

# Visual Theme Definitions
# Format: Name, dir_col, file_col, low_col, med_col, high_col, border_col, [bg_col]
# Colors can be tuples: (custom_pastel_color, fallback_standard_color)
THEMES = [
    # Classic standard themes
    ("Neon Cyan", curses.COLOR_CYAN, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_CYAN),
    ("Classic Amber", curses.COLOR_YELLOW, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_YELLOW),
    ("Hacker Green", curses.COLOR_GREEN, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_GREEN),
    ("Royal Purple", curses.COLOR_MAGENTA, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_MAGENTA),
    ("Sweet Pink", curses.COLOR_MAGENTA, curses.COLOR_WHITE, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA),
    ("Sunset Orange", curses.COLOR_YELLOW, curses.COLOR_WHITE, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_RED, curses.COLOR_YELLOW),
    ("Sleek Gray", curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_WHITE),
    
    # Muted / Medium brightness themes
    ("Nordic Teal", curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_CYAN, curses.COLOR_BLUE, curses.COLOR_RED, curses.COLOR_CYAN),
    ("Sage Green", curses.COLOR_GREEN, curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_GREEN),
    ("Soft Amber", curses.COLOR_YELLOW, curses.COLOR_BLUE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_YELLOW),
    
    # Soft Pastel Themes (Optimized for eyes with custom colors where supported)
    ("Pastel Teal", (PASTEL_CYAN, curses.COLOR_CYAN), (PASTEL_TEXT, curses.COLOR_WHITE), (PASTEL_GREEN, curses.COLOR_GREEN), (PASTEL_YELLOW, curses.COLOR_YELLOW), (PASTEL_RED, curses.COLOR_RED), (PASTEL_CYAN, curses.COLOR_CYAN), (PASTEL_BG_DARK, -1)),
    ("Soft Lavender", (PASTEL_MAGENTA, curses.COLOR_MAGENTA), (PASTEL_BLUE, curses.COLOR_CYAN), (PASTEL_GREEN, curses.COLOR_GREEN), (PASTEL_YELLOW, curses.COLOR_YELLOW), (PASTEL_RED, curses.COLOR_RED), (PASTEL_MAGENTA, curses.COLOR_MAGENTA), (PASTEL_BG_DARK, -1)),
    ("Warm Sandstone", (PASTEL_BLUE, curses.COLOR_BLUE), (curses.COLOR_BLACK, curses.COLOR_BLACK), (PASTEL_GREEN, curses.COLOR_GREEN), (PASTEL_MAGENTA, curses.COLOR_MAGENTA), (PASTEL_RED, curses.COLOR_RED), (PASTEL_BLUE, curses.COLOR_BLUE), (PASTEL_BG_LIGHT, curses.COLOR_WHITE)),
    
    # Light theme variants
    ("Light Terminal", curses.COLOR_BLUE, curses.COLOR_BLACK, curses.COLOR_GREEN, curses.COLOR_MAGENTA, curses.COLOR_RED, curses.COLOR_BLACK),
    # Medium background themes (Retro DOS / Blue style)
    ("Classic Blue", curses.COLOR_WHITE, curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_WHITE, curses.COLOR_BLUE),
    ("Ocean Depth", curses.COLOR_CYAN, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_CYAN, curses.COLOR_BLUE)
]

THEME_CACHE_DIR = os.path.expanduser("~/.diskman")
THEME_CACHE_FILE = os.path.join(THEME_CACHE_DIR, "theme")


def save_theme_cache(theme_idx):
    """Save the selected theme index to a persistent hidden ~/.diskman directory file."""
    try:
        os.makedirs(THEME_CACHE_DIR, exist_ok=True)
        with open(THEME_CACHE_FILE, "w") as f:
            f.write(str(theme_idx))
    except Exception:
        pass


def load_theme_cache():
    """Load the saved theme index from persistent hidden ~/.diskman directory file."""
    try:
        if os.path.exists(THEME_CACHE_FILE):
            with open(THEME_CACHE_FILE, "r") as f:
                idx = int(f.read().strip())
                if 0 <= idx < len(THEMES):
                    return idx
    except Exception:
        pass
    return 0


def apply_theme(theme_idx, stdscr=None):
    """Dynamically updates the color pairs in memory to switch visual themes on the fly."""
    init_pastel_colors()
    theme = THEMES[theme_idx]
    
    # Resolve colors based on terminal capability
    resolved = []
    for item in theme[1:]:
        if isinstance(item, tuple):
            val, fallback = item
            if hasattr(curses, 'can_change_color') and curses.can_change_color():
                resolved.append(val)
            else:
                resolved.append(fallback)
        else:
            resolved.append(item)
            
    if len(resolved) == 7:
        dir_col, file_col, low_col, med_col, high_col, border_col, bg_col = resolved
    else:
        dir_col, file_col, low_col, med_col, high_col, border_col = resolved
        bg_col = -1
        
    curses.init_pair(1, dir_col, bg_col)   # Folders / Cyan titles
    curses.init_pair(2, file_col, bg_col)  # Standard files / text
    curses.init_pair(3, low_col, bg_col)   # Green / low ratio space
    curses.init_pair(4, med_col, bg_col)   # Yellow highlights / medium ratio
    curses.init_pair(5, high_col, bg_col)  # Red warning / high ratio space
    curses.init_pair(6, border_col, bg_col) # Panel border colors

    if stdscr is not None:
        try:
            # Dynamically refresh the window background to use the theme's background color
            stdscr.bkgd(' ', curses.color_pair(2))
        except Exception:
            pass
