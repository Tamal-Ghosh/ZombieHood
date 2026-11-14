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

def make_config(difficulty: str = "hard", seed: Optional[int] = None) -> Config:
    """Create a balanced preset config for Easy (10x10), Medium (12x12), or Hard (15x15)."""
    diff = (difficulty or "hard").strip().lower()
    if diff == "easy":
        return Config(
            difficulty="easy",
            rows=10,
            cols=10,
            seed=seed,
            goal=(5, 5),
            zombie_count=4,
            heart_count=5,
            obstacle_count=3,
            coin_values=(4, 4, 4, 5, 5, 5, 6, 7, 8, 8),
            high_coin_value=7,
            start_lives=3,
            max_lives=5,
            attack_range=3,
            coins_to_kill=10,
            max_rounds=150,
        )
    elif diff == "medium":
        return Config(
            difficulty="medium",
            rows=12,
            cols=12,
            seed=seed,
            goal=(6, 6),
            zombie_count=7,
            heart_count=5,
            obstacle_count=6,
            coin_values=(3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 7, 8),
            high_coin_value=7,
            start_lives=2,
            max_lives=3,
            attack_range=2,
            coins_to_kill=15,
            max_rounds=200,
        )
    else:
        return Config(
            difficulty="hard",
            rows=15,
            cols=15,
            seed=seed,
            goal=(7, 7),
            zombie_count=10,
            heart_count=5,
            obstacle_count=9,
            coin_values=(3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 7, 8),
            high_coin_value=7,
            start_lives=1,
            max_lives=3,
            attack_range=2,
            coins_to_kill=20,
            max_rounds=250,
        )

DEFAULT = Config()
