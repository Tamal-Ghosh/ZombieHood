from dataclasses import dataclass


@dataclass
class Survivor:
    idx: int
    name: str
    algo: str
    label: str
    color: tuple
    female: bool
    start: tuple
    pos: tuple
    lives: int
    max_lives: int
    score: int = 0
    coins: int = 0
    kills: int = 0
    alive: bool = True
    human: bool = False
    reached_goal: bool = False

    def copy(self):
        c = Survivor.__new__(Survivor)
        c.__dict__.update(self.__dict__)
        return c

    def gain_life(self):
        if self.lives >= self.max_lives:
            return False
        self.lives += 1
        return True

    def lose_life(self, n=1):
        self.lives = max(0, self.lives - n)
        if self.lives == 0:
            self.alive = False
