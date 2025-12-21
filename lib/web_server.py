#!/usr/bin/env python3
"""
Web Dashboard Server for DiskMan.
Provides a full-featured web interface for disk analysis.
"""
import os
import json
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import humanize

# Reference to the cache will be set when server starts
_cache = None
_current_dir = None

# Color palette for pie chart slices
CHART_COLORS = [
    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
    '#FF9F40', '#FF6384', '#C9CBCF', '#7BC225', '#E7E9ED',
    '#F7464A', '#46BFBD', '#FDB45C', '#949FB1', '#4D5360',
    '#AC64AD', '#63FF7B', '#FF6347', '#40E0D0', '#EE82EE'
]


def get_folder_data(path, auto_rescan=True):
    """Get folder contents formatted for the dashboard.
    
    Args:
        path: Directory path to get data for
        auto_rescan: If True, rescan when navigating outside cached area
    """
    global _cache
    
    if not _cache or not path:
        return None
    
    path = os.path.abspath(path)
    
    if not os.path.isdir(path):
        return None
    
    scan_root = _cache.get_scan_root()
    
    # Check if path is outside the current scan root
    is_outside_cache = False
    if scan_root:
        # Path is outside if it doesn't start with scan_root
        # or if it's a parent of scan_root
        is_outside_cache = not path.startswith(scan_root) or len(path) < len(scan_root)
    
    # If outside cache and auto_rescan is enabled, rescan from the new path
    if is_outside_cache and auto_rescan:
        _cache.scan_directory_tree(path)
        scan_root = path
    
    # Get items from cache
    items = _cache.get_directory(path)
    
    if items is None:
        # Not in cache - try scanning this specific path
        if auto_rescan:
            _cache.scan_directory_tree(path)
            items = _cache.get_directory(path)
            scan_root = path
        if items is None:
            return None
    
    # Calculate totals
    total_size = sum(item[1] for item in items)
    file_count = sum(1 for item in items if not item[2])
    folder_count = sum(1 for item in items if item[2])
    
    # Build breadcrumbs - show full path from filesystem root
    breadcrumbs = []
    current = path
    while current:
        name = os.path.basename(current)
        if not name:  # Root directory
            name = current
        breadcrumbs.insert(0, {
            'name': name,
            'path': current,
            'in_cache': scan_root and current.startswith(scan_root)
        })
        parent = os.path.dirname(current)
        if parent == current:  # Reached filesystem root
            break
        current = parent
    
    # Format children
    children = []
    for i, (name, size, is_dir, is_hidden, mtime) in enumerate(items):
        if is_hidden and not _cache.show_hidden:
            continue
        
        item_path = os.path.join(path, name)
        percentage = (size / total_size * 100) if total_size > 0 else 0
        
        children.append({
            'name': name,
            'path': item_path,
            'size': size,
            'size_human': humanize.naturalsize(size),
            'percentage': round(percentage, 1),
            'is_dir': is_dir,
            'is_hidden': is_hidden,
            'mtime': mtime,
            'color': CHART_COLORS[i % len(CHART_COLORS)]
        })
    
    # Always allow navigating to parent (filesystem allows it)
    parent_path = os.path.dirname(path)
    has_parent = parent_path != path  # Not at filesystem root
    
    return {
        'path': path,
        'name': os.path.basename(path) or path,
        'total_size': total_size,
        'total_size_human': humanize.naturalsize(total_size),
        'parent': parent_path if has_parent else None,
        'scan_root': scan_root,
        'breadcrumbs': breadcrumbs,
        'children': children,
        'file_count': file_count,
        'folder_count': folder_count
    }


def get_stats():
    """Get overall scan statistics."""
    global _cache
    
    if not _cache:
        return None
    
    scan_root = _cache.get_scan_root()
    if not scan_root:
        return None
    
    # Count all files and folders
    total_files = 0
    total_folders = 0
    total_size = 0
    
    for dir_path, items in _cache.cache.items():
        for name, size, is_dir, is_hidden, mtime in items:
            if is_dir:
                total_folders += 1
            else:
                total_files += 1
            total_size += size
    
    return {
        'scan_root': scan_root,
        'scan_root_name': os.path.basename(scan_root) or scan_root,
        'total_size': total_size,
        'total_size_human': humanize.naturalsize(total_size),
        'file_count': total_files,
        'folder_count': total_folders
    }


