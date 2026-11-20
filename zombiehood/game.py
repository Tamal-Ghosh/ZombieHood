"""Game loop and state management (no drawing in here).

``Game`` owns the match: it builds the map, creates one agent per survivor,
asks whoever's turn it is for an action, applies it through the rules engine
and keeps the event log / visual effects that the UI reads.
"""
from enum import Enum
from ai import HumanAgent, create_agent
from config import Config, make_config
from map import generate_map, validate_map
from state import GameState


class Phase(Enum):
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"
    OVER = "over"


class Game:
    def __init__(self, cfg=None, audio=None):
        self.audio = audio
        self.cfg = cfg or Config()
        self.phase = Phase.MENU
        self.state = None
        self.agents = []
        self.human_idx = None
        self.seed = None
        self.log = []            # [(text, color)]
        self.effects = []        # short-lived visual effects for the UI
        self.outcome = None      # dict filled in when the match ends
        self.flash = ""          # one-line hint ("Blocked move!")
        self.delay_ms = self.cfg.step_delay_ms
        self._timer = 0
        self.goal_delay_ms = 0

    # --------------------------------------------------------- lifecycle
    def start_match(self, human_idx=None, seed=None, difficulty=None):
        """Build a fresh map + agents and begin playing."""
        if difficulty is not None:
            self.cfg = make_config(difficulty, seed=self.cfg.seed)
            self.delay_ms = self.cfg.step_delay_ms
        self.seed = seed if seed is not None else self.cfg.seed
        m = generate_map(self.cfg, self.seed)
        assert not validate_map(m, self.cfg)
        self.seed = m.seed
        self.state = GameState.from_map(self.cfg, m)
        self.human_idx = human_idx
        self.agents = []
        for i, spec in enumerate(self.cfg.agents):
            if i == human_idx:
                self.agents.append(HumanAgent())
                self.state.survivors[i].human = True
            else:
                self.agents.append(create_agent(spec, i, self.seed, self.cfg))
        self.log, self.effects, self.outcome, self.flash = [], [], None, ""
        self._timer = 0
        self.goal_delay_ms = 0
        self.phase = Phase.PLAYING
        diff_str = getattr(self.cfg, "difficulty", "hard").upper()
        self._say("👁️ 🕸️ Match started [%s %dx%d] - seed %d" % (diff_str, self.cfg.rows, self.cfg.cols, self.seed), (180, 220, 180))

    def restart(self):
        """Same map, same mode."""
        self.start_match(self.human_idx, self.seed)

    def new_map(self):
        # seed=None -> cfg.seed if one is configured, else a fresh random map
        self.start_match(self.human_idx, None)

    def to_menu(self):
        self.phase = Phase.MENU

    def toggle_pause(self):
        if self.phase == Phase.PLAYING:
            self.phase = Phase.PAUSED
        elif self.phase == Phase.PAUSED:
            self.phase = Phase.PLAYING

    def change_speed(self, faster):
        self.delay_ms = max(40, self.delay_ms - 60) if faster else min(1200, self.delay_ms + 60)

    # --------------------------------------------------------- input
    def human_input(self, action):
        """Queue an action for the human survivor (applied on their turn)."""
        if self.phase != Phase.PLAYING or self.human_idx is None or self.goal_delay_ms > 0:
            return
        agent = self.agents[self.human_idx]
        if self.state.turn == self.human_idx:
            agent.pending = action

    # --------------------------------------------------------- stepping
    def update(self, dt_ms):
        for fx in self.effects:
            fx["ttl"] -= dt_ms
        self.effects = [fx for fx in self.effects if fx["ttl"] > 0]
        if self.phase != Phase.PLAYING:
            return
        if self.goal_delay_ms > 0:
            self.goal_delay_ms -= dt_ms
            if self.goal_delay_ms <= 0:
                self.goal_delay_ms = 0
                self._finish()
            return
        st = self.state
        if isinstance(self.agents[st.turn], HumanAgent):
            if self.agents[st.turn].pending is not None:
                self.step()
            return
        self._timer += dt_ms
        if self._timer >= self.delay_ms:
            self._timer = 0
            self.step()

    def step(self):
        """Let the current survivor act once.  Returns True if a turn passed."""
        st = self.state
        if st.over:
            if self.goal_delay_ms <= 0:
                self._finish()
            return False
        idx = st.turn
        agent = self.agents[idx]
        if isinstance(agent, HumanAgent):
            action = agent.choose_action(st, idx)
            events = st.apply(idx, action) if action else None
            if events is None:
                self.flash = "Blocked - choose another move"
                return False
        else:
            action = agent.choose_action(st.copy(), idx)
            events = st.apply(idx, action)
            if events is None:          # an AI must never break the rules
                events = st.apply(idx, "WAIT")
        self.flash = ""
        self._record(events)
        if st.over:
            if st.reason == "goal":
                self.goal_delay_ms = 4000
                self._say("Winner reached goal! Game Over in 4s...", (120, 255, 140))
            else:
                self._finish()
        return True

    # --------------------------------------------------------- log / fx
    def _say(self, text, color=(200, 205, 200)):
        self.log.append((text, color))
        self.log = self.log[-40:]

    def _fx(self, kind, ttl=2000, **kw):
        self.effects.append(dict(kind=kind, ttl=ttl, total=ttl, **kw))

    def _record(self, events):
        st = self.state
        for e in events:
            s = st.survivors[e[1]]
            col = s.color
            kind = e[0]
            if self.audio is not None:
                self.audio.event(kind)
            if kind == "coin":
                self._say("🪙 💰 %s grabbed a %d coin (+%d)" % (s.name, e[2], e[3]), (255, 218, 80))
                self._fx("float", pos=e[4], text="+%d" % e[3], color=(255, 215, 80))
            elif kind == "heart":
                self._say("💉 ❤️ %s found a heart (+1 life)" % s.name, (255, 110, 140))
                self._fx("float", pos=e[2], text="+1 life", color=(255, 90, 110))
            elif kind == "penalty":
                penalty, lost, pos, col_name = e[2], e[3], e[4], e[5]
                p_col = (74, 163, 255) if col_name == "blue" else (255, 123, 181)
                icon = "⚡" if col_name == "blue" else "☣️"
                if lost > 0:
                    self._say("%s ⚠️ %s entered %s border (-%d coin%s)" % (icon, s.name, col_name, lost, "s" if lost > 1 else ""), p_col)
                    self._fx("float", pos=pos, text="-%d coin%s" % (lost, "s" if lost > 1 else ""), color=p_col, ttl=2000)
                else:
                    self._say("%s ⚠️ %s entered %s border (no coins to lose)" % (icon, s.name, col_name), p_col)
                    self._fx("float", pos=pos, text="-%d coins" % penalty, color=p_col, ttl=2000)
            elif kind == "clash":
                winner = st.survivors[e[1]]
                loser = st.survivors[e[2]]
                stolen = e[3]
                self._say("⚔️ 🩸 %s defeated %s! (-1 HP, stole %d coins)" % (winner.name, loser.name, stolen), (255, 175, 75))
                self._fx("float", pos=e[4], text="DEFEATED! -1 HP -%d coins" % stolen, color=(255, 80, 40))
            elif kind == "flee":
                loser = st.survivors[e[1]]
                self._say("🏃 💨 %s fled with 0 coins!" % loser.name, (240, 195, 90))
                self._fx("float", pos=e[2], text="FLED! (0 coins)", color=(220, 180, 80))
            elif kind == "hit":
                lost = e[4] if len(e) > 4 else 0
                if lost > 0:
                    self._say("🧟 🩸 %s was bitten! Lost %d coins & 1 life!" % (s.name, lost), (255, 110, 110))
                    self._fx("float", pos=e[3], text="-1 HP -%d coins" % lost, color=(255, 60, 60))
                else:
                    self._say("🧟 🩸 %s was bitten! (lives: %d)" % (s.name, s.lives), (255, 120, 120))
                    self._fx("float", pos=e[3], text="-%d HP" % e[2], color=(255, 60, 60))
            elif kind == "death":
                self._say("💀 ⚰️ %s has died" % s.name, (255, 105, 105))
            elif kind == "kill":
                self._say("💥 🎯 %s shot a zombie (+%d)" % (s.name, st.cfg.zombie_kill_score), (120, 255, 150))
                self._fx("shot", src=s.pos, dst=e[3], color=col, ttl=350)
            elif kind == "unlock":
                self._say("🗝️ 🔓 %s unlocked the goal!" % s.name, (120, 255, 150))
            elif kind == "goal":
                self._say("🏆 🚪 %s reached the goal! Escaped alive!" % s.name, (120, 255, 150))
                self._fx("float", pos=s.pos, text="ESCAPED!", color=(120, 255, 140), ttl=4000)

    def _finish(self):
        st = self.state
        self.phase = Phase.OVER
        self.goal_delay_ms = 0
        ranking = sorted(st.survivors, key=lambda s: (-s.score, -s.lives))
        w = st.survivors[st.winner] if st.winner is not None else None
        human = st.survivors[self.human_idx] if self.human_idx is not None else None
        if st.reason == "all_dead":
            if human is None and len(st.survivors) > 1 and ranking[0].score == ranking[1].score:
                title, detail = "GAME IS DRAW", "Game is Draw - Every survivor died with tied scores."
            else:
                title, detail = "DEFEAT", "Every survivor died before reaching the goal."
        elif st.reason == "goal":
            title, detail = "GAME OVER", "%s (%s) reached the unlocked goal alive." % (w.name, w.label)
        elif st.reason == "draw":
            alive = st.alive_survivors()
            if alive and not st.can_any_survivor_win():
                title = "GAME IS DRAW"
                detail = "Game is Draw - No way to win! Goal cannot be unlocked or reached."
            elif alive:
                max_score = max(s.score for s in alive)
                top = [s for s in alive if s.score == max_score]
                names = " & ".join(s.name for s in top)
                title = "GAME IS DRAW"
                detail = "Game is Draw - %s tied with %d points." % (names, max_score)
            else:
                title = "GAME IS DRAW"
                detail = "Game is Draw - Match ended in a tie."
        else:
            title = "TIME UP"
            detail = "Round limit reached - %s leads with %d points." % (w.name if w else "Nobody", w.score if w else 0)
        if human is not None:
            if w is human:
                title = "VICTORY"
                detail = "You escaped through the goal with %d points!" % human.score
            elif st.reason == "draw":
                alive = st.alive_survivors()
                if alive and not st.can_any_survivor_win():
                    title = "GAME IS DRAW"
                    detail = "Game is Draw - No way to win! Goal cannot be unlocked or reached."
                elif human in alive and human.score == max(s.score for s in alive):
                    title = "GAME IS DRAW"
                    detail = "Game is Draw - You tied for the lead with %d points!" % human.score
                else:
                    title = "DEFEAT"
                    detail = "Game is Draw between AIs - You lost with %d points." % human.score
            elif not human.alive:
                title, detail = "DEFEAT", "You died - %s" % detail
            else:
                title = "DEFEAT"
                detail = "%s beat you to it. %s" % (w.name if w else "Nobody", "")
        if "DRAW" in title:
            self._say("Game is Draw!", (255, 210, 63))
            self._fx("float", pos=(st.rows // 2, st.cols // 2), text="GAME IS DRAW", color=(255, 210, 63), ttl=4000)
        self.outcome = dict(title=title, detail=detail, winner=w, ranking=ranking,
                            reason=st.reason)
