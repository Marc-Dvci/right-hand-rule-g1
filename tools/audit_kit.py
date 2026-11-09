from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile
import shutil
import argparse

ROOT = Path(__file__).resolve().parents[1]
archive = ROOT/'research/g1-builder-kit-e93c492-v1.zip'
archive.parent.mkdir(parents=True, exist_ok=True)
if not archive.exists():
    urllib.request.urlretrieve('https://arena.himrobotics.com/policy-contracts/g1-builder-kit-e93c492-v1.zip', archive)
fresh = ROOT/'research/official-kit'
if not fresh.exists():
    with zipfile.ZipFile(archive) as z:
        z.extractall(fresh)
source = next(fresh.rglob('UPSTREAM_FILES.json')).parent
target = ROOT/'vendor/builder-kit'
rows = []
for f in source.rglob('*'):
    if not f.is_file():
        continue
    relative = f.relative_to(source)
    other = target/relative
    if not other.exists() or other.read_bytes() != f.read_bytes():
        rows.append(str(relative))
        other.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, other)
report = dict(archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
              mismatches_in_reused_kit=rows, action='Replaced mismatching files with fresh public archive bytes')
manifest = json.loads((target/'UPSTREAM_FILES.json').read_text())
report['manifest_mismatches'] = [row['path'] for row in manifest['files']
    if hashlib.sha256((target/row['path']).read_bytes()).hexdigest() != row['sha256']]
if report['manifest_mismatches']:
    raise RuntimeError(report['manifest_mismatches'])
(ROOT/'research/kit-integrity.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
