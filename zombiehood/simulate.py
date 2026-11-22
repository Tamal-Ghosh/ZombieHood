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

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    cfg = Config()
    wins, deaths, reasons = Counter(), Counter(), Counter()
    totals = {sp["name"]: [0, 0.0] for sp in cfg.agents}
    rounds = 0
    for seed in range(first, first + n):
        st, think = play_match(cfg, seed)
        reasons[st.reason] += 1
        rounds += st.round
        if st.winner is not None:
            wins[st.survivors[st.winner].name] += 1
        for s in st.survivors:
            totals[s.name][0] += s.coins
            totals[s.name][1] += think[s.idx]
            if not s.alive:
                deaths[s.name] += 1
    print("matches:", n, "avg rounds: %.1f" % (rounds / n), dict(reasons))
    for sp in cfg.agents:
        nm = sp["name"]
        print("%-7s %-24s wins=%2d deaths=%2d avg coins=%5.1f think=%.3fs/match"
              % (nm, sp["label"], wins[nm], deaths[nm], totals[nm][0] / n,
                 totals[nm][1] / n))

if __name__ == "__main__":
    main()
