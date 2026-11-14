"""Grid generation and map validation.

Placement rules (applied on every generation, so each refresh differs):
  * agents start in 3 different rows
  * hearts (+1 life) never lie in an agent's row
  * zombies occupy 5 different rows AND 5 different columns, never in an
    agent's row
  * one coin per row; the high coins (8/10/12) go next to zombies and far
    from the agents, the cheap ones (3/5) go anywhere else
  * nothing ever shares a cell
"""
import random
from collections import deque
from dataclasses import dataclass, field

DIRS = {"UP": (-1, 0), "DOWN": (1, 0), "LEFT": (0, -1), "RIGHT": (0, 1)}

def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

@dataclass
class MapData:
    rows: int
    cols: int
    goal: tuple
    starts: list
    zombies: list
    coins: dict
    hearts: set
    obstacles: set = field(default_factory=set)
    seed: int = 0