def get_extensions(folder_path=None):
    """Get file extension breakdown for a specific folder."""
    global _cache
    
    if not _cache:
        return []
    
    target_path = folder_path or _cache.get_scan_root()
    if not target_path:
        return []
    
    stats = _cache.get_extension_stats(target_path)
    total = sum(stats.values())
    
    result = []
    for ext, size in sorted(stats.items(), key=lambda x: x[1], reverse=True)[:15]:
        percentage = (size / total * 100) if total > 0 else 0
        result.append({
            'extension': ext or '(no ext)',
            'size': size,
            'size_human': humanize.naturalsize(size),
            'percentage': round(percentage, 1)
        })
    
    return result


def get_largest_files(folder_path=None, limit=20):
    """Get the largest files in a specific folder."""
    global _cache
    
    if not _cache:
        return []
    
    files = _cache.get_largest_files(dir_path=folder_path, limit=limit, show_progress=False)
    
    result = []
    for full_path, name, size, is_hidden, mtime, rel_path in files:
        result.append({
            'path': full_path,
            'name': name,
            'size': size,
            'size_human': humanize.naturalsize(size),
            'relative_path': rel_path,
            'mtime': mtime
        })
    
    return result


def get_duplicates():
    """Get duplicate files."""
    global _cache
    
    if not _cache:
        return []
    
    dups = _cache.find_duplicates()
    
    result = []
    for dup in dups:
        files = []
        for path in dup['files']:
            files.append({
                'path': path,
                'name': os.path.basename(path),
                'dir': os.path.dirname(path)
            })
        
        result.append({
            'files': files,
            'file_size': dup['size'],
            'file_size_human': humanize.naturalsize(dup['size']),
            'wasted_space': dup['wasted'],
            'wasted_space_human': humanize.naturalsize(dup['wasted']),
            'count': dup['count']
        })
    
    return result


def get_cache_folders():
    """Get system cache folders."""
    from .system_cache import scan_cache_folders
    
    folders = scan_cache_folders()
    
    result = []
    for path, name, description, size, clearable in folders:
        result.append({
            'path': path,
            'name': name,
            'description': description,
            'size': size,
            'size_human': humanize.naturalsize(size),
            'clearable': clearable
        })
    
    return result


def search_files(query):
    """Search for files matching the query."""
    global _cache
    
    if not _cache or not query:
        return []
    
    results = _cache.search_files(query)
    scan_root = _cache.get_scan_root() or ''
    
    result = []
    for full_path, name, size, is_dir, is_hidden, mtime, rel_path in results[:50]:
        result.append({
            'path': full_path,
            'name': name,
            'size': size,
            'size_human': humanize.naturalsize(size),
            'is_dir': is_dir,
            'relative_path': rel_path
        })
    
    return result


def do_rescan(path):
    """Trigger a rescan of the given path."""
    global _cache
    
    if not _cache:
        return False, "Cache not initialized"
    
    try:
        _cache.scan_directory_tree(path)
        return True, "Scan complete"
    except Exception as e:
        return False, str(e)


def do_open(path):
    """Open item in Finder."""
    from .utils import open_file_explorer
    
    if not os.path.exists(path):
        return False, "Path not found"
    
    try:
        open_file_explorer(path, os.path.basename(path))
        return True, "Opened in Finder"
    except Exception as e:
        return False, str(e)


def do_delete(path):
    """Move item to trash."""
    from .file_operations import delete_item, remove_from_cache
    
    if not os.path.exists(path):
        return False, "Path not found"
    
    success, msg = delete_item(path, use_trash=True)
    if success:
        remove_from_cache(path)
    
    return success, msg


