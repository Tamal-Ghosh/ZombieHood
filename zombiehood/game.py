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
    def __init__(self, cfg=None):
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


    # --------------------------------------------------------- log / fx
    def _say(self, text, color=(200, 205, 200)):
        self.log.append((text, color))
        self.log = self.log[-40:]

    def _fx(self, kind, ttl=2000, **kw):
        self.effects.append(dict(kind=kind, ttl=ttl, total=ttl, **kw))


