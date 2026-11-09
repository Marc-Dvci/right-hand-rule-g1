"""Verify and independently score every trajectory in the portable evidence ZIP."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness.scoring import score_trajectory

p=argparse.ArgumentParser()
p.add_argument('archive',type=Path)
a=p.parse_args()
exits=0
with zipfile.ZipFile(a.archive) as archive:
    index=json.loads(archive.read('MOTION_INDEX.json'))
    assert len(index['rows'])==index['episodes']==100
    protocol=json.loads((ROOT/'evaluation_protocol.json').read_text())
    assert sorted(r['seed'] for r in index['rows'])==protocol['final_seeds']
    for row in index['rows']:
        data=archive.read(row['replay'])
        assert hashlib.sha256(data).hexdigest()==row['replay_sha256']
        report=json.loads(archive.read(row['report']))
        assert report['seed']==row['seed']
        spec=report['scene_specification']
        entrance=min(p[0] for wall in spec['walls'] for p in wall)-.15
        with np.load(io.BytesIO(data),allow_pickle=False) as z:
            score=score_trajectory(z['time'],z['qpos'],spec['exit'],entrance)
        assert score['exited']==report['exited']
        exits+=score['exited']
print(json.dumps(dict(episodes=100,independently_scored_exits=exits,all_replay_digests_match=True)))
