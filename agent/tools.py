"""Bounded local file tools and HTTP verification for the practice agents."""
from pathlib import Path
from urllib.parse import urlsplit
import requests

BASE = str(Path(__file__).resolve().parent.parent)
TARGET_HOST = "http://127.0.0.1:5000"
SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules"}
SUFFIXES = {".py", ".json", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".toml", ".md", ".txt"}
MAX_BYTES = 100_000

def _boundary(scan_dir):
    return str((Path(BASE) / scan_dir).resolve())

def _resolve(scan_dir, requested):
    if not isinstance(scan_dir, str) or not isinstance(requested, str):
        return None, "ERROR: paths must be strings"
    try:
        base = Path(BASE).resolve()
        boundary = (base / scan_dir).resolve()
        target = (boundary / requested).resolve()
        if not boundary.is_relative_to(base) or not target.is_relative_to(boundary):
            return None, "ERROR: outside the allowed scan directory"
        return str(target), None
    except (OSError, ValueError, RuntimeError):
        return None, "ERROR: invalid path"

def list_files(scan_dir, root="."):
    import os
    target, err = _resolve(scan_dir, root)
    if err:
        return err
    if not Path(target).is_dir():
        return "ERROR: no such directory"
    found = []
    boundary = Path(_boundary(scan_dir))
    for directory, dirs, files in os.walk(target, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not (Path(directory)/d).is_symlink())
        for name in sorted(files):
            p = Path(directory)/name
            if p.is_symlink():
                continue
            if p.suffix.lower() in SUFFIXES or name.startswith('.env') or name in {'Dockerfile', '.htaccess'}:
                found.append(str(p.relative_to(boundary)))
    return sorted(found)

def read_file(scan_dir, path):
    target, err = _resolve(scan_dir, path)
    if err:
        return err
    try:
        p = Path(target)
        if p.stat().st_size > MAX_BYTES:
            return "ERROR: file exceeds read limit"
        text = p.read_text(encoding="utf-8")
        return '\n'.join(f'{i:4}: {line}' for i, line in enumerate(text.splitlines(), 1))
    except (OSError, UnicodeError):
        return "ERROR: cannot read text file"

def write_file(scan_dir, path, contents):
    # Intentionally narrow: the model cannot overwrite source or arbitrary files.
    if path != 'app_fixed.py' or not isinstance(contents, str):
        return "ERROR: only app_fixed.py may be written"
    if len(contents.encode('utf-8')) > MAX_BYTES:
        return "ERROR: file exceeds write limit"
    target, err = _resolve(scan_dir, path)
    if err:
        return err
    if Path(_boundary(scan_dir), path).is_symlink():
        return "ERROR: refusing symlink output"
    try:
        compile(contents, path, 'exec')  # Validate syntax; never execute generated code.
        Path(target).write_text(contents, encoding='utf-8')
    except (OSError, SyntaxError, ValueError):
        return "ERROR: write failed or invalid Python"
    return f'Wrote {len(contents)} characters to app_fixed.py; runtime verification pending'

def send_request(method, path, data=None):
    if not isinstance(method, str) or method.upper() not in {'GET', 'POST'}:
        return {'error': 'only GET and POST are allowed'}
    if not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or '\\' in path:
        return {'error': 'expected a local route beginning with one slash'}
    parts = urlsplit(path)
    if parts.scheme or parts.netloc or parts.fragment:
        return {'error': 'only local routes are allowed'}
    try:
        # Redirects cannot carry verification traffic off the local application.
        with requests.request(method.upper(), TARGET_HOST + path,
                              json=(data or {}) if method.upper() == 'POST' else None,
                              timeout=10, allow_redirects=False, stream=True) as response:
            body = response.raw.read(MAX_BYTES + 1, decode_content=True)
            return {'status': response.status_code,
                    'body': body[:MAX_BYTES].decode('utf-8', errors='replace'),
                    'truncated': len(body) > MAX_BYTES}
    except requests.RequestException:
        return {'error': 'local request failed; verify the practice app is running'}
