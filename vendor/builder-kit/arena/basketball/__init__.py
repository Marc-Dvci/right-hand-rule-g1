"""Fingerprint-only dispatch; importing this module never imports submission code."""
import hashlib
import json
from pathlib import Path

MANIFEST = json.loads((Path(__file__).parent / "bundle.json").read_text())


def digest(path):
    data = Path(path).read_bytes()
    if Path(path).suffix in ('.py', '.xml', '.json', '.md', '.urdf'):
        data = data.replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest()


def identify_bundle(base):
    declaration = base / 'arena-policy.json'
    declared_profile = False
    if declaration.is_file() and declaration.stat().st_size <= 16384:
        try:
            data = json.loads(declaration.read_text())
            declared_profile = (isinstance(data, dict) and data.get('safety_adapter') == 'g1-basketball-115-profile-v1'
                                and data.get('model') == 'policy.onnx')
        except (ValueError, OSError):
            pass
    for variant in MANIFEST['variants']:
        if declared_profile and variant.get('controller') != 'profile-onnx':
            continue
        files = variant['files']
        # Explicit opt-in accepts a new ONNX controller under the same documented
        # observation/action contract and exact task assets; source code is unused.
        if declared_profile and variant.get('controller') == 'profile-onnx':
            files = {name: sha for name, sha in files.items() if name.startswith('assets/')}
        if all((base / name).is_file() and digest(base / name) == sha
               for name, sha in files.items()):
            return variant
    return None


def find_bundle(root):
    candidates = {p.parent for pattern in ('policy_weights.npz', 'arena-policy.json') for p in root.rglob(pattern)}
    matches = [base for base in candidates if identify_bundle(base)]
    return matches[0] if len(matches) == 1 else None
