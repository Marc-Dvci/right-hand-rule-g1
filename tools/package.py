"""Assemble the contest ZIP and transparent, size-bounded evidence artifacts."""
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
DIST.mkdir(exist_ok=True)
summary=json.loads((ROOT/'reports/final-nominal/summary.json').read_text())
audit=json.loads((ROOT/'reports/final-audit.json').read_text())
native=json.loads((ROOT/'reports/native-summary.json').read_text())
assert audit['primary_gate_passed'] and native['exact_image_gate_passed']
assert audit['episodes']==summary['episodes']==100
film=json.loads((DIST/'result.json').read_text())
video=DIST/'result.mp4'
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
files={ROOT/name for name in tracked if name}
for directory in (ROOT/'reports',ROOT/'evidence/cohorts'):
    for p in directory.rglob('*'):
        current_report=(directory.name=='reports' and (p.relative_to(directory).parts[0] in
                        ('final-nominal','comparisons','hero','final-audit.json','native-summary.json')))
        if p.is_file() and (current_report or ('final-' in str(p) and p.name in ('report.json','run.log','freeze.json'))):
            files.add(p)
for p in (ROOT/'evidence/walker').glob('*'):
    if p.is_file():
        files.add(p)
for p in (ROOT/'evidence/optimization/cma-dev-v1').glob('*'):
    if p.suffix in ('.json','.jsonl'):
        files.add(p)
native_paths={ROOT/row['report_path'] for row in native['rows']}
native_base=next(iter(native_paths)).parent.parent
for p in native_base.rglob('*'):
    if p.is_file() and p.suffix in ('.json','.log'):
        files.add(p)
for name in ('image-provenance.json','result.json'):
    files.add(DIST/name)
full_traces=[ROOT/film['hero']/'trace.npz',
    ROOT/'evidence/cohorts/final-control-neutral/neutral-26111500/trace.npz',
    ROOT/'evidence/cohorts/final-control-touch_off/touch_off-26111500/trace.npz']
files.update(full_traces)
virtual={}
motion_index=[]
motion_archive=DIST/'maze-trajectories.zip'
with zipfile.ZipFile(motion_archive,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
    for row in summary['rows']:
        report=ROOT/row['report_path']
        trace=report.parent/'trace.npz'
        with np.load(trace,allow_pickle=False) as z:
            data=io.BytesIO()
            np.savez_compressed(data,time=z['time'],qpos=z['qpos'])
        replay=data.getvalue()
        replay_name=(report.parent/'replay.npz').relative_to(ROOT).as_posix()
        archive.writestr(replay_name,replay)
        archive.write(report,report.relative_to(ROOT).as_posix())
        motion_index.append(dict(seed=row['seed'],report=report.relative_to(ROOT).as_posix(),
            replay=replay_name,replay_sha256=hashlib.sha256(replay).hexdigest(),
            full_trace_sha256=next(r['trace_sha256'] for r in audit['rows'] if r['seed']==row['seed'])))
        if row['seed'] in film['grid_seeds'] and row['seed']!=26111500:
            virtual[replay_name]=replay
    index=dict(episodes=100,rows=motion_index,
        reduction='Lossless selection of time and floating-base qpos from each full local trace. Other channels remain in the recorded local traces, identified by their full SHA-256. No resampling or state changes.')
    archive.writestr('MOTION_INDEX.json',json.dumps(index,indent=2)+'\n')
virtual['MOTION_INDEX.json']=(json.dumps(index,indent=2)+'\n').encode()
package=DIST/'RightHandRule.zip'
inventory=[]
with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as archive:
    def add(name,data,executable=False):
        info=zipfile.ZipInfo('RightHandRule/'+name,date_time=(2026,11,9,0,0,0))
        info.create_system=3
        info.external_attr=(stat.S_IFREG|(0o755 if executable else 0o644))<<16
        info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
        inventory.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    for p in sorted(files):
        if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('Invalid package input: '+str(p))
        name=p.relative_to(ROOT).as_posix()
        if any(x in p.relative_to(ROOT).parts for x in ('.git','.venv','.aws','.ssh','.env')):
            raise ValueError('Private path in package')
        add(name,p.read_bytes(),p.suffix=='.sh')
    for name,data in sorted(virtual.items()):
        add(name,data)
    add('PACKAGE_INVENTORY.json',(json.dumps(dict(files=inventory),indent=2)+'\n').encode())
    if archive.testzip():
        raise ValueError('ZIP integrity failure')
assert video.stat().st_size<=50_000_000,'Video exceeds contest limit'
assert package.stat().st_size+video.stat().st_size<=100_000_000,'Combined contest files exceed 100 MB'
raw_native=DIST/'native-arm64-evidence.zip'
with zipfile.ZipFile(raw_native,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
    for p in sorted(native_base.rglob('*')):
        if p.is_file():
            archive.write(p,p.relative_to(ROOT).as_posix())
artifacts=[]
for p in (package,video,DIST/'submission.tar',motion_archive,raw_native):
    digest=hashlib.sha256()
    with p.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    artifacts.append(dict(name=p.name,bytes=p.stat().st_size,sha256=digest.hexdigest()))
manifest=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
    artifacts=artifacts,contest_combined_bytes=package.stat().st_size+video.stat().st_size,
    primary_gate_passed=True,native_gate_passed=True,hardware_authorization=False)
(DIST/'artifacts.json').write_text(json.dumps(manifest,indent=2)+'\n')
(DIST/'SHA256SUMS').write_text(''.join(f'{r["sha256"]}  {r["name"]}\n' for r in artifacts))
print(json.dumps(manifest,indent=2))
