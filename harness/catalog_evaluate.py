"""A topology-disjoint maze screen; task truth stays outside the controller."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
from pathlib import Path
import argparse
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness import evaluate
from harness.maze_catalog import wall_segments
from harness.scenes import write_scene
from harness.protocol import validate_episode


def make_scene(layout,seed,width):
    return write_scene(f'maze-{seed}-layout{layout}-w{width:.3f}',wall_segments(layout,width),
        dict(axis=0,value=2.5*width+.25,sign=1,min_y=1.5*width,max_y=2.5*width))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--layout-id',type=int,required=True)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--seconds',type=int,default=600)
    p.add_argument('--mode',default='navigate')
    p.add_argument('--delay',type=int,choices=(0,1,2),default=0)
    p.add_argument('--control-config',type=Path,required=True)
    p.add_argument('--parameters',type=Path,default=ROOT/'config/navigation.json')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--final',action='store_true')
    a=p.parse_args()
    protocol=json.loads((ROOT/'review/evaluation_v2_protocol.json').read_text())
    validate_episode(protocol,layout=a.layout_id,seed=a.seed,seconds=a.seconds,mode=a.mode,
        delay=a.delay,final=a.final,root=ROOT,parameters=a.parameters,control=a.control_config)
    if a.output.exists() and any(p.name!='run.log' for p in a.output.iterdir()):
        raise SystemExit('Refusing to replace existing episode evidence')
    if a.final:
        from tools.freeze_v2 import check
        freeze=check()
    evaluate.make=lambda kind,seed,width:make_scene(a.layout_id,seed,width)
    report=evaluate.run('maze',a.seed,a.seconds,a.mode,None,a.output,
        parameters=json.loads(a.parameters.read_text()),randomize=True,transport=True,
        transport_config={'max_gap_frames':5},latency_steps=a.delay,
        control=json.loads(a.control_config.read_text()))
    report['layout_id']=a.layout_id
    report['split']='geometry_holdout' if a.final else 'development_geometry'
    report['scene_generator_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        for name in ('harness/catalog_evaluate.py','harness/maze_catalog.py')}
    report['protocol_sha256']=hashlib.sha256((ROOT/'review/evaluation_v2_protocol.json').read_bytes()).hexdigest()
    if a.final:
        check()
        report['freeze_sha256']=hashlib.sha256((ROOT/'evaluation/frozen-v2.json').read_bytes()).hexdigest()
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
