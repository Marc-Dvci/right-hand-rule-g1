"""Run the exact Arena bridge against data-only submissions; no uploaded Python executes."""
import argparse
import hashlib
import json
import stat
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / 'arena'), str(ROOT / 'packages/policy_safety/src'), str(ROOT / 'robot_safety')]
from basketball import find_bundle
from basketball.screen import screen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--episodes', type=int, default=12, choices=range(1, 101))
    args = parser.parse_args()
    release = json.loads((ROOT / 'arena/release.json').read_text())
    if args.archive.stat().st_size > release['max_archive_bytes']:
        raise ValueError('Archive exceeds the Arena size limit.')
    args.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(args.archive) as archive:
            infos = archive.infolist()
            if len(infos) > 5000 or sum(i.file_size for i in infos) > release['max_expanded_bytes']:
                raise ValueError('Archive exceeds extraction limits.')
            seen = set()
            for info in infos:
                name = info.filename.replace('\\', '/')
                p = PurePosixPath(name)
                if (not name or p.is_absolute() or '..' in p.parts or ':' in name or '\0' in name
                    or any(x in ('', '.', '..') for x in name.rstrip('/').split('/'))
                    or name.lower() in seen or stat.S_ISLNK(info.external_attr >> 16)
                    or info.flag_bits & 1 or info.compress_type not in (0, 8)):
                    raise ValueError('Unsafe or ambiguous archive entry.')
                seen.add(name.lower())
                target = root.joinpath(*p.parts)
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open('xb') as destination:
                        count = 0
                        while chunk := source.read(1024 * 1024):
                            count += len(chunk)
                            if count > info.file_size:
                                raise ValueError('Archive entry expanded beyond its declared size.')
                            destination.write(chunk)
        base = find_bundle(root)
        if base is None:
            raise ValueError('Unrecognized assets or controller declaration. Use the latest reference at https://arena.himrobotics.com/docs/g1-policy-checks#basketball')
        report = screen(base, args.output, release, episodes=args.episodes)
        with args.archive.open('rb') as source:
            source_sha = hashlib.file_digest(source, 'sha256').hexdigest()
        (args.output / 'source.json').write_text(json.dumps({'source_sha256': source_sha, 'release_id': release['id'], 'evidence': 'builder_local', 'hardware_authorization': False}, indent=2)+'\n')
        print(json.dumps({'status': report['status'], 'coverage': report['coverage'], 'task_summary': report['task_summary']}, indent=2))
        return report['exit_code']


if __name__ == '__main__':
    raise SystemExit(main())
