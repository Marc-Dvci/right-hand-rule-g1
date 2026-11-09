from pathlib import Path
import json
import numpy as np
import sys
root = Path(__file__).resolve().parents[1]
path = root/sys.argv[1]
report = json.loads((path/'report.json').read_text())
with np.load(path/'trace.npz') as z:
    for event in report['controller_events']:
        i = int(np.argmin(abs(z['time']-(event['time']+2.))))
        print(round(z['time'][i],2), event['target'], 'pos', z['qpos'][i,:2].round(3).tolist(),
              'est',z['estimated_force'][i].round(1).tolist(), 'truth',z['true_force'][i].round(1).tolist())
