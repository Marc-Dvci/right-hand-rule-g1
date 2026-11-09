"""All 192 spanning-tree mazes on a 3x3 grid, with exact topology identities."""
from functools import lru_cache
from itertools import combinations

VERTICES=tuple((x,y) for y in range(3) for x in range(3))
EDGES=tuple(((x,y),(x+dx,y+dy)) for x,y in VERTICES for dx,dy in ((1,0),(0,1)) if x+dx<3 and y+dy<3)


@lru_cache(maxsize=1)
def catalog():
    trees=[]
    for edges in combinations(range(len(EDGES)),8):
        reached={(0,0)}
        while True:
            before=len(reached)
            for index in edges:
                a,b=EDGES[index]
                if a in reached or b in reached:
                    reached.update((a,b))
            if len(reached)==before:
                break
        if len(reached)==9:
            trees.append(edges)
    assert len(trees)==192
    return tuple(trees)


def passages(index):
    if not isinstance(index,int) or not 0<=index<len(catalog()):
        raise ValueError('Topology ID must be an integer in [0,191]')
    return {frozenset(EDGES[e]) for e in catalog()[index]}


def wall_segments(index,width=1.25):
    tree=passages(index)
    walls=[]
    for y in range(3):
        for x in range(3):
            left,right=(x-.5)*width,(x+.5)*width
            bottom,top=(y-.5)*width,(y+.5)*width
            if y==0:
                walls.append(((left,bottom),(right,bottom)))
            if x==0 and y!=0:
                walls.append(((left,bottom),(left,top)))
            if y==2 or frozenset(((x,y),(x,y+1))) not in tree:
                walls.append(((left,top),(right,top)))
            if (x,y)!=(2,2) and (x==2 or frozenset(((x,y),(x+1,y))) not in tree):
                walls.append(((right,bottom),(right,top)))
    return walls


@lru_cache(maxsize=1)
def legacy_ids():
    """Exhaustively enumerate every topology reachable by the old DFS generator."""
    edge_lookup={frozenset(edge):i for i,edge in enumerate(EDGES)}
    tree_lookup={frozenset(tree):i for i,tree in enumerate(catalog())}
    found=set()
    def visit(visited,stack,edges):
        stack=stack.copy()
        while stack:
            x,y=stack[-1]
            options=[(x+dx,y+dy) for dx,dy in ((1,0),(0,1),(-1,0),(0,-1))
                     if 0<=x+dx<3 and 0<=y+dy<3 and (x+dx,y+dy) not in visited]
            if options:
                break
            stack.pop()
        if not stack:
            found.add(tree_lookup[frozenset(edges)])
            return
        for cell in options:
            edge=edge_lookup[frozenset((stack[-1],cell))]
            visit(visited|{cell},stack+[cell],edges|{edge})
    visit({(0,0)},[(0,0)],set())
    return tuple(sorted(found))
