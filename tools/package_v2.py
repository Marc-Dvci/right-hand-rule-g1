"""Package selected V2 source, all outcomes, portable motions and exact-image evidence."""
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import sys
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.freeze_v2 import check
from tools.sensor_replay import replay


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    check()
    dist=ROOT/'dist'
    audit=json.loads((ROOT/'reports/v2/final-audit.json').read_text())
    native=json.loads((ROOT/'reports/v2/native-summary.json').read_text())
    provenance=json.loads((dist/'image-provenance.json').read_text())
    runner=json.loads((ROOT/'g1-runner.json').read_text())
    film=json.loads((dist/'result.json').read_text())
    video=dist/'result.mp4'
    if not audit['controls_complete'] or len(audit['rows'])!=480:
        raise ValueError('Complete 300 primary and 180 control episodes are required')
    if not native['exact_image_gate_passed'] or native['image_sha256']!=provenance['archive_sha256'] or runner['image']['sha256']!=native['image_sha256']:
        raise ValueError('Runner does not reference the qualified exact image')
    if digest(ROOT/'reports/v2/final-audit.json')!=film['audit_sha256'] or digest(ROOT/'reports/v2/native-summary.json')!=film['native_summary_sha256']:
        raise ValueError('Film results differ from packaged audit')
    if digest(dist/'submission.tar')!=native['image_sha256']:
        raise ValueError('Image archive changed')
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    files={ROOT/name for name in tracked if name}
    files.update(p for p in (ROOT/'reports/v2').rglob('*') if p.is_file() and p.suffix=='.json')
    files.update((dist/name) for name in ('image-provenance.json','result.json'))
    bundle=ROOT/'evidence/sensor-proof/v2-selected.npz'
    proof=replay(bundle)
    if not proof['bitwise_numeric_match'] or proof['simulator_imported']:
        raise ValueError('Sensor-only replay failed')
    files.add(bundle)
    files.add(ROOT/'review/results/sensor-replay-v2-selected.json')
    virtual={}
    motion_artifacts=[]
    for delay in (0,20,40):
        target=dist/f'v2-trajectories-delay{delay}.zip'
        index=[]
        with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
            for row in sorted((r for r in audit['rows'] if r['delay_ms']==delay),key=lambda r:(r['mode'],r['seed'])):
                report=ROOT/row['report_path']
                trace=report.parent/'trace.npz'
                if digest(report)!=row['report_sha256'] or digest(trace)!=row['trace_sha256']:
                    raise ValueError('Final evidence changed: '+str(report))
                with np.load(trace,allow_pickle=False) as z:
                    data=io.BytesIO()
                    np.savez_compressed(data,time=z['time'],qpos=z['qpos'])
                    motion=data.getvalue()
                    if str(report.parent.relative_to(ROOT)) in film['grid']:
                        clip=io.BytesIO()
                        np.savez_compressed(clip,**{k:z[k] for k in ('time','qpos','state','estimated_force','true_force_filtered')})
                        virtual[(report.parent/'replay.npz').relative_to(ROOT).as_posix()]=clip.getvalue()
                name=(report.parent/'replay.npz').relative_to(ROOT).as_posix()
                archive.writestr(name,motion)
                archive.write(report,report.relative_to(ROOT).as_posix())
                index.append(dict(mode=row['mode'],delay_ms=delay,seed=row['seed'],layout=row['layout'],
                    report=row['report_path'],report_sha256=row['report_sha256'],replay=name,
                    replay_sha256=hashlib.sha256(motion).hexdigest(),full_trace_sha256=row['trace_sha256']))
                files.add(report)
                files.add(report.parent/'run.log')
            manifest=dict(episodes=len(index),rows=index,
                reduction='Exact time/qpos arrays from recorded traces. No resampling or state changes. Full local sensor traces remain fingerprinted, not embedded in these portable archives.')
            archive.writestr('MOTION_INDEX.json',json.dumps(manifest,indent=2)+'\n')
        virtual[f'evaluation/results/v2/MOTION_INDEX_delay{delay}.json']=(json.dumps(manifest,indent=2)+'\n').encode()
        if target.stat().st_size>1_900_000_000:
            raise ValueError('Motion artifact requires smaller release chunks')
        motion_artifacts.append(target)
        print('Built',target.name,flush=True)
    native_base=(ROOT/native['rows'][0]['report_path']).parent.parent
    from tools.check_motion_v2 import check as check_motions
    portable=check_motions(motion_artifacts,audit)
    portable_path=ROOT/'reports/v2/portable-motion-check.json'
    portable_path.write_text(json.dumps(portable,indent=2)+'\n')
    files.add(portable_path)
    native_archive=dist/'native-arm64-evidence-v2.zip'
    with zipfile.ZipFile(native_archive,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
        for p in sorted(native_base.rglob('*')):
            if p.is_file():
                archive.write(p,p.relative_to(ROOT).as_posix())
                if p.suffix in ('.json','.log'):
                    files.add(p)
    package=dist/'RightHandRule.zip'
    inventory=[]
    with zipfile.ZipFile(package,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9,allowZip64=True) as archive:
        def add(name,data,executable=False):
            info=zipfile.ZipInfo('RightHandRule/'+name,date_time=(2026,11,10,0,0,0))
            info.create_system=3
            info.external_attr=(stat.S_IFREG|(0o755 if executable else 0o644))<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,data,compresslevel=9)
            inventory.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
        for path in sorted(files):
            if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()):
                raise ValueError('Invalid package input: '+str(path))
            name=path.relative_to(ROOT).as_posix()
            if any(p in ('.git','.venv','.aws','.ssh','.env','credentials.json') for p in path.relative_to(ROOT).parts):
                raise ValueError('Private package path')
            add(name,path.read_bytes(),path.suffix=='.sh')
        for name,data in sorted(virtual.items()):
            add(name,data)
        add('PACKAGE_INVENTORY.json',(json.dumps(dict(files=inventory),indent=2)+'\n').encode())
        if archive.testzip():
            raise ValueError('ZIP integrity failure')
    if video.stat().st_size>50_000_000 or package.stat().st_size+video.stat().st_size>100_000_000:
        raise ValueError('Contest upload size limit exceeded')
    artifacts=[]
    for p in (package,video,dist/'submission.tar',*motion_artifacts,native_archive):
        artifacts.append(dict(name=p.name,bytes=p.stat().st_size,sha256=digest(p)))
    manifest=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        artifacts=artifacts,contest_combined_bytes=package.stat().st_size+video.stat().st_size,
        primary_gate_passed=audit['primary_gate_passed'],native_gate_passed=True,hardware_authorization=False)
    (dist/'artifacts.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (dist/'SHA256SUMS').write_text(''.join(f'{r["sha256"]}  {r["name"]}\n' for r in artifacts))
    check()
    print(json.dumps(manifest,indent=2))


if __name__=='__main__':
    main()
