"""Stage the pinned public kit and NVIDIA networks, verifying every download."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
KIT_SOURCE = ROOT.parents[1] / 'Ping Pong challenge/research/kit/g1-builder-kit'
KIT = ROOT / 'vendor/builder-kit'
REVISION = 'b042411fae38ee4d1af9aac82a37a1f8d14d6dd0'


def main():
    if not KIT.exists():
        shutil.copytree(KIT_SOURCE, KIT, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'output', 'submission.tar'))
    models = ROOT / 'policy/models'
    models.mkdir(parents=True, exist_ok=True)
    provenance = json.loads((KIT / 'examples/policies/walker/provenance.json').read_text())
    for name, spec in provenance['files'].items():
        target = models / name
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != spec['sha256']:
            bundled = KIT / 'examples/policies/walker' / name
            if bundled.exists():
                shutil.copyfile(bundled, target)
            else:
                url = f'https://media.githubusercontent.com/media/NVlabs/GR00T-WholeBodyControl/{REVISION}/{provenance["upstream_directory"]}/{spec["upstream"]}'
                print('Downloading', name, flush=True)
                urllib.request.urlretrieve(url, target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != spec['sha256']:
            raise RuntimeError(f'Wrong model digest: {name}: {digest}')
        print(name, digest, flush=True)
    shutil.copyfile(KIT / 'examples/policies/walker/LICENSE', models / 'LICENSE-NVIDIA')
    (models / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    import importlib.metadata
    for name in ('mujoco', 'numpy', 'onnxruntime', 'onnx', 'imageio', 'imageio-ffmpeg', 'pytest'):
        try:
            print(name, importlib.metadata.version(name))
        except importlib.metadata.PackageNotFoundError:
            print(name, 'MISSING')


if __name__ == '__main__':
    main()
