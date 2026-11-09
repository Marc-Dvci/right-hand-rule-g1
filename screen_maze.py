"""Small task screen for HIM: explicit joint/IMU boundary and geometric exit."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--seed',type=int,default=0)
p.add_argument('--seconds',type=int,default=400)
p.add_argument('--randomize',action='store_true')
p.add_argument('--container',action='store_true',help='Use the loaded right-hand-rule:local image in the real ROS kit')
a=p.parse_args()
if a.container:
    if a.randomize:
        raise SystemExit('Container mode tests the static scene; dynamic randomization is harness-only.')
    from harness.scenes import make
    scene=make('maze',a.seed)
    name=f'screen-maze-{a.seed}'
    subprocess.run([sys.executable,str(ROOT/'tools/run_kit.py'),'--scene',scene.stem,
                    '--seconds',str(a.seconds),'--name',name,'--report-timeout-fix'],check=True)
    import platform
    kind='container-native' if platform.machine().lower() in ('aarch64','arm64') else 'container-qemu'
    subprocess.run([sys.executable,str(ROOT/'tools/score_container.py'),str(ROOT/'evidence'/kind/name),str(scene)],check=True)
else:
    command=[sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','maze','--seed',str(a.seed),
        '--seconds',str(a.seconds),'--parameters',str(ROOT/'config/navigation.json'),'--transport',
        '--transport-config',str(ROOT/'config/deployment.json'),'--latency-steps','0',
        '--output',str(ROOT/f'evidence/screen-maze-{a.seed}')]
    if a.randomize:
        command.append('--randomize')
    subprocess.run(command,check=True)
    r=json.loads((ROOT/f'evidence/screen-maze-{a.seed}/report.json').read_text())
    raise SystemExit(0 if r['exited'] and not r['reason'] and not any(w.get('limits') for w in r['warnings'].values()) else 2)
