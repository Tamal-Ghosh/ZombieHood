"""Nijhum - A* search.

Every turn Nijhum builds a list of goals (coins, hearts, safe firing cells
for each zombie, or the exit once it is unlocked), runs A* to each one with
a path cost that makes zombie-adjacent cells very expensive, and walks the
first step toward the goal with the best value / path-cost ratio.
"""
import heapq
from itertools import count
from ai import Agent, danger_cost, greedy_action, fallback_move
from map import DIRS, manhattan


def astar(state, idx, goals, penalty):
    """A* from the survivor's cell to the nearest cell in ``goals``.

    Step cost = 1, plus ``penalty`` for entering a cell next to a living
    zombie.  The heuristic (min Manhattan distance to a goal) never
    overestimates, so the returned path is optimal.
    Returns (path_without_start, cost) or None.
    """
    s = state.survivors[idx]
    start = s.pos
    goals = set(goals)
    if not goals:
        return None

    def h(p):
        return min(manhattan(p, g) for g in goals)

    tie = count()
    open_heap = [(h(start), next(tie), 0, start)]
    best_g = {start: 0}
    parent = {}
    while open_heap:
        _, _, g, cur = heapq.heappop(open_heap)
        if g > best_g.get(cur, 1e9):
            continue
        if cur in goals and cur != start:
            path = []
            while cur != start:
                path.append(cur)
                cur = parent[cur]
            return path[::-1], g
        for dr, dc in DIRS.values():
            nxt = (cur[0] + dr, cur[1] + dc)
            if cur == start:
                if not state.can_enter(s, nxt):
                    continue
            else:
                if (not state.in_bounds(nxt) or nxt in state.obstacles
                        or nxt in state.zombie_cells or nxt in state.buried_cells):
                    continue
                if nxt == state.goal and not state.goal_unlocked_for(s):
                    continue
            border_cost = 0
            if nxt in state.blue_cells:
                border_cost = 10 if s.coins > 0 else 3
            elif nxt in state.pink_cells:
                border_cost = 20 if s.coins > 0 else 5
            ng = g + 1 + (penalty if state.is_adjacent_to_zombie(nxt) else 0) + border_cost
            if ng < best_g.get(nxt, 1e9):
                best_g[nxt] = ng
                parent[nxt] = cur
                heapq.heappush(open_heap, (ng + h(nxt), next(tie), ng, nxt))
    return None


def step_to_action(src, dst):
    for name, (dr, dc) in DIRS.items():
        if (src[0] + dr, src[1] + dc) == dst:
            return name
    return "WAIT"


class AStarAgent(Agent):
    name = "A*"

    def choose_action(self, state, idx):
        s = state.survivors[idx]
        cfg = state.cfg
        penalty = danger_cost(s)
        unlocked = state.goal_unlocked_for(s)
        in_range = bool(state.zombies_in_range(s.pos))
        can_attack = in_range and s.coins >= cfg.coins_to_kill

        if unlocked:
            for act_name, (dr, dc) in DIRS.items():
                if (s.pos[0] + dr, s.pos[1] + dc) == state.goal:
                    return act_name
            res = astar(state, idx, {state.goal}, 8 if s.lives > 1 else penalty)
            if res:
                path, cost = res
                if can_attack and cost > len(path):
                    return "ATTACK"
                return step_to_action(s.pos, path[0])
            return "ATTACK" if can_attack else greedy_action(state, idx, self.rng, 0)

        if can_attack:                     # free 20 points + unlock progress
            return "ATTACK"

        self.pos_history.append(s.pos)
        self.pos_history = self.pos_history[-10:]
        is_oscillating = len(self.pos_history) >= 3 and self.pos_history[-3] == s.pos
        prev_pos = self.pos_history[-2] if len(self.pos_history) >= 2 else None

        candidates = []                    # (utility, first_step)
        for cell, v in state.coins.items():
            res = astar(state, idx, {cell}, penalty)
            if res:
                path, cost = res
                weight = 1.8 if s.coins < cfg.coins_to_kill else 1.0
                if s.lives <= 1 and state.is_adjacent_to_zombie(cell):
                    weight *= 0.15
                candidates.append(((v * cfg.coin_multiplier * weight + 2) / (cost + 1), path[0]))
        if s.lives < s.max_lives:
            hv = 80 if s.lives <= 1 else 15
            for cell in state.hearts:
                res = astar(state, idx, {cell}, penalty)
                if res:
                    path, cost = res
                    candidates.append((hv / (cost + 1), path[0]))
        lo = 2 if cfg.attack_range >= 2 else 1
        if s.coins >= cfg.coins_to_kill:
            for z in state.zombies:
                if not z.alive:
                    continue
                firing = set()
                for dr in range(-cfg.attack_range, cfg.attack_range + 1):
                    for dc in range(-cfg.attack_range, cfg.attack_range + 1):
                        p = (z.pos[0] + dr, z.pos[1] + dc)
                        d = manhattan(p, z.pos)
                        if (lo <= d <= cfg.attack_range and state.in_bounds(p)
                                and p not in state.obstacles
                                and p not in state.zombie_cells
                                and (lo == 1 or not state.is_adjacent_to_zombie(p))):
                            firing.add(p)
                if s.pos in firing and can_attack:
                    return "ATTACK"
                res = astar(state, idx, firing, penalty)
                if res:
                    path, cost = res
                    need = max(0, cfg.kills_to_unlock - s.kills)
                    candidates.append((((cfg.zombie_kill_score + 10 * (need > 0)) + 15) / (cost + 1),
                                       path[0]))
        if not candidates:
            return fallback_move(state, idx, self.rng, self.pos_history)

        adjusted = []
        for util, step in candidates:
            if is_oscillating and step == prev_pos:
                util *= 0.1
            if step in state.pink_cells:
                util *= 0.2 if s.coins > 0 else 0.5
            elif step in state.blue_cells:
                util *= 0.4 if s.coins > 0 else 0.7
            adjusted.append((util, step))

        best = max(c[0] for c in adjusted)
        pool = [c[1] for c in adjusted if c[0] >= best - 1e-9]
        act = step_to_action(s.pos, self.rng.choice(pool))
        if act == "WAIT":
            return fallback_move(state, idx, self.rng, self.pos_history)
        return act
