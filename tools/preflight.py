"""Check the documented host environment without installing or changing it."""
import ctypes.util
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
issues=[]
versions={}
if sys.version_info[:2]!=(3,12):
    issues.append('Use Python 3.12 for the pinned evaluation environment.')
for line in (ROOT/'requirements.txt').read_text().splitlines():
    if '==' not in line or line.lstrip().startswith('#'):
        continue
    package,expected=line.strip().split('==')
    try:
        actual=importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        actual=None
    versions[package]=actual
    if actual!=expected:
        issues.append(f'{package}: expected {expected}, found {actual}; install requirements.txt in a fresh venv.')
if not ctypes.util.find_library('EGL'):
    issues.append('Saved-state rendering needs a working EGL driver (for Ubuntu CPU rendering: libegl1 and libgl1-mesa-dri).')
print(json.dumps(dict(python=sys.version.split()[0],versions=versions,issues=issues),indent=2))
raise SystemExit(1 if issues else 0)
