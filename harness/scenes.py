"""Deterministic static scenes. Layouts are never given to the controller."""
from pathlib import Path
import json
import random
import xml.etree.ElementTree as ET
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def write_scene(name, walls, exit_spec=None):
    root = ET.parse(ROOT/'scene/flat.xml').getroot()
    world = root.find('worldbody')
    for i, (a, b) in enumerate(walls):
        center = [(a[k]+b[k])/2 for k in range(2)]
        size = [max(.045, abs(a[k]-b[k])/2+.045) for k in range(2)]
        ET.SubElement(world, 'geom', name=f'wall_{i:03d}', type='box',
                      pos=f'{center[0]} {center[1]} .65', size=f'{size[0]} {size[1]} .65',
                      rgba='.70 .75 .79 1', friction='.35 .005 .0001', condim='3')
    scene = ROOT/'scene'/f'{name}.xml'
    with tempfile.NamedTemporaryFile(mode='w',suffix='.xml',dir=scene.parent,delete=False) as temp:
        ET.ElementTree(root).write(temp, encoding='unicode')
        temp_path = temp.name
    os.replace(temp_path,scene)
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',dir=scene.parent,delete=False) as temp:
        temp.write(json.dumps(dict(walls=walls, exit=exit_spec), indent=2)+'\n')
        temp_path = temp.name
    os.replace(temp_path,scene.with_suffix('.json'))
    return scene


def make(kind='wall', seed=0, size=3, width=1.25):
    w = width
    if kind == 'flat':
        return ROOT/'scene/flat.xml'
    if kind == 'wall':
        return write_scene('wall', [((-1, -.55), (7, -.55))], dict(axis=0, value=6., sign=1))
    if kind == 'outer':
        return write_scene('outer', [((-1, -.55), (2., -.55)), ((2., -.55), (2., -4.))], dict(axis=1, value=-3., sign=-1))
    if kind == 'inner':
        return write_scene('inner', [((-1, -.55), (2., -.55)), ((2., -.55), (2., 4.))], dict(axis=1, value=3., sign=1))
    if kind != 'maze':
        raise ValueError(kind)
    rng = random.Random(seed)
    visited, stack, passages = {(0, 0)}, [(0, 0)], set()
    while stack:
        x, y = stack[-1]
        options = [(x+dx, y+dy) for dx, dy in ((1,0),(0,1),(-1,0),(0,-1))
                   if 0 <= x+dx < size and 0 <= y+dy < size and (x+dx,y+dy) not in visited]
        if not options:
            stack.pop()
            continue
        cell = rng.choice(options)
        passages.add(frozenset(((x, y), cell)))
        visited.add(cell)
        stack.append(cell)
    walls = []
    for y in range(size):
        for x in range(size):
            left, right = (x-.5)*w, (x+.5)*w
            bottom, top = (y-.5)*w, (y+.5)*w
            if y == 0:
                walls.append(((left,bottom),(right,bottom)))
            if x == 0 and y != 0:
                walls.append(((left,bottom),(left,top)))
            if y == size-1 or frozenset(((x,y),(x,y+1))) not in passages:
                walls.append(((left,top),(right,top)))
            if not (x == size-1 and y == size-1) and (x == size-1 or frozenset(((x,y),(x+1,y))) not in passages):
                walls.append(((right,bottom),(right,top)))
    return write_scene(f'maze-{seed}-w{width:.3f}', walls, dict(axis=0, value=(size-.5)*w+.25, sign=1,
                                               min_y=(size-1.5)*w, max_y=(size-.5)*w))


if __name__ == '__main__':
    for kind in ('wall', 'inner', 'outer', 'maze'):
        print(make(kind))
