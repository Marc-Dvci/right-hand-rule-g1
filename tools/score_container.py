"""Score the actual task from the builder kit's own saved base trajectory."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.scoring import score_trajectory

p = argparse.ArgumentParser()
p.add_argument('run',type=Path)
p.add_argument('scene',type=Path)
a = p.parse_args()
spec = json.loads(a.scene.with_suffix('.json').read_text())
trace = a.run/'trace.npz'
with np.load(trace,allow_pickle=False) as z:
    # The original kit saves full qpos including its floating base.
    times = z['t'] if 't' in z else z['time']
    entrance = min(point[0] for wall in spec['walls'] for point in wall)-.15
    result = score_trajectory(times,z['qpos'],spec['exit'],entrance)
result['trace_sha256'] = hashlib.sha256(trace.read_bytes()).hexdigest()
result['method'] = 'Outward crossing of the declared exit segment, before any return through the entrance; kit trace only.'
(a.run/'task-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['exited'] else 2)
