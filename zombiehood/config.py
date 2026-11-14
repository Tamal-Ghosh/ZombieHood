"""Central, tweakable settings for ZombieHood - The Last Rise.

Every gameplay rule that can be tuned lives in ``Config``.  Tests and the
headless simulator build their own ``Config`` instances, so nothing in the
game logic reads module-level globals.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

AGENTS = (
    {"name": "Tamal", "algo": "mcts", "label": "Monte Carlo Tree Search",
     "color": (74, 163, 255), "female": False},
    {"name": "Progga", "algo": "fuzzy", "label": "Fuzzy Logic (FIS)",
     "color": (255, 123, 181), "female": True},
    {"name": "Nijhum", "algo": "minimax", "label": "Minimax + Alpha-Beta",
     "color": (255, 184, 74), "female": False},
)

@dataclass
class Config:
    difficulty: str = "hard"

    rows: int = 15
    cols: int = 15
    seed: Optional[int] = None
    goal: Tuple[int, int] = (7, 7)
    zombie_count: int = 10
    heart_count: int = 5
    obstacle_count: int = 9

    coin_values: Tuple[int, ...] = (3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 7, 8)
    high_coin_value: int = 7

    start_lives: int = 1
    max_lives: int = 3
    agents: tuple = AGENTS

    attack_range: int = 2
    zombie_damage: int = 1
    zombie_kill_score: int = 20
    coin_multiplier: int = 1
    kills_to_unlock: int = 1
    coins_to_kill: int = 20

    max_rounds: int = 250
    step_delay_ms: int = 260

    minimax_depth: int = 4
    mcts_iterations: int = 60
    mcts_time_limit: float = 0.02

DEFAULT = Config()
