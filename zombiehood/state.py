"""The rules engine.  Pure Python - no pygame - and cheap to copy, so every
AI can simulate "what if" futures on a ``GameState.copy()``.

Rules in one place
------------------
* One action per turn, survivors act in order (Tamal, Progga, Nijhum).
* Actions: UP / DOWN / LEFT / RIGHT (no diagonals), ATTACK, WAIT.
* Locked cells: a living zombie's cell and the goal (until unlocked for
  that survivor) cannot be entered.  Obstacles and living survivors block too.
* Entering a coin cell collects it (score += value * multiplier).
* Entering a heart cell gives +1 life (only if below the maximum).
* Agent clashes compare both coin balances, regardless of who moves first.
  The richer agent takes all loser coins; the loser loses exactly one life.
  Equal coin balances block the move. Life is not transferred to the winner.
* COMBAT: after a move, every living zombie orthogonally adjacent to the new
  cell hits the survivor once for ``zombie_damage``.  Attack / wait never
  trigger damage, and a zombie cannot hit twice in one action.
* ATTACK kills the nearest living zombie within ``attack_range`` (Manhattan),
  +20 score, +1 kill.
* The goal unlocks for a survivor at ``kills_to_unlock`` kills (or for all
  once no zombie is left alive, so a match can always finish).
* Reaching the unlocked goal alive wins.  All dead -> defeat.  After
  ``max_rounds`` the best living score wins (time up).
"""
from collections import deque
import random
from map import DIRS, manhattan
from survivor import Survivor
from zombie import Zombie, adjacent_alive, in_range_alive

MOVES = tuple(DIRS)
ACTIONS = MOVES + ("ATTACK", "WAIT")


