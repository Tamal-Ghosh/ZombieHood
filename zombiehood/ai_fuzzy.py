"""Progga - Fuzzy Logic AI (Mamdani Fuzzy Inference System).

Implements a Mamdani Fuzzy Inference System (FIS) with linguistic variables,
fuzzy membership functions (trapezoidal and triangular), rule evaluation,
and Centroid Defuzzification to dynamically rank goals (coins, zombies,
clashes, hearts, exit) and execute safe navigation.
"""
from ai import Agent, danger_cost, fallback_move
from map import DIRS, manhattan
import heapq
from itertools import count

def trimf(x, a, b, c):
    """Triangular membership function."""
    if x <= a or x >= c:
        return 0.0
    if x == b:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (c - x) / (c - b)

def trapmf(x, a, b, c, d):
    """Trapezoidal membership function."""
    if x <= a or x >= d:
        return 0.0
    if b <= x <= c:
        return 1.0
    if a < x < b:
        return (x - a) / (b - a)
    return (d - x) / (d - c)

def fuzzy_path(state, idx, goals, penalty):
    s = state.survivors[idx]
    start = s.pos
    goals = set(goals)
    if not goals:
        return None
    tie = count()
    open_heap = [(0, next(tie), 0, start)]
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
                h_val = min(manhattan(nxt, goal) for goal in goals)
                heapq.heappush(open_heap, (ng + h_val, next(tie), ng, nxt))
    return None

def step_to_action(src, dst):
    for name, (dr, dc) in DIRS.items():
        if (src[0] + dr, src[1] + dc) == dst:
            return name
    return "WAIT"

