"""Headless batch simulator: python simulate.py [matches] [first_seed]

Plays full AI-vs-AI matches without opening a window and prints a summary.
Useful for debugging, balancing and comparing the three algorithms.
"""
import sys
import time
from collections import Counter
from ai import create_agent
from config import Config
from map import generate_map
from state import GameState

def play_match(cfg, seed, max_actions=5000):
    st = GameState.from_map(cfg, generate_map(cfg, seed))
    agents = [create_agent(sp, i, seed, cfg) for i, sp in enumerate(cfg.agents)]
    think = [0.0] * len(agents)
    actions = 0
    while not st.over and actions < max_actions:
        i = st.turn
        t0 = time.perf_counter()
        a = agents[i].choose_action(st.copy(), i)
        think[i] += time.perf_counter() - t0
        if st.apply(i, a) is None:
            raise RuntimeError("%s returned illegal action %r" % (cfg.agents[i]["name"], a))
        actions += 1
    return st, think
