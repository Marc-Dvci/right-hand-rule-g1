import json
from pathlib import Path
import numpy as np
from harness.maze_catalog import catalog,legacy_ids,EDGES,VERTICES


def test_catalog_is_complete_by_independent_matrix_tree_count():
    index={v:i for i,v in enumerate(VERTICES)}
    laplacian=np.zeros((9,9))
    for a,b in EDGES:
        i,j=index[a],index[b]
        laplacian[i,i]+=1
        laplacian[j,j]+=1
        laplacian[i,j]-=1
        laplacian[j,i]-=1
    count=round(np.linalg.det(laplacian[:-1,:-1]))
    assert count==192==len(set(catalog()))
    assert all(len(tree)==8 for tree in catalog())


def test_new_geometry_holdout_excludes_every_legacy_topology():
    root=Path(__file__).resolve().parents[1]
    protocol=json.loads((root/'review/evaluation_v2_protocol.json').read_text())
    held=set(protocol['holdout_topologies'])
    development=set(protocol['development_topologies'])
    assert len(held)==100 and len(development)==92
    assert held|development==set(range(192)) and not held&development
    assert set(legacy_ids())<=development and len(legacy_ids())==14
