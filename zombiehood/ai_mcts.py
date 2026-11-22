"""Tamal - Monte Carlo Tree Search (Intent-based MCTS).

Overcomes the grid horizon problem by branching over high-level strategic
intents (target coins, hearts, combat positions, clashes, and goal escape).
Playouts simulate multi-step movements of all three survivors to project
who secures resources and reaches the endgame first, backpropagating UCT
rewards to select the optimal move.
"""
import math
import time
import heapq
from itertools import count
from ai import Agent, danger_cost, fallback_move
from map import DIRS, manhattan


def mcts_path(state, idx, goals, penalty):
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


class MCTSNode:
    __slots__ = ("action", "target", "visits", "total_reward")

    def __init__(self, action, target):
        self.action = action
        self.target = target
        self.visits = 0
        self.total_reward = 0.0


class MCTSAgent(Agent):
    name = "MCTS"

    def __init__(self, iterations=60, time_limit=0.03, rollout_steps=12,
                 exploration=1.414, seed=None):
        super().__init__(seed)
        self.iterations = iterations
        self.time_limit = time_limit
        self.rollout_steps = rollout_steps
        self.c = exploration

    def _generate_intent_candidates(self, state, idx):
        s = state.survivors[idx]
        cfg = state.cfg
        penalty = danger_cost(s)
        candidates = []  # list of (action, target_cell, base_weight)

        unlocked = state.goal_unlocked_for(s)
        in_range = bool(state.zombies_in_range(s.pos))
        can_attack = in_range and s.coins >= cfg.coins_to_kill

        # 1. Unlocked goal
        if unlocked:
            for act_name, (dr, dc) in DIRS.items():
                if (s.pos[0] + dr, s.pos[1] + dc) == state.goal:
                    return [MCTSNode(act_name, state.goal)]
            res = mcts_path(state, idx, {state.goal}, 8 if s.lives > 1 else penalty)
            if res:
                path, cost = res
                candidates.append((step_to_action(s.pos, path[0]), state.goal, 500.0))

        # 2. Attack in place
        if can_attack:
            candidates.append(("ATTACK", s.pos, 300.0))

        # 3. Zombie hunting positions
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
                res = mcts_path(state, idx, firing_spots, penalty)
                if res:
                    path, cost = res
                    candidates.append((step_to_action(s.pos, path[0]), path[-1], 250.0 / (cost + 1)))

        # 4. Top coins
        scored_coins = []
        for cell, val in state.coins.items():
            dist = manhattan(s.pos, cell)
            urgency = 2.4 if s.coins < cfg.coins_to_kill else 0.8
            if s.lives <= 1 and state.is_adjacent_to_zombie(cell):
                urgency *= 0.15
            scored_coins.append((val * urgency / (dist + 1), cell))
        scored_coins.sort(reverse=True)

        for _, cell in scored_coins[:5]:  # top 5 most promising coins
            res = mcts_path(state, idx, {cell}, penalty)
            if res:
                path, cost = res
                candidates.append((step_to_action(s.pos, path[0]), cell, 100.0 / (cost + 1)))

        # 5. Heart pickups
        if s.lives < s.max_lives:
            h_weight = 180.0 if s.lives <= 1 else 80.0
            for cell in list(state.hearts)[:3]:
                res = mcts_path(state, idx, {cell}, penalty)
                if res:
                    path, cost = res
                    candidates.append((step_to_action(s.pos, path[0]), cell, h_weight / (cost + 1)))

        # 6. Clash opportunism (stealing coins from weaker agent)
        for other in state.survivors:
            if other.idx != idx and other.alive and s.coins > other.coins and other.coins >= 4:
                res = mcts_path(state, idx, {other.pos}, penalty)
                if res:
                    path, cost = res
                    candidates.append((step_to_action(s.pos, path[0]), other.pos, 120.0 / (cost + 1)))

        # Deduplicate actions, keeping nodes
        node_map = {}
        for act, tgt, weight in candidates:
            if act not in node_map:
                node_map[act] = MCTSNode(act, tgt)
        return list(node_map.values())

    def _simulate_rollout(self, state, me, candidate_node):
        """Simulate playout starting from candidate_node's target."""
        st = state.copy()
        if st.apply(me, candidate_node.action) is None:
            return 0.0

        s = st.survivors[me]
        cfg = st.cfg

        # Playout simulation
        for _ in range(self.rollout_steps):
            if st.over or not s.alive:
                break
            cur = st.turn
            if cur == me:
                # Steer toward candidate target if still relevant
                tgt = candidate_node.target
                if tgt and (tgt in st.coins or tgt in st.zombie_cells or tgt == st.goal or tgt in st.hearts):
                    unlocked = st.goal_unlocked_for(s)
                    if unlocked and tgt != st.goal:
                        tgt = st.goal
                    # Quick step toward tgt
                    best_a, min_d = "WAIT", 1e9
                    for a, (dr, dc) in DIRS.items():
                        nxt = (s.pos[0] + dr, s.pos[1] + dc)
                        if st.can_enter(s, nxt):
                            d = manhattan(nxt, tgt)
                            if st.is_adjacent_to_zombie(nxt) and nxt != tgt:
                                d += 15
                            if nxt in st.blue_cells:
                                d += 8 if s.coins > 0 else 2
                            elif nxt in st.pink_cells:
                                d += 16 if s.coins > 0 else 4
                            if d < min_d:
                                min_d, best_a = d, a
                    st.apply(cur, best_a)
                else:
                    st.apply(cur, "WAIT")
            else:
                # Fast opponent step toward their best goal
                opp = st.survivors[cur]
                if opp.alive:
                    if st.coins:
                        c_target = min(st.coins.keys(), key=lambda c: manhattan(opp.pos, c))
                        best_a, min_d = "WAIT", 1e9
                        for a, (dr, dc) in DIRS.items():
                            nxt = (opp.pos[0] + dr, opp.pos[1] + dc)
                            if st.can_enter(opp, nxt):
                                d = manhattan(nxt, c_target)
                                if d < min_d:
                                    min_d, best_a = d, a
                        st.apply(cur, best_a)
                    else:
                        st.apply(cur, "WAIT")

        # Evaluate final state
        r = s.coins * 2.5 + 40 * s.lives + 60 * s.kills
        r -= 0.3 * sum(o.coins for o in st.survivors if o.idx != me)
        if st.winner == me:
            r += 1200
        elif st.winner is not None:
            r -= 500
        if not s.alive:
            r -= 600
        elif st.goal_unlocked_for(s):
            r += 800 - 35 * manhattan(s.pos, st.goal)
        elif s.coins >= cfg.coins_to_kill and st.zombie_cells:
            dz = min(manhattan(s.pos, z) for z in st.zombie_cells)
            r += 140 - 10 * max(0, dz - cfg.attack_range)
        elif st.coins:
            dc = min(manhattan(s.pos, c) for c in st.coins)
            r += 70 - 4.0 * dc

        return min(1.0, max(0.0, (r + 500) / 1800.0))

    def choose_action(self, state, idx):
        s = state.survivors[idx]
        cfg = state.cfg
        legal = state.legal_actions(idx)
        if not legal:
            return "WAIT"
        if len(legal) == 1:
            return legal[0]

        self.pos_history.append(s.pos)
        self.pos_history = self.pos_history[-10:]
        is_oscillating = len(self.pos_history) >= 3 and self.pos_history[-3] == s.pos
        prev_pos = self.pos_history[-2] if len(self.pos_history) >= 2 else None

        nodes = self._generate_intent_candidates(state, idx)
        if not nodes:
            return fallback_move(state, idx, self.rng, self.pos_history)
        if len(nodes) == 1:
            act = nodes[0].action
            if is_oscillating and prev_pos and step_to_action(s.pos, prev_pos) == act:
                return fallback_move(state, idx, self.rng, self.pos_history)
            return act

        # Run MCTS rollouts across candidate nodes
        deadline = time.perf_counter() + self.time_limit
        total_visits = 0

        # Initial warm-up rollout for each node
        for node in nodes:
            reward = self._simulate_rollout(state, idx, node)
            node.visits += 1
            node.total_reward += reward
            total_visits += 1

        # UCT selection and simulation loop
        for it in range(self.iterations):
            if it % 5 == 0 and time.perf_counter() > deadline:
                break
            log_n = math.log(total_visits)
            selected = max(nodes, key=lambda n: (n.total_reward / n.visits)
                                                + self.c * math.sqrt(log_n / n.visits))
            reward = self._simulate_rollout(state, idx, selected)
            selected.visits += 1
            selected.total_reward += reward
            total_visits += 1

        # Choose the node with highest visit count (avoiding reversal if oscillating)
        best_node = max(nodes, key=lambda n: n.visits)
        if is_oscillating and prev_pos:
            reversal_act = step_to_action(s.pos, prev_pos)
            non_rev = [n for n in nodes if n.action != reversal_act]
            if non_rev:
                best_node = max(non_rev, key=lambda n: n.visits)

        if best_node.action == "WAIT":
            return fallback_move(state, idx, self.rng, self.pos_history)
        return best_node.action
