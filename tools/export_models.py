"""Export the pinned GR00T MLP weights; ONNX is a build-time dependency only."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import onnx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    for name in ('walk', 'balance'):
        source = ROOT / 'policy/models' / ('walker.onnx' if name == 'walk' else 'balance.onnx')
        graph = onnx.load(str(source))
        arrays = {v.name: onnx.numpy_helper.to_array(v) for v in graph.graph.initializer}
        target = source.with_suffix('.npz')
        np.savez_compressed(target, **arrays)
        print(name, [(n.op_type, list(n.input), list(n.output)) for n in graph.graph.node], flush=True)
        print('Arrays', [(k, v.shape) for k, v in arrays.items()], flush=True)


if __name__ == '__main__':
    main()
