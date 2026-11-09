import json
import numpy as np
from harness.map_baseline import route
from harness.scenes import make


def test_privileged_map_route_uses_only_open_cell_boundaries():
    for seed in range(10):
        width=1.25
        spec=json.loads(make('maze',seed,width=width).with_suffix('.json').read_text())
        points=[np.zeros(2),*route(spec,width)]
        walls=np.asarray(spec['walls'])
        for a,b in zip(points[:-2],points[1:-1]):
            assert np.sum(abs((b-a)/width))==1
            midpoint=(a+b)/2
            assert not any(np.all(midpoint>=w.min(axis=0)-1e-6) and np.all(midpoint<=w.max(axis=0)+1e-6) for w in walls)
        assert points[-1][0]>spec['exit']['value']