class GameState:
    def __init__(self, cfg, m, survivors, zombies, blue_cells=None, pink_cells=None):
        self.cfg = cfg
        self.rows, self.cols = m.rows, m.cols
        self.goal = m.goal
        self.obstacles = frozenset(m.obstacles)
        self.coins = dict(m.coins)
        self.hearts = set(m.hearts)
        self.survivors = survivors
        self.zombies = zombies
        self.zombie_cells = {z.pos for z in zombies if z.alive}
        self.buried_cells = set()   # cells where defeated survivors died, blocked for others
        diff = getattr(cfg, "difficulty", "hard").lower()
        if blue_cells is not None:
            self.blue_cells = set(blue_cells)
        elif diff == "easy":
            self.blue_cells = set()
        else:
            self.blue_cells = {survivors[0].start} if survivors else set()

        if pink_cells is not None:
            self.pink_cells = set(pink_cells)
        elif diff in ("easy", "medium"):
            self.pink_cells = set()
        else:
            self.pink_cells = {survivors[1].start} if len(survivors) > 1 else set()
        self.timed_match = False  # Live games use an elapsed-time deadline instead of round/draw limits.
        self.turn = 0          # index of the survivor who acts next
        self.round = 0
        self.over = False
        self.winner = None     # index of winning survivor, or None
        self.reason = ""       # goal / all_dead / timeup
        self.initial_coins = sum(m.coins.values())
        self.initial_zombies = len(m.zombies)

    @classmethod
    def from_map(cls, cfg, m):
        survivors = [
            Survivor(idx=i, name=sp["name"], algo=sp["algo"], label=sp["label"],
                     color=sp["color"], female=sp["female"], start=m.starts[i],
                     pos=m.starts[i], lives=cfg.start_lives,
                     max_lives=cfg.max_lives)
            for i, sp in enumerate(cfg.agents)]
        zombies = [Zombie(i, p) for i, p in enumerate(m.zombies)]
        blue_cells = {m.starts[0]} if cfg.blue_cell_count and m.starts else set()
        pink_cells = {m.starts[1]} if cfg.pink_cell_count and len(m.starts)>1 else set()
        blocked = (set(m.obstacles) | set(m.zombies) | set(m.coins) | set(m.hearts)
                   | set(m.starts) | {m.goal})
        available = [(r,c) for r in range(m.rows) for c in range(m.cols)
                     if (r,c) not in blocked]
        rng = random.Random(m.seed + 9173)
        rng.shuffle(available)
        needed = cfg.blue_cell_count-len(blue_cells)+cfg.pink_cell_count-len(pink_cells)
        if len(available)<needed:
            raise ValueError("Not enough empty cells for blue and pink penalty tiles")
        while len(blue_cells)<cfg.blue_cell_count:
            blue_cells.add(available.pop())
        while len(pink_cells)<cfg.pink_cell_count:
            pink_cells.add(available.pop())
        return cls(cfg, m, survivors, zombies, blue_cells=blue_cells, pink_cells=pink_cells)

    # ------------------------------------------------------------ copying
    def copy(self):
        c = GameState.__new__(GameState)
        c.__dict__.update(self.__dict__)          # immutable/shared fields
        c.coins = dict(self.coins)
        c.hearts = set(self.hearts)
        c.survivors = [s.copy() for s in self.survivors]
        c.zombies = [z.copy() for z in self.zombies]
        c.zombie_cells = set(self.zombie_cells)
        c.buried_cells = set(self.buried_cells)
        c.blue_cells = set(self.blue_cells)
        c.pink_cells = set(self.pink_cells)
        return c

    # ------------------------------------------------------------ queries
    def goal_unlocked_for(self, s):
        return s.kills >= self.cfg.kills_to_unlock

    def in_bounds(self, pos):
        return 0 <= pos[0] < self.rows and 0 <= pos[1] < self.cols

    def can_enter(self, s, pos):
        if not self.in_bounds(pos):
            return False
        if pos in self.obstacles or pos in self.zombie_cells or pos in self.buried_cells:
            return False
        if pos == self.goal and not self.goal_unlocked_for(s):
            return False
        for o in self.survivors:
            if o.alive and o.idx != s.idx and o.pos == pos:
                # Unequal balances resolve a clash; equal balances block the move.
                if s.coins == o.coins:
                    return False
        return True

    def find_flee_cell(self, survivor, from_pos):
        """Find a safe neighboring cell for a defeated survivor to flee to."""
        r, c = survivor.pos
        opts = []
        for dr, dc in DIRS.values():
            n = (r + dr, c + dc)
            if (self.in_bounds(n) and n not in self.obstacles
                    and n not in self.zombie_cells and n not in self.buried_cells):
                if n == self.goal and not self.goal_unlocked_for(survivor):
                    continue
                # The attacking agent vacates from_pos on a winning move.
                if any(o.alive and o.idx != survivor.idx and o.pos == n and o.pos != from_pos
                       for o in self.survivors):
                    continue
                safe = not self.is_adjacent_to_zombie(n)
                opts.append((1 if safe else 0, -manhattan(n, from_pos), n))
        if opts:
            opts.sort(reverse=True)
            return opts[0][2]
        return survivor.pos

    def zombies_in_range(self, pos):
        return in_range_alive(self.zombies, pos, self.cfg.attack_range)

    def is_adjacent_to_zombie(self, pos):
        r, c = pos
        zc = self.zombie_cells
        return ((r - 1, c) in zc or (r + 1, c) in zc or
                (r, c - 1) in zc or (r, c + 1) in zc)

    def legal_actions(self, idx):
        s = self.survivors[idx]
        if self.over or not s.alive:
            return []
        r, c = s.pos
        acts = [n for n, (dr, dc) in DIRS.items()
                if self.can_enter(s, (r + dr, c + dc))]
        if self.zombies_in_range(s.pos) and s.coins >= self.cfg.coins_to_kill:
            acts.append("ATTACK")
        acts.append("WAIT")
        return acts

    def alive_survivors(self):
        return [s for s in self.survivors if s.alive]

    def can_survivor_win(self, s):
        """Check if survivor ``s`` has any theoretical possibility to unlock and reach the goal."""
        if s.reached_goal:
            return True
        if not s.alive:
            return False

        # If map never had enough coins or zombies to unlock goal (e.g. synthetic test), don't declare unwinnable
        if self.initial_coins < self.cfg.coins_to_kill and self.initial_zombies < self.cfg.kills_to_unlock:
            return True

        # Total coins in existence that s could possibly obtain
        total_coins_possible = sum(self.coins.values()) + sum(o.coins for o in self.survivors if o.alive)
        living_zombies = [z for z in self.zombies if z.alive]

        # Can s unlock the goal?
        if not self.goal_unlocked_for(s):
            kills_needed = self.cfg.kills_to_unlock - s.kills
            if len(living_zombies) < kills_needed and self.initial_zombies >= self.cfg.kills_to_unlock:
                return False
            if total_coins_possible < self.cfg.coins_to_kill and self.initial_coins >= self.cfg.coins_to_kill:
                return False

        # Can s physically reach the goal?
        # Obstacles and buried cells are impassable walls.
        # Living zombie cells are impassable walls unless they can be killed.
        can_kill = (total_coins_possible >= self.cfg.coins_to_kill and len(living_zombies) > 0)
        impassable = set(self.obstacles) | set(self.buried_cells)
        if not can_kill:
            impassable |= set(self.zombie_cells)

        if self.goal in impassable:
            return False

        q = deque([s.pos])
        seen = {s.pos}
        while q:
            curr = q.popleft()
            if curr == self.goal:
                return True
            for dr, dc in DIRS.values():
                nxt = (curr[0] + dr, curr[1] + dc)
                if (0 <= nxt[0] < self.rows and 0 <= nxt[1] < self.cols
                        and nxt not in impassable and nxt not in seen):
                    seen.add(nxt)
                    q.append(nxt)
        return False

    def can_any_survivor_win(self):
        alive = self.alive_survivors()
        if not alive:
            return False
        return any(self.can_survivor_win(s) for s in alive)

    # ------------------------------------------------------------ acting
    def apply(self, idx, action):
        """Perform ``action`` for survivor ``idx``.

        Returns a list of event tuples, or ``None`` if the action is illegal
        (nothing changes and the turn is not consumed).
        """
        if self.over or idx != self.turn:
            return None
        s = self.survivors[idx]
        if not s.alive:
            return None
        cfg, ev = self.cfg, []

        if action in DIRS:
            dr, dc = DIRS[action]
            new = (s.pos[0] + dr, s.pos[1] + dc)
            if not self.can_enter(s, new):
                return None
            s.facing = action

            # Face-to-face clash: check if opponent occupies `new`
            opponent = next((o for o in self.survivors if o.alive and o.idx != s.idx and o.pos == new), None)
            if opponent is not None and s.coins < opponent.coins:
                # A poorer initiator loses too: defender stays put, initiator retreats
                # to its current cell (or dies there), with no destination pickups.
                stolen = s.coins
                opponent.coins += stolen
                opponent.score += stolen
                s.coins = 0
                s.lose_life(1)
                ev.append(("clash", opponent.idx, idx, stolen, s.pos))
                if s.alive:
                    ev.append(("flee", idx, s.pos))
                else:
                    ev.append(("death", idx, s.pos))
                    self.buried_cells.add(s.pos)
                self._advance()
                return ev
            if opponent is not None:
                stolen = opponent.coins
                s.coins += stolen
                s.score += stolen
                opponent.coins = 0
                opponent.lose_life(1)
                ev.append(("clash", idx, opponent.idx, stolen, new))

                if opponent.alive:
                    flee_to = self.find_flee_cell(opponent, s.pos)
                    opponent.pos = flee_to
                    ev.append(("flee", opponent.idx, flee_to))
                else:
                    ev.append(("death", opponent.idx, new))
                    self.buried_cells.add(new)

            s.pos = new
            ev.append(("move", idx, new))
            value = self.coins.pop(new, None)
            if value is not None:
                gain = value * cfg.coin_multiplier
                s.score += gain
                s.coins += value
                ev.append(("coin", idx, value, gain, new))
            if new in self.hearts and s.gain_life():
                self.hearts.discard(new)
                ev.append(("heart", idx, new))
            if new in self.blue_cells:
                penalty = 1
                lost = min(s.coins, penalty)
                s.coins -= lost
                s.score = max(0, s.score - lost)
                ev.append(("penalty", idx, penalty, lost, new, "blue"))
            elif new in self.pink_cells:
                penalty = 2
                lost = min(s.coins, penalty)
                s.coins -= lost
                s.score = max(0, s.score - lost)
                ev.append(("penalty", idx, penalty, lost, new, "pink"))
            adj = adjacent_alive(self.zombies, new)
            if adj:
                s.lose_life(len(adj) * cfg.zombie_damage)
                # Zombie attacks remove health only; coins and score are retained.
                ev.append(("hit", idx, len(adj), new, 0))
                if not s.alive:
                    ev.append(("death", idx, new))
                    self.buried_cells.add(new)
            if s.alive and new == self.goal and self.goal_unlocked_for(s):
                s.reached_goal = True
                self.over, self.winner, self.reason = True, idx, "goal"
                ev.append(("goal", idx))

        elif action == "ATTACK":
            if s.coins < cfg.coins_to_kill:
                return None
            targets = self.zombies_in_range(s.pos)
            if not targets:
                return None
            z = min(targets, key=lambda t: (manhattan(t.pos, s.pos), t.id))
            was_open = self.goal_unlocked_for(s)
            z.kill()
            self.zombie_cells.discard(z.pos)
            s.kills += 1
            s.score += cfg.zombie_kill_score
            ev.append(("kill", idx, z.id, z.pos))
            if not was_open and self.goal_unlocked_for(s):
                ev.append(("unlock", idx))

        elif action == "WAIT":
            ev.append(("wait", idx))
        else:
            return None

        self._advance()
        return ev

    # ------------------------------------------------------------ turns
    def _advance(self):
        if self.over:
            return
        if not any(s.alive for s in self.survivors):
            self.over, self.reason = True, "all_dead"
            return
        if not self.timed_match and not self.can_any_survivor_win():
            self.over, self.winner, self.reason = True, None, "draw"
            return
        n, i = len(self.survivors), self.turn
        while True:
            i = (i + 1) % n
            if i == 0:
                self.round += 1
            if self.survivors[i].alive:
                break
        self.turn = i
        if not self.timed_match and self.round >= self.cfg.max_rounds:
            alive = self.alive_survivors()
            if not alive:
                self.over, self.winner, self.reason = True, None, "all_dead"
                return
            max_score = max(s.score for s in alive)
            top = [s for s in alive if s.score == max_score]
            if len(top) > 1:
                self.over, self.winner, self.reason = True, None, "draw"
            else:
                best = top[0]
                self.over, self.winner, self.reason = True, best.idx, "timeup"
