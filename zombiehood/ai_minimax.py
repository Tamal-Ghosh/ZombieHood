# GLOBAL COMMIT: 18
# OWNER: Nijhum
# COMMIT MESSAGE: Add minimax root selection and repetition avoidance
# REPOSITORY DESTINATION: zombiehood/ai_minimax.py
# Cumulative snapshot: replace destination contents with this file.
# Partial stage; follow GLOBAL_SERIAL.md before running.

"""Nijhum - Heuristic Minimax (paranoid, with alpha-beta pruning).

Three survivors act in turn, so Nijhum treats the two opponents as one
adversary that tries to minimise Nijhum's heuristic value ("paranoid"
minimax).  Search depth is a number of plies (one ply = one survivor's
action); leaves are scored by ``evaluate``.
"""
from ai import Agent
from map import manhattan

INF = float("inf")


class MinimaxAgent(Agent):
    name = "Minimax"

    def __init__(self, depth=4, seed=None):
        super().__init__(seed)
        self.depth = depth
        self._progress = None

    # ------------------------------------------------------------ heuristic
    def evaluate(self, st, me):
        s = st.survivors[me]
        cfg = st.cfg
        if not s.alive:
            return -3000 + s.coins
        if st.over and st.winner == me:
            return 5000 + s.coins
        if st.over and st.winner is not None:
            return -2500 + s.coins
        others = [o for o in st.survivors if o.idx != me]
        v = s.coins + 45 * s.lives + 12 * s.kills
        v -= 0.35 * sum(o.coins for o in others)

        if st.goal_unlocked_for(s):
            v += 4000 - 40 * manhattan(s.pos, st.goal)
        elif s.coins >= cfg.coins_to_kill and st.zombie_cells:
            dz = min(manhattan(s.pos, z) for z in st.zombie_cells)
            v -= 4 * max(0, dz - cfg.attack_range)

        if st.coins:                       # pull toward valuable, close coins
            coin_weight = 3.5 if s.coins < cfg.coins_to_kill else 1.5
            v += max(val * coin_weight / (manhattan(s.pos, c) + 1)
                     for c, val in st.coins.items())
        if st.hearts and s.lives < s.max_lives:
            v += 25.0 / (min(manhattan(s.pos, h) for h in st.hearts) + 1)
        for o in others:                   # opponents racing to the exit
            if o.alive and st.goal_unlocked_for(o):
                v -= max(0, 24 - 2 * manhattan(o.pos, st.goal))
        return v

    # ------------------------------------------------------------ search
    @staticmethod
    def _ordered(actions):
        order = {"ATTACK": 0, "UP": 1, "DOWN": 1, "LEFT": 1, "RIGHT": 1, "WAIT": 2}
        return sorted(actions, key=lambda a: order[a])

    def _search(self, st, depth, alpha, beta, me):
        if st.over or depth == 0 or not st.survivors[me].alive:
            return self.evaluate(st, me)
        cur = st.turn
        maximizing = cur == me
        best = -INF if maximizing else INF
        for a in self._ordered(st.legal_actions(cur)):
            child = st.copy()
            if child.apply(cur, a) is None:
                continue
            val = self._search(child, depth - 1, alpha, beta, me)
            if maximizing:
                best = max(best, val)
                alpha = max(alpha, best)
            else:
                best = min(best, val)
                beta = min(beta, best)
            if beta <= alpha:
                break
        return best

    def choose_action(self, state, idx):
        survivor = state.survivors[idx]
        # Forget old visits after a pickup, combat or a changed map objective.
        progress = (survivor.coins, survivor.lives, survivor.kills,
                    len(state.coins), len(state.hearts), len(state.zombie_cells))
        if progress != self._progress:
            self.pos_history = []
            self._progress = progress
        self.pos_history.append(survivor.pos)
        self.pos_history = self.pos_history[-16:]
        best_val, best_actions = -INF, []
        for a in self._ordered(state.legal_actions(idx)):
            child = state.copy()
            if child.apply(idx, a) is None:
                continue
            # Search each root action with a full window. A pruned upper bound
            # must not be treated as an exact tie and randomly selected.
            val = self._search(child, max(0, self.depth - 1), -INF, INF, idx)
            after = child.survivors[idx]
            productive = (after.coins != survivor.coins or
                          after.lives != survivor.lives or
                          after.kills != survivor.kills or after.reached_goal)
            if after.alive and not child.over and not productive:
                val -= 18 * self.pos_history.count(after.pos)
                if len(self.pos_history) > 1 and after.pos == self.pos_history[-2]:
                    val -= 12
            if a == "WAIT":
                val -= 2.0
            if val > best_val + 1e-9:
                best_val, best_actions = val, [a]
            elif abs(val - best_val) <= 1e-9:
                best_actions.append(a)
        return self.rng.choice(best_actions) if best_actions else "WAIT"
