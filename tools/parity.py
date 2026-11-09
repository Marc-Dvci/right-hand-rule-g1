"""Compare both NumPy exports with ONNX Runtime on recorded histories."""
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import onnxruntime as ort
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from policy.networks import Network

paths = sorted((ROOT/'evidence/development').glob('*/trace.npz'))
features, sources = [], []
for path in paths:
    with np.load(path, allow_pickle=False) as z:
        if 'features' not in z:
            continue
        features.append(z['features'])
        sources.append(dict(path=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), rows=len(z['features'])))
x = np.concatenate(features)
if len(x) < 10000:
    raise RuntimeError(f'Need at least 10,000 recorded observations; have {len(x)}')
rng = np.random.default_rng(261109)
x = x[rng.choice(len(x), 10000, replace=False)]
options = ort.SessionOptions()
options.intra_op_num_threads = 1
options.inter_op_num_threads = 1
rows = []
full = {'features':x}
for name in ('walker','balance'):
    path = ROOT/'policy/models'/f'{name}.onnx'
    session = ort.InferenceSession(str(path), sess_options=options, providers=['CPUExecutionProvider'])
    net = Network(path.with_suffix('.npz'))
    expected = np.concatenate([session.run(None, {session.get_inputs()[0].name: row[None]})[0] for row in x])
    full[name+'_expected'] = expected
    actual = np.concatenate([net(row) for row in x])
    error = float(np.max(abs(expected-actual)))
    print(name, 'single-observation maximum absolute error', error, flush=True)
    rows.append(dict(model=name, maximum_absolute_error=error, passed=error<=1e-4,
                     onnx_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                     numpy_sha256=hashlib.sha256(path.with_suffix('.npz').read_bytes()).hexdigest()))
    fixture = ROOT/'tests/fixtures'
    fixture.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(fixture/f'{name}-parity.npz', features=x[:64], expected=expected[:64])
report = dict(observations=10000, source_observations=sum(s['rows'] for s in sources),
              sampling_seed=261109, onnxruntime=ort.__version__, numpy=np.__version__, models=rows, sources=sources)
target = ROOT/'evidence/walker/numpy-parity.json'
target.parent.mkdir(parents=True,exist_ok=True)
np.savez_compressed(target.parent/'parity-10000.npz',**full)
report['full_fixture_sha256'] = hashlib.sha256((target.parent/'parity-10000.npz').read_bytes()).hexdigest()
target.write_text(json.dumps(report, indent=2)+'\n')
if not all(r['passed'] for r in rows):
    raise RuntimeError('NumPy parity gate failed')
