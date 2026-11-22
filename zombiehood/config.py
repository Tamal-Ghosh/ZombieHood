"""Central, tweakable settings for ZombieHood - The Last Rise.

Every gameplay rule that can be tuned lives in ``Config``.  Tests and the
headless simulator build their own ``Config`` instances, so nothing in the
game logic reads module-level globals.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

# The three competing survivors.  ``algo`` selects the AI implementation.
AGENTS = (
    {"name": "Tamal", "algo": "mcts", "label": "Monte Carlo Tree Search",
     "color": (74, 163, 255), "female": False},
    {"name": "Progga", "algo": "fuzzy", "label": "Fuzzy Logic (FIS)",
     "color": (255, 123, 181), "female": True},
    {"name": "Nijhum", "algo": "astar", "label": "A* Search",
     "color": (255, 184, 74), "female": False},
)


@dataclass
class Config:
    difficulty: str = "hard"
    # --- map ---------------------------------------------------------
    rows: int = 15
    cols: int = 15
    seed: Optional[int] = None          # None -> random map every game
    goal: Tuple[int, int] = (7, 7)      # (row, col) of the locked goal
    zombie_count: int = 10
    heart_count: int = 5                # +1 life pickups
    blue_cell_count: int = 4
    pink_cell_count: int = 3
    obstacle_count: int = 9             # 8-10 blocked cells (steel boxes)
    # 15 coins across 15 rows (sum = 64, <= 65)
    coin_values: Tuple[int, ...] = (3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 7, 8)
    high_coin_value: int = 7            # coins >= this go near zombies

    # --- survivors ---------------------------------------------------
    start_lives: int = 1
    max_lives: int = 3
    agents: tuple = AGENTS

    # --- combat / scoring -------------------------------------------
    attack_range: int = 2               # Manhattan distance of a shot
    zombie_damage: int = 1              # lives lost per adjacent zombie
    zombie_kill_score: int = 20
    coin_multiplier: int = 1            # reward = coin value * multiplier
    kills_to_unlock: int = 1            # kills needed to unlock the goal
    coins_to_kill: int = 20             # coins needed to kill a zombie

    # --- match flow --------------------------------------------------
    match_time_limit_ms: int = 150_000   # 2 minutes 30 seconds of active play
    max_rounds: int = 250               # safety stop (time-up)
    step_delay_ms: int = 420            # pause between AI actions

    # --- AI strength -------------------------------------------------
    minimax_depth: int = 4
    mcts_iterations: int = 60
    mcts_time_limit: float = 0.02       # seconds per decision


def make_config(difficulty: str = "hard", seed: Optional[int] = None) -> Config:
    """Create a balanced preset config for Easy (10x10), Medium (12x12), or Hard (15x15)."""
    diff = (difficulty or "hard").strip().lower()
    if diff == "easy":
        return Config(
            difficulty="easy",
            blue_cell_count=2,
            pink_cell_count=1,
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
            blue_cell_count=3,
            pink_cell_count=2,
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
    else:  # hard (default)
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