def do_clear_cache(path):
    """Clear a cache folder."""
    from .system_cache import clear_folder
    
    if not os.path.exists(path):
        return False, "Path not found", 0
    
    return clear_folder(path)


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for the dashboard."""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve static files from
        self.static_dir = os.path.join(os.path.dirname(__file__), 'static')
        super().__init__(*args, directory=self.static_dir, **kwargs)
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass
    
    def send_json(self, data, status=200):
        """Send a JSON response."""
        try:
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except BrokenPipeError:
            pass  # Client disconnected, ignore
    
    def send_error_json(self, message, status=400):
        """Send an error JSON response."""
        self.send_json({'error': message}, status)
    
    def serve_thumbnail(self, file_path):
        """Serve an image file as a thumbnail."""
        # Image extensions we support
        IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.ico', '.svg'}
        MIME_TYPES = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
            '.ico': 'image/x-icon',
            '.svg': 'image/svg+xml'
        }
        
        # Security: validate path
        if not file_path or not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return
        
        # Check extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            self.send_error(400, "Not an image file")
            return
        
        # Serve the file
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', MIME_TYPES.get(ext, 'application/octet-stream'))
            self.send_header('Content-Length', len(content))
            self.send_header('Cache-Control', 'max-age=3600')  # Cache for 1 hour
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))
    
    def serve_media(self, file_path):
        """Serve image or video files for preview."""
        MEDIA_EXTENSIONS = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
            '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
            '.svg': 'image/svg+xml',
            '.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime',
            '.m4v': 'video/x-m4v', '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo'
        }
        
        if not file_path or not os.path.isfile(file_path):
            self.send_error(404, "File not found")
            return
        
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in MEDIA_EXTENSIONS:
            self.send_error(400, "Not a media file")
            return
        
        try:
            file_size = os.path.getsize(file_path)
            mime_type = MEDIA_EXTENSIONS.get(ext, 'application/octet-stream')
            
            # Handle range requests for video streaming
            range_header = self.headers.get('Range')
            if range_header and ext in ['.mp4', '.webm', '.mov', '.m4v', '.mkv', '.avi']:
                # Parse range header
                range_match = range_header.replace('bytes=', '').split('-')
                start = int(range_match[0]) if range_match[0] else 0
                end = int(range_match[1]) if range_match[1] else file_size - 1
                
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    content = f.read(end - start + 1)
                
                self.send_response(206)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Length', len(content))
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                self.wfile.write(content)
            else:
                # Serve full file
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Length', len(content))
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        # API endpoints
        if path == '/api/folder':
            folder_path = params.get('path', [_current_dir or os.path.expanduser('~')])[0]
            data = get_folder_data(folder_path)
            if data:
                self.send_json(data)
            else:
                self.send_error_json("Folder not found", 404)
        
        elif path == '/api/stats':
            data = get_stats()
            if data:
                self.send_json(data)
            else:
                self.send_error_json("No scan data available", 404)
        
        
        elif path == '/api/extensions':
            folder_path = params.get('path', [None])[0]
            data = get_extensions(folder_path)
            self.send_json(data)
        
        elif path == '/api/largest':
            folder_path = params.get('path', [None])[0]
            limit = int(params.get('limit', ['20'])[0])
            data = get_largest_files(folder_path, limit)
            self.send_json(data)
        
        elif path == '/api/duplicates':
            data = get_duplicates()
            self.send_json(data)
        
        elif path == '/api/cache-folders':
            data = get_cache_folders()
            self.send_json(data)
        
        elif path == '/api/search':
            query = params.get('q', [''])[0]
            data = search_files(query)
            self.send_json(data)
        
        elif path == '/api/thumbnail':
            # Serve actual image files as thumbnails
            file_path = params.get('path', [''])[0]
            self.serve_thumbnail(file_path)
        
        elif path == '/api/media':
            # Serve full media files for preview (images and videos)
            file_path = params.get('path', [''])[0]
            self.serve_media(file_path)
        
        elif path == '/' or path == '/index.html':
            # Serve the dashboard
            self.path = '/dashboard.html'
            super().do_GET()
        
        else:
            # Serve static files
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_error_json("Invalid JSON", 400)
            return
        
        if path == '/api/rescan':
            target_path = data.get('path', _current_dir or os.path.expanduser('~'))
            success, msg = do_rescan(target_path)
            self.send_json({'success': success, 'message': msg})
        
        elif path == '/api/open':
            target_path = data.get('path')
            if not target_path:
                self.send_error_json("Path required", 400)
                return
            success, msg = do_open(target_path)
            self.send_json({'success': success, 'message': msg})
        
        elif path == '/api/delete':
            target_path = data.get('path')
            if not target_path:
                self.send_error_json("Path required", 400)
                return
            success, msg = do_delete(target_path)
            self.send_json({'success': success, 'message': msg})
        
        elif path == '/api/clear-cache':
            target_path = data.get('path')
            if not target_path:
                self.send_error_json("Path required", 400)
                return
            success, msg, freed = do_clear_cache(target_path)
            self.send_json({
                'success': success, 
                'message': msg,
                'freed': freed,
                'freed_human': humanize.naturalsize(freed) if freed else '0 B'
            })
        
        else:
            self.send_error_json("Not found", 404)
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def start_dashboard(cache, current_dir=None, port=5001, open_browser=True):
    """Start the web dashboard server.
    
    Args:
        cache: The DirectoryCache instance
        current_dir: Current directory to show initially
        port: Port to run the server on
        open_browser: Whether to open browser automatically
    """
    global _cache, _current_dir
    _cache = cache
    _current_dir = current_dir or cache.get_scan_root() or os.path.expanduser('~')
    
    server = HTTPServer(('localhost', port), DashboardHandler)
    
    if open_browser:
        # Open browser after a short delay
        def open_delayed():
            import time
            time.sleep(0.5)
            webbrowser.open(f'http://localhost:{port}')
        
        threading.Thread(target=open_delayed, daemon=True).start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
