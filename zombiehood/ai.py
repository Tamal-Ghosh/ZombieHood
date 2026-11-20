"""AI decision-making interface (independent of pygame).

An agent receives a *copy* of the game state and the index of the survivor
it controls, and returns one action string.  Any algorithm can be plugged in
by subclassing ``Agent`` and registering it in ``create_agent``.
"""
import random
from map import DIRS, manhattan


class Agent:
    """Base class for everything that can drive a survivor."""
    name = "agent"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.pos_history = []

    def choose_action(self, state, idx):          # pragma: no cover
        raise NotImplementedError


class HumanAgent(Agent):
    """Keyboard player.  The UI stores the next key press in ``pending``;
    the human is subject to exactly the same rules as the AIs."""
    name = "human"

    def __init__(self):
        super().__init__(0)
        self.pending = None

    def choose_action(self, state, idx):
        action, self.pending = self.pending, None
        return action


def danger_cost(s):
    """How much a single step next to a zombie 'costs' (in path steps)."""
    return 60 if s.lives <= 1 or s.coins > 0 else 18


def fallback_move(state, idx, rng, pos_history=None):
    """Safe directional step to keep the agent moving rather than freezing."""
    s = state.survivors[idx]
    legal_moves = [a for a in state.legal_actions(idx) if a in DIRS]
    if not legal_moves:
        return "WAIT"

    # Avoid immediate suicide if 1 life
    safe_moves = [a for a in legal_moves if not (s.lives <= 1 and state.is_adjacent_to_zombie((s.pos[0] + DIRS[a][0], s.pos[1] + DIRS[a][1])))]
    pool = safe_moves if safe_moves else legal_moves

    # Avoid immediate reversal if oscillating
    if pos_history and len(pos_history) >= 2:
        prev = pos_history[-2]
        non_reversal = [a for a in pool if (s.pos[0] + DIRS[a][0], s.pos[1] + DIRS[a][1]) != prev]
        if non_reversal:
            pool = non_reversal

    # Avoid penalty border cells (blue / pink) unless no other choice
    clean_moves = [a for a in pool if (s.pos[0] + DIRS[a][0], s.pos[1] + DIRS[a][1]) not in state.blue_cells
                   and (s.pos[0] + DIRS[a][0], s.pos[1] + DIRS[a][1]) not in state.pink_cells]
    if clean_moves:
        pool = clean_moves

    # Steer toward closest available coin, heart, or unlocked goal
    targets = list(state.coins.keys())
    if s.lives < s.max_lives and state.hearts:
        targets.extend(state.hearts)
    if state.goal_unlocked_for(s):
        targets.append(state.goal)

    if targets:
        best_a = min(pool, key=lambda a: min(manhattan((s.pos[0] + DIRS[a][0], s.pos[1] + DIRS[a][1]), t) for t in targets))
        return best_a

    return rng.choice(pool)


def greedy_action(state, idx, rng, eps=0.2):
    """Cheap, reasonable default policy (used by MCTS rollouts and as a
    fall-back): shoot when possible, otherwise walk toward the nearest
    valuable thing while avoiding zombie-adjacent cells."""
    s = state.survivors[idx]
    legal = state.legal_actions(idx)
    if not legal:
        return "WAIT"
    moves = [a for a in legal if a in DIRS]
    if rng.random() < eps:
        safe = [a for a in moves if not state.is_adjacent_to_zombie(
            (s.pos[0] + DIRS[a][0], s.pos[1] + DIRS[a][1]))]
        pool = safe or moves
        return rng.choice(pool) if pool else "WAIT"
    unlocked = state.goal_unlocked_for(s)
    if "ATTACK" in legal and not (unlocked and not state.is_adjacent_to_zombie(s.pos)):
        return "ATTACK"
    rng_a = state.cfg.attack_range
    targets = []                                   # (priority, cell)
    if unlocked:
        targets = [(-5000, state.goal)]
    elif s.coins >= state.cfg.coins_to_kill:
        for z in state.zombie_cells:
            targets.append((manhattan(s.pos, z) - rng_a - 12, z))
    for cell, v in state.coins.items():
        weight = 1.8 if s.coins < state.cfg.coins_to_kill else 0.6
        targets.append((manhattan(s.pos, cell) - v * weight, cell))
    if s.lives < s.max_lives:
        for cell in state.hearts:
            targets.append((manhattan(s.pos, cell) - (14 if s.lives <= 1 else 5), cell))
    if not targets or not moves:
        return "WAIT"
    goal_cell = min(targets)[1]
    best, best_val = [], 1e9
    for a in moves:
        n = (s.pos[0] + DIRS[a][0], s.pos[1] + DIRS[a][1])
        val = manhattan(n, goal_cell)
        if goal_cell in state.zombie_cells:        # stop at shooting range
            val = abs(val - rng_a) if val >= 2 else val + 5
        if state.is_adjacent_to_zombie(n) and n != goal_cell:
            val += 25 if s.coins > 0 else 10
        if n in state.blue_cells:
            val += 8 if s.coins > 0 else 2
        elif n in state.pink_cells:
            val += 16 if s.coins > 0 else 4
        if val < best_val:
            best, best_val = [a], val
        elif val == best_val:
            best.append(a)
    return rng.choice(best)


def create_agent(spec, idx, seed, cfg):
    """Factory: build the AI named in the agent spec."""
    algo = spec["algo"]
    s = (seed or 0) * 31 + idx
    if algo == "minimax":
        from ai_minimax import MinimaxAgent
        return MinimaxAgent(depth=cfg.minimax_depth, seed=s)
    if algo == "mcts":
        from ai_mcts import MCTSAgent
        return MCTSAgent(iterations=cfg.mcts_iterations,
                         time_limit=cfg.mcts_time_limit, seed=s)
    if algo == "fuzzy":
        from ai_fuzzy import FuzzyAgent
        return FuzzyAgent(seed=s)
    if algo == "astar":
        from ai_astar import AStarAgent
        return AStarAgent(seed=s)
    if algo == "human":
        return HumanAgent()
    raise ValueError("unknown algorithm %r" % algo)
