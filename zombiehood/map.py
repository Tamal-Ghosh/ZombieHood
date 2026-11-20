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

def generate_map(cfg, seed=None):
    """Create a valid random map.  The same seed always gives the same map."""
    if seed is None:
        seed = cfg.seed
    if seed is None:
        seed = random.randrange(1, 2 ** 31 - 1)
    rng = random.Random(seed)
    for _ in range(500):
        m = _attempt(cfg, rng, seed)
        if m is not None and not validate_map(m, cfg):
            return m
    raise RuntimeError("could not build a valid map with this configuration")

def _attempt(cfg, rng, seed):
    rows, cols = cfg.rows, cfg.cols
    n_agents = len(cfg.agents)
    occupied = {cfg.goal}

    agent_rows = rng.sample(range(rows), n_agents)
    starts = []
    for r in agent_rows:
        options = [c for c in range(cols) if (r, c) not in occupied]
        if not options:
            return None
        cell = (r, rng.choice(options))
        starts.append(cell)
        occupied.add(cell)

    heart_cells = [(r, c) for r in range(rows) if r not in agent_rows
                   for c in range(cols) if (r, c) not in occupied]
    if len(heart_cells) < cfg.heart_count:
        return None
    hearts = set(rng.sample(heart_cells, cfg.heart_count))
    occupied |= hearts

    zrows = [r for r in range(rows) if r not in agent_rows]
    rng.shuffle(zrows)

    def place(start, used_cols, picked):
        if len(picked) == cfg.zombie_count:
            return picked
        for a in range(start, len(zrows)):
            r = zrows[a]
            opts = [c for c in range(cols)
                    if c not in used_cols and (r, c) not in occupied]
            rng.shuffle(opts)
            for c in opts:
                used_cols.add(c)
                res = place(a + 1, used_cols, picked + [(r, c)])
                if res:
                    return res
                used_cols.discard(c)
        return None

    zombies = place(0, set(), [])
    if zombies is None:
        return None
    occupied |= set(zombies)

    def score(cell):
        return (min(chebyshev(cell, a) for a in starts)
                - 1.5 * min(chebyshev(cell, z) for z in zombies))

    values = sorted(cfg.coin_values, reverse=True)
    infos = []
    for r in range(rows):
        opts = sorted(((r, c) for c in range(cols) if (r, c) not in occupied),
                      key=score, reverse=True)
        if opts:
            infos.append((score(opts[0]) + rng.random() * 3, opts))
    infos.sort(key=lambda x: -x[0])
    coins = {}
    for value, (_, opts) in zip(values, infos):
        pool = opts[:3] if value >= cfg.high_coin_value else opts
        cell = rng.choice(pool)
        coins[cell] = value
        occupied.add(cell)

    free = [(r, c) for r in range(rows) for c in range(cols)
            if (r, c) not in occupied]
    obs_count = cfg.obstacle_count
    if isinstance(obs_count, (tuple, list)):
        obs_count = rng.randint(obs_count[0], obs_count[1])
    elif obs_count == 9:
        obs_count = rng.randint(8, 10)
    elif obs_count == 6:
        obs_count = rng.randint(5, 6)
    elif obs_count == 3:
        obs_count = rng.randint(3, 4)
    obstacles = set(rng.sample(free, obs_count)) \
        if obs_count <= len(free) else set()

    return MapData(rows, cols, cfg.goal, starts, zombies, coins, hearts,
                   obstacles, seed)

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