class FuzzyAgent(Agent):
    name = "Fuzzy Logic"

    CENTROIDS = {
        "LOW": 20.0,
        "MEDIUM": 50.0,
        "HIGH": 80.0,
        "VERY_HIGH": 100.0,
        "CRITICAL": 120.0,
    }

    def _defuzzify(self, rule_outputs):
        """Centroid Defuzzification over aggregated fuzzy outputs.
        rule_outputs: dict of consequent label -> max firing strength (alpha)
        """
        numerator = 0.0
        denominator = 0.0
        for label, strength in rule_outputs.items():
            if strength > 0.0:
                c = self.CENTROIDS[label]
                numerator += c * strength
                denominator += strength
        if denominator == 0.0:
            return 0.0
        return numerator / denominator

    def evaluate_coin_utility(self, val, dist, coins, coins_to_kill=20):
        """Fuzzy rule evaluation for collecting a coin."""

        val_med = trimf(val, 2, 4, 6)
        val_high = trapmf(val, 5, 7, 10, 10)

        dist_close = trapmf(dist, 0, 0, 3, 6)
        dist_med = trimf(dist, 4, 8, 12)
        dist_far = trapmf(dist, 9, 14, 30, 30)

        need_urgent = trapmf(coins, 0, 0, int(coins_to_kill * 0.6), coins_to_kill)
        need_satisfied = trapmf(coins, coins_to_kill - 1, coins_to_kill, 100, 100)

        rules = {
            "CRITICAL": min(need_urgent, dist_close),
            "VERY_HIGH": max(min(need_urgent, val_high, max(dist_close, dist_med)),
                             min(val_high, dist_close)),
            "HIGH": min(need_urgent, max(val_med, dist_med)),
            "MEDIUM": max(dist_med, min(val_med, dist_close)),
            "LOW": min(need_satisfied, dist_far),
        }
        return self._defuzzify(rules)

    def evaluate_clash_utility(self, coin_diff, dist):
        """Fuzzy rules for face-to-face clash opportunities (stealing coins)."""

        diff_huge = trapmf(coin_diff, 8, 15, 100, 100)
        diff_moderate = trimf(coin_diff, 1, 6, 12)
        diff_negative = trapmf(coin_diff, -100, -100, 0, 0)

        dist_close = trapmf(dist, 0, 0, 2, 4)
        dist_med = trimf(dist, 3, 5, 8)

        if diff_negative > 0.8:
            return -100.0

        rules = {
            "CRITICAL": min(diff_huge, dist_close),
            "VERY_HIGH": max(min(diff_huge, dist_med), min(diff_moderate, dist_close)),
            "HIGH": min(diff_moderate, dist_med),
            "MEDIUM": 0.0,
            "LOW": 0.0,
        }
        return self._defuzzify(rules)

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
            res = fuzzy_path(state, idx, {state.goal}, 8 if s.lives > 1 else penalty)
            if res:
                path, cost = res
                if can_attack and cost > len(path):
                    return "ATTACK"
                return step_to_action(s.pos, path[0])
            return "ATTACK" if can_attack else "WAIT"

        if can_attack:
            return "ATTACK"

        self.pos_history.append(s.pos)
        self.pos_history = self.pos_history[-10:]
        is_oscillating = len(self.pos_history) >= 3 and self.pos_history[-3] == s.pos
        prev_pos = self.pos_history[-2] if len(self.pos_history) >= 2 else None

        candidates = []

        for cell, val in state.coins.items():
            res = fuzzy_path(state, idx, {cell}, penalty)
            if res:
                path, cost = res
                fuzzy_score = self.evaluate_coin_utility(val, cost, s.coins, cfg.coins_to_kill)
                if s.lives <= 1 and state.is_adjacent_to_zombie(cell):
                    fuzzy_score *= 0.15
                candidates.append((fuzzy_score / (cost + 1), path[0]))

        if s.coins >= cfg.coins_to_kill and state.zombie_cells:
            firing_spots = set()
            for z in state.zombie_cells:
                for dr in range(-cfg.attack_range, cfg.attack_range + 1):
                    for dc in range(-cfg.attack_range, cfg.attack_range + 1):
                        p = (z[0] + dr, z[1] + dc)
                        if (manhattan(p, z) <= cfg.attack_range
                                and state.in_bounds(p)
                                and not state.is_adjacent_to_zombie(p)
                                and p not in state.zombie_cells):
                            firing_spots.add(p)
            if firing_spots:
                res = fuzzy_path(state, idx, firing_spots, penalty)
                if res:
                    path, cost = res

                    candidates.append(((130.0 / (cost + 1)), path[0]))

        for other in state.survivors:
            if other.idx != idx and other.alive and other.coins > 4:
                diff = s.coins - other.coins
                dist = manhattan(s.pos, other.pos)
                clash_score = self.evaluate_clash_utility(diff, dist)
                if clash_score > 30.0:
                    res = fuzzy_path(state, idx, {other.pos}, penalty)
                    if res:
                        path, cost = res
                        candidates.append(((clash_score * 1.2 / (cost + 1)), path[0]))

        if s.lives < s.max_lives:

            life_critical = trapmf(s.lives, 0, 1, 1, 2)
            for cell in state.hearts:
                res = fuzzy_path(state, idx, {cell}, penalty)
                if res:
                    path, cost = res
                    heart_score = 150.0 if life_critical > 0.5 else 45.0
                    candidates.append(((heart_score / (cost + 1)), path[0]))

        if not candidates:
            return fallback_move(state, idx, self.rng, self.pos_history)

        adjusted = []
        for score, step in candidates:
            if is_oscillating and step == prev_pos:
                score *= 0.1
            if step in state.pink_cells:
                score *= 0.2 if s.coins > 0 else 0.5
            elif step in state.blue_cells:
                score *= 0.4 if s.coins > 0 else 0.7
            adjusted.append((score, step))
        adjusted.sort(key=lambda c: c[0], reverse=True)
        act = step_to_action(s.pos, adjusted[0][1])
        if act == "WAIT":
            return fallback_move(state, idx, self.rng, self.pos_history)
        return act
