"""Summarize real kit artifacts, including 500 Hz thrash and all starts."""
import argparse
import codecs
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('directory',type=Path)
p.add_argument('--repeats',type=int,default=3)
p.add_argument('--output',type=Path,default=ROOT/'reports/native-summary.json')
a=p.parse_args()
base=next(a.directory.rglob('standard-1/builder-check.json')).resolve().parent.parent
provenance=json.loads((ROOT/'dist/image-provenance.json').read_text())


def peak_thrash(path):
    # The kit stores a large JSON scalar in thrash.npy. Stream it rather than
    # materializing millions of per-joint Python dictionaries.
    with zipfile.ZipFile(path) as archive,archive.open('thrash.npy') as stream:
        version=np.lib.format.read_magic(stream)
        shape,order,dtype=(np.lib.format.read_array_header_1_0(stream) if version==(1,0)
                           else np.lib.format.read_array_header_2_0(stream))
        if shape!=() or dtype.kind not in ('U','S'):
            raise ValueError('Unexpected kit thrash trace format')
        encoding=('utf-32-be' if dtype.byteorder=='>' else 'utf-32-le') if dtype.kind=='U' else 'utf-8'
        decoder=codecs.getincrementaldecoder(encoding)()
        carry=''
        peak=0.
        count=0
        while chunk:=stream.read(4*1024*1024):
            value=carry+decoder.decode(chunk)
            for found in re.finditer(r'"weighted_rms"\s*:\s*([0-9.eE+-]+)\s*[,}]',value):
                peak=max(peak,float(found[1]))
                count+=1
            carry=value[-256:]
        if not count:
            raise ValueError('No thrash samples found')
        return peak


rows=[]
for kind in ('standard','task'):
    for repeat in range(1,a.repeats+1):
        directory=base/f'{kind}-{repeat}'
        check=json.loads((directory/'builder-check.json').read_text())
        report=json.loads((directory/'report.json').read_text())
        invocation=json.loads((directory/'invocation.json').read_text())
        assert invocation['runtime']=='native ARM64'
        assert invocation['image_archive_sha256']==provenance['archive_sha256']
        assert invocation['image_id']==provenance['archive_config_digest']
        hard=[v for w in report['warnings'].values() for v in w.get('limits',[])]
        score=json.loads((directory/'task-check.json').read_text()) if kind=='task' else None
        trace=directory/'trace.npz'
        rows.append(dict(scene=kind,repeat=repeat,builder_status=check['status'],reason=report['reason'],
            clean=check['status']=='simulation_checks_complete' and not report['reason'] and not hard,
            exited=score['exited'] if score else None,exit_time=score['exit_time'] if score else None,
            seconds=report['seconds'],commands=report['commands'],diagnostic_warnings=len(report['warnings']),
            hard_findings=hard,peak_thrash=peak_thrash(trace),
            github_run=invocation['github_run'],report_timeout_patch=invocation['report_timeout_patch'],
            report_path=str((directory/'report.json').relative_to(ROOT)),
            report_sha256=hashlib.sha256((directory/'report.json').read_bytes()).hexdigest(),
            trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest()))
        print(kind,repeat,'checked',flush=True)
counterfactuals=[]
for path in sorted(base.glob('counterfactuals-*/**/report.json')):
    report=json.loads(path.read_text())
    counterfactuals.append(dict(path=str(path.relative_to(ROOT)),pose=report.get('pose'),status=report.get('status'),
        scene=path.relative_to(base).parts[0].replace('counterfactuals-',''),
        reason=report.get('reason'),detail=report.get('detail'),seconds=report.get('seconds'),
        handoff=report.get('policy_handoff_at_secs'),commands=report.get('commands'),
        first_stop_time=report.get('stop_time_seconds'),warnings=report.get('warnings'),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
for scene in ('standard','task'):
    directory=base/f'counterfactuals-{scene}'
    if not directory.exists():
        continue
    log=(directory/'launcher.log').read_text()
    for pose in ('standing','seated','supine','prone','left_side','right_side'):
        if any(r['scene']==scene and r['pose']==pose for r in counterfactuals):
            continue
        initial_error=f'invalid {pose} pose: substantial initial penetration'
        counterfactuals.append(dict(scene=scene,pose=pose,status='error',reason='no_report',
            detail=initial_error if initial_error in log else 'See raw launcher log',
            path=str((directory/'launcher.log').relative_to(ROOT)),handoff=None,commands=None,
            sha256=hashlib.sha256((directory/'launcher.log').read_bytes()).hexdigest()))
standard=sum(r['clean'] for r in rows if r['scene']=='standard')
task=sum(r['clean'] for r in rows if r['scene']=='task')
exits=sum(bool(r['exited']) for r in rows if r['scene']=='task')
result=dict(repeats=a.repeats,standard_passes=standard,task_passes=task,task_exits=exits,
    task_status='simulation_checks_complete' if task==a.repeats else 'incomplete or findings',
    exact_image_gate_passed=standard==task==exits==a.repeats,
    image_sha256=provenance['archive_sha256'],archive_config_digest=provenance['archive_config_digest'],
    native_peak_thrash=max(r['peak_thrash'] for r in rows),rows=rows,counterfactuals=counterfactuals,
    hardware_authorization=False,
    note='Standard uses canonical kit. Task uses isolated report-only RPC timeout extension; active checks and plant are unchanged. Counterfactual findings are reported separately, never counted as passes.')
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('rows','counterfactuals')},indent=2))
