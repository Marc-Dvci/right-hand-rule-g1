"""Stage the pinned public kit and NVIDIA networks, verifying every download."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import urllib.request
import argparse
import zipfile

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'vendor/builder-kit'
REVISION = 'b042411fae38ee4d1af9aac82a37a1f8d14d6dd0'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kit-source',type=Path,help='Optional existing public kit directory')
    args = parser.parse_args()
    if not KIT.exists():
        if args.kit_source:
            shutil.copytree(args.kit_source, KIT, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'output', 'submission.tar'))
        else:
            archive = ROOT/'research/g1-builder-kit-e93c492-v1.zip'
            archive.parent.mkdir(parents=True,exist_ok=True)
            urllib.request.urlretrieve('https://arena.himrobotics.com/policy-contracts/g1-builder-kit-e93c492-v1.zip',archive)
            with zipfile.ZipFile(archive) as z:
                z.extractall(KIT.parent)
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
