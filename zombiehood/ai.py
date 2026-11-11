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








