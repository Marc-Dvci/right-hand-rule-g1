"""CMA-ES on development seeds only. Parameters are immutable per episode."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import cma

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy.controller import Parameters

NAMES = list(Parameters.__dataclass_fields__)
LOW = np.array([.10,.05,.14,2.8,1.7,.25,.18,3.5,4.0])
HIGH = np.array([.22,.14,.34,6.5,3.8,1.,.42,7.5,8.0])


def policy_digest():
    h = hashlib.sha256()
    for f in sorted((ROOT/'policy').rglob('*')):
        if f.is_file() and '__pycache__' not in str(f):
            h.update(f.read_bytes())
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--generations',type=int,default=5)
    p.add_argument('--population',type=int,default=8)
    p.add_argument('--name',default='cma-dev-v1')
    args = p.parse_args()
    target = ROOT/'evidence/optimization'/args.name
    target.mkdir(parents=True,exist_ok=True)
    original_digest = policy_digest()
    seeds = [0,4,5]
    (target/'protocol.json').write_text(json.dumps(dict(seeds=seeds,optimizer='cma',version=cma.__version__,
        optimizer_seed=26110911,generations=args.generations,population=args.population,
        names=NAMES,lower=LOW.tolist(),upper=HIGH.tolist(),controller_sha256=original_digest,
        final_seeds_used=False),indent=2)+'\n')
    x0 = (np.array(list(asdict(Parameters()).values()))-LOW)/(HIGH-LOW)
    es = cma.CMAEvolutionStrategy(x0,.18,dict(bounds=[0,1],seed=26110911,popsize=args.population,
        maxiter=args.generations,verbose=-9,verb_log=0))
    best = -1e9
    count = 0
    while not es.stop():
        candidates = es.ask()
        objectives = []
        for x in candidates:
            assert policy_digest()==original_digest,'Policy changed during tuning; restart with a new cohort name'
            params = dict(zip(NAMES,(LOW+np.asarray(x)*(HIGH-LOW)).tolist()))
            trial = target/f'trial-{count:03d}'
            trial.mkdir(parents=True,exist_ok=True)
            (trial/'parameters.json').write_text(json.dumps(params,indent=2)+'\n')
            scores,exits,reports = [],0,[]
            for seed in seeds:
                output = trial/f'seed-{seed}'
                output.mkdir(exist_ok=True)
                with (output/'run.log').open('w') as log:
                    code = subprocess.run([sys.executable,str(ROOT/'harness/evaluate.py'),'--scene','maze',
                        '--seed',str(seed),'--seconds','320','--parameters',str(trial/'parameters.json'),
                        '--output',str(output)],stdout=log,stderr=log).returncode
                if code:
                    scores.append(-10.)
                    continue
                r = json.loads((output/'report.json').read_text())
                reports.append(r)
                with np.load(output/'trace.npz') as trace:
                    pos = trace['qpos'][:,:2]
                cells = np.floor((pos+.625)/1.25).astype(int)
                cells = cells[np.all((cells>=0)&(cells<3),axis=1)]
                coverage = len(np.unique(cells,axis=0))/9 if len(cells) else 0.
                score = (2.+.35*(1-r['seconds']/320)) if r['exited'] else .6*coverage
                if r['wrong_exit']:
                    score -= .3
                if r['reason'] or r['warnings']:
                    score -= 2.
                score -= .001*max(0.,r['touch_metrics']['peak_hand_force_n']-30.)
                scores.append(score)
                exits += int(r['exited'])
            average = float(np.mean(scores))
            summary = dict(trial=count,score=average,exits=exits,seeds=seeds,parameters=params,
                           seconds=[r['seconds'] for r in reports],warnings=[len(r['warnings']) for r in reports])
            with (target/'trials.jsonl').open('a') as f:
                f.write(json.dumps(summary)+'\n')
            if average > best:
                best = average
                (target/'best.json').write_text(json.dumps(summary,indent=2)+'\n')
            print(json.dumps(dict(trial=count,score=round(average,3),exits=exits,best=round(best,3))),flush=True)
            objectives.append(-average)
            count += 1
        es.tell(candidates,objectives)
    print('Optimization complete',target/'best.json',flush=True)


if __name__=='__main__':
    main()
