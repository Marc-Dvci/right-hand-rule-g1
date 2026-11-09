"""Run the preregistered matched-seed controls and latency stresses."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser()
p.add_argument('--workers',type=int,default=2)
a=p.parse_args()
protocol=json.loads((ROOT/'evaluation_protocol.json').read_text())
common=[sys.executable,str(ROOT/'harness/cohort.py'),'--randomize','--transport',
        '--parameters',str(ROOT/'config/navigation.json'),'--transport-config',str(ROOT/'config/deployment.json'),
        '--seconds','400','--workers',str(a.workers)]
for mode in protocol['controls']['modes']:
    name='final-control-'+mode
    if (ROOT/'evidence/cohorts'/name).exists():
        raise SystemExit('Refusing to overwrite '+name)
    subprocess.run(common+['--seeds',*map(str,protocol['controls']['seeds']),
                   '--mode',mode,'--latency-steps','0','--name',name],check=True)
for ms in protocol['latency_stress']['additional_full_frame_command_latency_ms']:
    name=f'final-latency-{ms}ms'
    if (ROOT/'evidence/cohorts'/name).exists():
        raise SystemExit('Refusing to overwrite '+name)
    subprocess.run(common+['--seeds',*map(str,protocol['latency_stress']['seeds']),
                   '--latency-steps',str(ms//20),'--name',name],check=True)
for seed in protocol['controls']['seeds']:
    target=ROOT/f'evidence/cohorts/final-control-map_only/map_only-{seed}'
    if target.exists():
        raise SystemExit('Refusing to overwrite '+str(target))
    subprocess.run([sys.executable,str(ROOT/'harness/map_baseline.py'),
                    '--seed',str(seed),'--output',str(target)],check=True)
