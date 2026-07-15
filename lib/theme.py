import os
import curses

# Visual Theme Definitions
THEMES = [
    ("Neon Cyan", curses.COLOR_CYAN, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_CYAN),
    ("Classic Amber", curses.COLOR_YELLOW, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_YELLOW),
    ("Hacker Green", curses.COLOR_GREEN, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_GREEN),
    ("Royal Purple", curses.COLOR_MAGENTA, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_MAGENTA),
    ("Sweet Pink", curses.COLOR_MAGENTA, curses.COLOR_WHITE, curses.COLOR_MAGENTA, curses.COLOR_CYAN, curses.COLOR_RED, curses.COLOR_MAGENTA),
    ("Sunset Orange", curses.COLOR_YELLOW, curses.COLOR_WHITE, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_RED, curses.COLOR_YELLOW),
    ("Sleek Gray", curses.COLOR_WHITE, curses.COLOR_WHITE, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_WHITE)
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


def apply_theme(theme_idx):
    """Dynamically updates the color pairs in memory to switch visual themes on the fly."""
    theme = THEMES[theme_idx]
    _, dir_col, file_col, low_col, med_col, high_col, border_col = theme
    curses.init_pair(1, dir_col, -1)   # Folders / Cyan titles
    curses.init_pair(2, file_col, -1)  # Standard files / text
    curses.init_pair(3, low_col, -1)   # Green / low ratio space
    curses.init_pair(4, med_col, -1)   # Yellow highlights / medium ratio
    curses.init_pair(5, high_col, -1)  # Red warning / high ratio space
    curses.init_pair(6, border_col, -1) # Panel border colors
