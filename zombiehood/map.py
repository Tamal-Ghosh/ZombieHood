"""Grid generation and map validation.

Placement rules (applied on every generation, so each refresh differs):
  * agents start in 3 different rows
  * hearts (+1 life) never lie in an agent's row
  * zombies occupy 5 different rows AND 5 different columns, never in an
    agent's row
  * one coin per row; the high coins (8/10/12) go next to zombies and far
    from the agents, the cheap ones (3/5) go anywhere else
  * nothing ever shares a cell
"""
import random
from collections import deque
from dataclasses import dataclass, field

DIRS = {"UP": (-1, 0), "DOWN": (1, 0), "LEFT": (0, -1), "RIGHT": (0, 1)}

def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

@dataclass
class MapData:
    rows: int
    cols: int
    goal: tuple
    starts: list
    zombies: list
    coins: dict
    hearts: set
    obstacles: set = field(default_factory=set)
    seed: int = 0

def reachable(m, start):
    """Cells reachable from ``start`` ignoring zombies (they can be shot)."""
    seen, q = {start}, deque([start])
    while q:
        r, c = q.popleft()
        for dr, dc in DIRS.values():
            n = (r + dr, c + dc)
            if (0 <= n[0] < m.rows and 0 <= n[1] < m.cols
                    and n not in m.obstacles and n not in seen):
                seen.add(n)
                q.append(n)
    return seen

def validate_map(m, cfg):
    """Return a list of rule violations (empty list == valid map)."""
    errs = []
    spots = (list(m.starts) + list(m.zombies) + list(m.coins) +
             list(m.hearts) + list(m.obstacles) + [m.goal])
    if len(spots) != len(set(spots)):
        errs.append("two objects share a cell")
    for p in spots:
        if not (0 <= p[0] < m.rows and 0 <= p[1] < m.cols):
            errs.append("object outside the grid %s" % (p,))
    arows = [s[0] for s in m.starts]
    if len(set(arows)) != len(arows):
        errs.append("agents must start in different rows")
    zr = [z[0] for z in m.zombies]
    zc = [z[1] for z in m.zombies]
    if len(set(zr)) != len(zr) or len(set(zc)) != len(zc):
        errs.append("zombies must have distinct rows and columns")
    if any(r in arows for r in zr):
        errs.append("a zombie shares a row with an agent")
    if any(h[0] in arows for h in m.hearts):
        errs.append("a heart shares a row with an agent")
    crow = [c[0] for c in m.coins]
    if len(set(crow)) != len(crow):
        errs.append("more than one coin in a row")
    if len(cfg.coin_values) >= m.rows and len(set(crow)) != m.rows:
        errs.append("every row needs a coin")
    for s in m.starts:
        reach = reachable(m, s)
        for p in [m.goal] + list(m.coins) + list(m.hearts):
            if p not in reach:
                errs.append("%s unreachable from start %s" % (p, s))
                break
    return errs
