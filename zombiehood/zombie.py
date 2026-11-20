"""Zombie state and combat helpers."""
from dataclasses import dataclass
from map import manhattan


@dataclass
class Zombie:
    id: int
    pos: tuple
    alive: bool = True

    def copy(self):
        c = Zombie.__new__(Zombie)
        c.__dict__.update(self.__dict__)
        return c

    def kill(self):
        self.alive = False


def adjacent_alive(zombies, pos):
    """Living zombies orthogonally adjacent to ``pos`` (each listed once)."""
    return [z for z in zombies if z.alive and manhattan(z.pos, pos) == 1]


def in_range_alive(zombies, pos, attack_range):
    """Living zombies a survivor standing on ``pos`` could shoot."""
    return [z for z in zombies
            if z.alive and 1 <= manhattan(z.pos, pos) <= attack_range]
