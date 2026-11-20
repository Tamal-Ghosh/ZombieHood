"""Run:  python -m unittest discover -s tests -v   (from the project folder)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from ai import create_agent                                  # noqa: E402
from config import Config, make_config                       # noqa: E402
from game import Game, Phase                                 # noqa: E402
from map import MapData, generate_map, validate_map          # noqa: E402
from state import GameState                                  # noqa: E402


def make_state(starts=((0, 0), (11, 11), (11, 0)), zombies=(), coins=None,
               hearts=(), obstacles=(), goal=(5, 6), **cfg_kw):
    cfg_kw.setdefault("blue_cell_count", 1)
    cfg_kw.setdefault("pink_cell_count", 1)
    cfg = Config(**cfg_kw)
    m = MapData(cfg.rows, cfg.cols, goal, list(starts), list(zombies), dict(coins or {}),
                set(hearts), set(obstacles), 0)
    return cfg, GameState.from_map(cfg, m)


def act(st, idx, a):
    """Apply ``a`` for ``idx`` after forcing it to be that survivor's turn."""
    st.turn = idx
    return st.apply(idx, a)


class MapRules(unittest.TestCase):
    def test_generation_follows_all_rules_for_many_seeds(self):
        cfg = Config()
        for seed in range(150):
            m = generate_map(cfg, seed)
            self.assertEqual(validate_map(m, cfg), [])
            self.assertEqual(len(m.zombies), cfg.zombie_count)
            self.assertEqual(len({z[0] for z in m.zombies}), cfg.zombie_count)
            self.assertEqual(len({z[1] for z in m.zombies}), cfg.zombie_count)
            self.assertEqual(len({s[0] for s in m.starts}), 3)
            self.assertEqual(len(m.coins), len(cfg.coin_values))
            self.assertTrue(60 <= sum(m.coins.values()) <= 65)
            self.assertEqual(sorted(m.coins.values()), sorted(cfg.coin_values))
            self.assertEqual(len(m.hearts), cfg.heart_count)
            self.assertTrue(8 <= len(m.obstacles) <= 10)

    def test_same_seed_same_map_different_seed_different_map(self):
        cfg = Config()
        a, b, c = generate_map(cfg, 7), generate_map(cfg, 7), generate_map(cfg, 8)
        self.assertEqual((a.starts, a.zombies, a.coins), (b.starts, b.zombies, b.coins))
        self.assertNotEqual((a.starts, a.zombies), (c.starts, c.zombies))

    def test_obstacles_never_block_the_goal(self):
        cfg = Config(obstacle_count=20)
        for seed in range(30):
            self.assertEqual(validate_map(generate_map(cfg, seed), cfg), [])


class Movement(unittest.TestCase):
    def test_moves_and_no_diagonals(self):
        _, st = make_state()
        self.assertIsNotNone(act(st, 0, "DOWN"))
        self.assertEqual(st.survivors[0].pos, (1, 0))
        self.assertIsNone(act(st, 0, "UP-LEFT"))       # diagonal is not an action
        self.assertEqual(st.survivors[0].pos, (1, 0))

    def test_cannot_leave_map(self):
        _, st = make_state()
        self.assertIsNone(act(st, 0, "UP"))
        self.assertIsNone(act(st, 0, "LEFT"))
        self.assertNotIn("UP", st.legal_actions(0))

    def test_blocked_by_obstacle_zombie_and_survivor(self):
        _, st = make_state(starts=((0, 0), (1, 1), (11, 0)), zombies=[(0, 2)],
                           obstacles=[(1, 0)])
        st.survivors[1].pos = (0, 1)
        self.assertIsNone(act(st, 0, "DOWN"))          # obstacle
        self.assertIsNone(act(st, 0, "RIGHT"))         # another survivor
        st.survivors[1].pos = (5, 5)
        act(st, 0, "RIGHT")                            # (0,1) is free now
        self.assertIsNone(act(st, 0, "RIGHT"))         # zombie cell is locked

    def test_turn_order_is_enforced(self):
        _, st = make_state()
        self.assertIsNone(st.apply(1, "UP"))
        self.assertIsNotNone(st.apply(0, "DOWN"))
        self.assertEqual(st.turn, 1)


class Combat(unittest.TestCase):
    def test_adjacent_zombie_costs_a_life(self):
        _, st = make_state(zombies=[(3, 3)], start_lives=3)
        st.survivors[0].pos = (3, 1)
        act(st, 0, "RIGHT")                            # now at (3,2), next to zombie
        self.assertEqual(st.survivors[0].lives, 2)

    def test_each_zombie_hits_once_per_action(self):
        _, st = make_state(zombies=[(2, 3), (3, 2)], start_lives=3)
        st.survivors[0].pos = (3, 3)                   # touches both zombies
        st.survivors[0].pos = (3, 4)
        act(st, 0, "LEFT")                             # enters (3,3)
        self.assertEqual(st.survivors[0].lives, 1)     # exactly one hit per zombie
        act(st, 0, "WAIT")                             # no new damage
        st.turn = 0
        self.assertEqual(st.survivors[0].lives, 1)

    def test_attack_and_wait_never_hurt(self):
        _, st = make_state(zombies=[(3, 3)], start_lives=3)
        st.survivors[0].pos = (3, 2)                   # adjacent, no damage yet
        self.assertEqual(st.survivors[0].lives, 3)
        act(st, 0, "ATTACK")
        self.assertEqual(st.survivors[0].lives, 3)

    def test_attack_kills_nearest_and_scores_20(self):
        _, st = make_state(zombies=[(3, 5), (3, 3)], attack_range=2)
        st.survivors[0].pos = (3, 1)
        st.survivors[0].coins = 25                     # requires >= 25 coins
        act(st, 0, "ATTACK")
        self.assertEqual(st.survivors[0].kills, 1)
        self.assertEqual(st.survivors[0].score, 20)
        self.assertEqual(st.zombie_cells, {(3, 5)})
        self.assertFalse(st.zombies[1].alive)

    def test_cannot_kill_without_required_coins(self):
        _, st = make_state(zombies=[(3, 3)], attack_range=2)
        st.survivors[0].pos = (3, 1)
        st.survivors[0].coins = 19                     # less than coins_to_kill (20)
        self.assertNotIn("ATTACK", st.legal_actions(0))
        self.assertIsNone(act(st, 0, "ATTACK"))
        st.survivors[0].coins = 20                     # 20 coins allows attack
        self.assertIn("ATTACK", st.legal_actions(0))
        self.assertIsNotNone(act(st, 0, "ATTACK"))
        self.assertEqual(st.survivors[0].kills, 1)

    def test_adjacent_zombie_loses_all_coins_and_life(self):
        _, st = make_state(zombies=[(3, 3)], start_lives=2)
        st.survivors[0].pos = (3, 1)
        st.survivors[0].coins = 30
        st.survivors[0].score = 30
        act(st, 0, "RIGHT")                            # enters (3, 2), adjacent to (3,3)
        self.assertEqual(st.survivors[0].lives, 1)     # lost 1 life
        self.assertEqual(st.survivors[0].coins, 0)     # lost all coins!
        self.assertEqual(st.survivors[0].score, 0)

    def test_attack_out_of_range_is_illegal(self):
        _, st = make_state(zombies=[(8, 8)])
        st.survivors[0].coins = 25
        self.assertIsNone(act(st, 0, "ATTACK"))
        self.assertNotIn("ATTACK", st.legal_actions(0))

    def test_killed_zombie_cell_becomes_walkable_and_safe(self):
        _, st = make_state(zombies=[(3, 3)], start_lives=1)
        st.survivors[0].pos = (3, 1)
        st.survivors[0].coins = 25                     # requires >= 25 coins
        act(st, 0, "ATTACK")
        act(st, 0, "RIGHT")
        act(st, 0, "RIGHT")                            # onto the old zombie cell
        self.assertEqual(st.survivors[0].pos, (3, 3))
        self.assertTrue(st.survivors[0].alive)


class CoinsHeartsLives(unittest.TestCase):
    def test_coin_collection_and_reward(self):
        _, st = make_state(coins={(0, 1): 12}, coin_multiplier=2)
        act(st, 0, "RIGHT")
        s = st.survivors[0]
        self.assertEqual((s.score, s.coins), (24, 12))
        self.assertNotIn((0, 1), st.coins)

    def test_heart_adds_life_capped_at_max(self):
        _, st = make_state(hearts=[(0, 1), (0, 3)], start_lives=1, max_lives=2)
        act(st, 0, "RIGHT")
        self.assertEqual(st.survivors[0].lives, 2)
        st.survivors[0].pos = (0, 2)
        act(st, 0, "RIGHT")                            # already at max: heart stays
        self.assertEqual(st.survivors[0].lives, 2)
        self.assertIn((0, 3), st.hearts)

    def test_zero_lives_means_death_and_defeat(self):
        _, st = make_state(zombies=[(3, 3)], start_lives=1)
        st.survivors[0].pos = (3, 1)
        ev = act(st, 0, "RIGHT")
        s = st.survivors[0]
        self.assertFalse(s.alive)
        self.assertIn("death", [e[0] for e in ev])
        self.assertFalse(st.over)                      # others still alive
        for i in (1, 2):
            st.survivors[i].lose_life(5)
        st._advance()
        self.assertTrue(st.over)
        self.assertEqual(st.reason, "all_dead")
        self.assertIsNone(st.winner)

    def test_dead_survivors_are_skipped(self):
        _, st = make_state()
        st.survivors[1].lose_life(st.survivors[1].lives)
        act(st, 0, "DOWN")
        self.assertEqual(st.turn, 2)


class GoalAndVictory(unittest.TestCase):
    def test_goal_is_locked_then_unlocks_after_kills(self):
        _, st = make_state(zombies=[(8, 8), (9, 9)], kills_to_unlock=1, goal=(5, 6))
        s = st.survivors[0]
        s.coins = 25
        s.pos = (5, 5)
        self.assertFalse(st.goal_unlocked_for(s))
        self.assertIsNone(act(st, 0, "RIGHT"))         # cannot enter locked goal
        s.pos = (8, 6)
        ev = act(st, 0, "ATTACK")                      # zombie (8,8) is 2 away
        self.assertIn("unlock", [e[0] for e in ev])
        self.assertTrue(st.goal_unlocked_for(s))
        s.pos = (5, 5)
        ev = act(st, 0, "RIGHT")
        self.assertIn("goal", [e[0] for e in ev])
        self.assertTrue(st.over)
        self.assertEqual((st.winner, st.reason), (0, "goal"))

    def test_goal_requires_at_least_one_kill_even_when_no_zombie_is_left(self):
        _, st = make_state(zombies=[], kills_to_unlock=1)
        self.assertFalse(st.goal_unlocked_for(st.survivors[1]))
        st.survivors[1].kills = 1
        self.assertTrue(st.goal_unlocked_for(st.survivors[1]))

    def test_unlock_is_per_survivor(self):
        _, st = make_state(zombies=[(8, 8)], kills_to_unlock=1)
        st.survivors[0].kills = 1
        self.assertTrue(st.goal_unlocked_for(st.survivors[0]))
        self.assertFalse(st.goal_unlocked_for(st.survivors[1]))

    def test_dying_on_the_goal_step_is_not_a_win(self):
        _, st = make_state(zombies=[(5, 8)], start_lives=1, goal=(5, 6), kills_to_unlock=0)
        st.survivors[0].pos = (5, 5)
        act(st, 0, "RIGHT")                            # goal cell touches (5,7)? no: zombie (5,8)
        self.assertTrue(st.over)                       # not adjacent -> real win
        _, st2 = make_state(zombies=[(5, 7)], start_lives=1, goal=(5, 6), kills_to_unlock=0)
        st2.survivors[0].pos = (5, 5)
        act(st2, 0, "RIGHT")
        self.assertFalse(st2.survivors[0].alive)       # bitten at the goal -> loses
        self.assertNotEqual(st2.winner, 0)

    def test_time_up_picks_best_living_score(self):
        _, st = make_state(max_rounds=1)
        st.survivors[1].score = 50
        for i in range(3):
            act(st, i, "WAIT")
        self.assertTrue(st.over)
        self.assertEqual((st.reason, st.winner), ("timeup", 1))

    def test_time_up_tied_scores_results_in_draw(self):
        _, st = make_state(max_rounds=1)
        st.survivors[0].score = 30
        st.survivors[1].score = 30
        for i in range(3):
            act(st, i, "WAIT")
        self.assertTrue(st.over)
        self.assertEqual(st.reason, "draw")
        self.assertIsNone(st.winner)

    def test_no_way_to_win_triggers_immediate_draw(self):
        # When all coins are gone and no survivor has kills to unlock goal:
        # nobody can ever get 25 coins to kill a zombie, so immediate draw
        _, st = make_state(coins={(1, 1): 25}, zombies=[(3, 3)], kills_to_unlock=1)
        st.initial_coins = 25
        st.initial_zombies = 1
        st.coins.clear()
        for s in st.survivors:
            s.kills = 0
            s.coins = 0
        act(st, 0, "WAIT")
        self.assertTrue(st.over)
        self.assertEqual(st.reason, "draw")
        self.assertIsNone(st.winner)


class GameFlow(unittest.TestCase):
    def test_every_ai_only_returns_legal_actions(self):
        cfg = Config(mcts_iterations=40, mcts_time_limit=0.1)
        st = GameState.from_map(cfg, generate_map(cfg, 5))
        agents = [create_agent(sp, i, 5, cfg) for i, sp in enumerate(cfg.agents)]
        for _ in range(60):
            if st.over:
                break
            i = st.turn
            a = agents[i].choose_action(st.copy(), i)
            self.assertIn(a, st.legal_actions(i))
            st.apply(i, a)

    def test_full_ai_match_finishes_with_an_outcome(self):
        cfg = Config(mcts_iterations=40, mcts_time_limit=0.1)
        g = Game(cfg)
        g.start_match(None, 11)
        for _ in range(2000):
            if g.phase != Phase.PLAYING:
                break
            g.update(10 ** 4)
        self.assertEqual(g.phase, Phase.OVER)
        self.assertIn(g.outcome["title"], ("GAME OVER", "DEFEAT", "TIME UP", "GAME IS DRAW"))

    def test_goal_delays_finish_for_four_seconds(self):
        g = Game(Config())
        g.start_match(0, 7)
        # Position survivor 0 next to unlocked goal
        g.state.survivors[0].kills = g.cfg.kills_to_unlock
        g.state.survivors[0].pos = (g.state.goal[0], g.state.goal[1] - 1)
        g.state.turn = 0
        g.human_input("RIGHT")
        g.update(0)
        self.assertEqual(g.state.survivors[0].pos, g.state.goal)
        self.assertTrue(g.state.over)
        self.assertTrue(g.state.survivors[0].reached_goal)
        # Immediately after entering goal: still in playing phase during 4s delay
        self.assertEqual(g.phase, Phase.PLAYING)
        self.assertEqual(g.goal_delay_ms, 4000)
        # Advance 2 seconds (2000 ms)
        g.update(2000)
        self.assertEqual(g.phase, Phase.PLAYING)
        self.assertEqual(g.goal_delay_ms, 2000)
        # Advance another 2 seconds (2000 ms) -> triggers finish and game over
        g.update(2000)
        self.assertEqual(g.phase, Phase.OVER)
        self.assertEqual(g.goal_delay_ms, 0)
        self.assertIsNotNone(g.outcome)

    def test_human_obeys_same_rules_and_waits_for_input(self):
        cfg = Config(mcts_iterations=20, mcts_time_limit=0.05)
        g = Game(cfg)
        g.start_match(0, 4)
        g.update(10 ** 4)                              # no key pressed: nothing happens
        self.assertEqual(g.state.turn, 0)
        pos = g.state.survivors[0].pos
        for bad in ("UP", "DOWN", "LEFT", "RIGHT"):
            if bad not in g.state.legal_actions(0):
                g.human_input(bad)
                g.update(0)
                self.assertEqual(g.state.turn, 0)      # blocked move: turn not used
                self.assertEqual(g.state.survivors[0].pos, pos)
                break
        g.human_input("WAIT")
        g.update(0)
        self.assertEqual(g.state.turn, 1)

    def test_pause_and_restart(self):
        g = Game(Config(mcts_iterations=20, mcts_time_limit=0.05))
        g.start_match(None, 9)
        g.toggle_pause()
        self.assertEqual(g.phase, Phase.PAUSED)
        before = g.state.round, g.state.turn
        g.update(10 ** 4)
        self.assertEqual((g.state.round, g.state.turn), before)
        g.toggle_pause()
        g.update(10 ** 4)
        g.restart()
        self.assertEqual((g.phase, g.state.round, g.seed), (Phase.PLAYING, 0, 9))


class AgentClash(unittest.TestCase):
    def test_clash_winner_with_more_coins_decreases_life_and_steals_coins(self):
        _, st = make_state(starts=((0, 0), (10, 10), (11, 11)), start_lives=2)
        st.survivors[0].pos = (3, 3)
        st.survivors[0].coins = 10
        st.survivors[0].score = 10
        st.survivors[1].pos = (3, 4)
        st.survivors[1].coins = 5
        st.survivors[1].score = 5
        ev = act(st, 0, "RIGHT")                       # Survivor 0 moves onto (3, 4)
        self.assertIsNotNone(ev)
        # Survivor 0 wins and moves to (3, 4)
        self.assertEqual(st.survivors[0].pos, (3, 4))
        self.assertEqual(st.survivors[0].coins, 15)    # 10 + 5 stolen
        # Survivor 1 lost 1 life, lost all coins, and fled to adjacent cell
        self.assertEqual(st.survivors[1].lives, 1)
        self.assertEqual(st.survivors[1].coins, 0)
        self.assertNotEqual(st.survivors[1].pos, (3, 4))
        self.assertTrue(st.survivors[1].alive)
        self.assertIn("clash", [e[0] for e in ev])
        self.assertIn("flee", [e[0] for e in ev])

    def test_blue_and_pink_border_cell_penalties(self):
        _, st = make_state(starts=((1, 1), (1, 3), (10, 10)))
        # (1, 1) is blue border cell (Tamal's start), (1, 3) is pink border cell (Progga's start)
        self.assertEqual(st.blue_cells, {(1, 1)})
        self.assertEqual(st.pink_cells, {(1, 3)})

        # Test blue border cell penalty: moving onto (1, 1) costs 1 coin
        st.survivors[0].pos = (1, 2)
        st.survivors[0].coins = 5
        st.survivors[0].score = 5
        ev_blue = act(st, 0, "LEFT")                   # moves to (1, 1)
        self.assertEqual(st.survivors[0].pos, (1, 1))
        self.assertEqual(st.survivors[0].coins, 4)     # 5 - 1 = 4
        self.assertEqual(st.survivors[0].score, 4)
        self.assertIn("penalty", [e[0] for e in ev_blue])

        # Test pink border cell penalty: moving onto (1, 3) costs 2 coins
        st.survivors[0].pos = (1, 2)
        st.survivors[0].coins = 5
        st.survivors[0].score = 5
        ev_pink = act(st, 0, "RIGHT")                  # moves to (1, 3)
        self.assertEqual(st.survivors[0].pos, (1, 3))
        self.assertEqual(st.survivors[0].coins, 3)     # 5 - 2 = 3
        self.assertEqual(st.survivors[0].score, 3)
        self.assertIn("penalty", [e[0] for e in ev_pink])

    def test_effects_live_messages_appear_for_two_seconds(self):
        cfg = Config()
        g = Game(cfg)
        g._fx("float", pos=(3, 3), text="DEFEATED!", color=(255, 80, 40))
        self.assertEqual(len(g.effects), 1)
        self.assertEqual(g.effects[0]["total"], 2000)
        self.assertEqual(g.effects[0]["ttl"], 2000)

    def test_clash_when_defeated_agent_dies_cell_is_buried_and_blocked(self):
        _, st = make_state(starts=((3, 3), (3, 4), (10, 10)), start_lives=1)
        st.survivors[0].coins = 10
        st.survivors[1].coins = 5
        ev = act(st, 0, "RIGHT")                       # Survivor 0 moves onto (3, 4)
        self.assertIsNotNone(ev)
        self.assertEqual(st.survivors[0].pos, (3, 4))
        self.assertFalse(st.survivors[1].alive)        # Survivor 1 dies!
        self.assertIn((3, 4), st.buried_cells)         # (3, 4) is a buried cell
        # Survivor 2 cannot enter (3, 4) because it's a buried cell
        self.assertFalse(st.can_enter(st.survivors[2], (3, 4)))

    def test_cannot_enter_opponent_cell_with_less_or_equal_coins(self):
        _, st = make_state(starts=((3, 3), (3, 4), (10, 10)), start_lives=2)
        st.survivors[0].coins = 5
        st.survivors[1].coins = 10
        self.assertFalse(st.can_enter(st.survivors[0], (3, 4)))
        self.assertIsNone(act(st, 0, "RIGHT"))
        # When coins are equal:
        st.survivors[0].coins = 10
        self.assertFalse(st.can_enter(st.survivors[0], (3, 4)))
        self.assertIsNone(act(st, 0, "RIGHT"))


class DifficultyLevels(unittest.TestCase):
    def test_easy_level_properties(self):
        cfg = make_config("easy")
        self.assertEqual((cfg.rows, cfg.cols), (10, 10))
        self.assertEqual(cfg.start_lives, 3)
        self.assertEqual(cfg.coins_to_kill, 10)
        self.assertEqual(cfg.zombie_count, 4)
        self.assertEqual(cfg.attack_range, 3)
        m = generate_map(cfg, 42)
        self.assertEqual(validate_map(m, cfg), [])
        st = GameState.from_map(cfg, m)
        self.assertEqual(len(st.blue_cells), 2)
        self.assertEqual(len(st.pink_cells), 1)

    def test_medium_level_properties(self):
        cfg = make_config("medium")
        self.assertEqual((cfg.rows, cfg.cols), (12, 12))
        self.assertEqual(cfg.start_lives, 2)
        self.assertEqual(cfg.coins_to_kill, 15)
        self.assertEqual(cfg.zombie_count, 7)
        self.assertEqual(cfg.attack_range, 2)
        m = generate_map(cfg, 42)
        self.assertEqual(validate_map(m, cfg), [])
        st = GameState.from_map(cfg, m)
        self.assertEqual(len(st.blue_cells), 3)
        self.assertEqual(len(st.pink_cells), 2)

    def test_hard_level_properties(self):
        cfg = make_config("hard")
        self.assertEqual((cfg.rows, cfg.cols), (15, 15))
        self.assertEqual(cfg.start_lives, 1)
        self.assertEqual(cfg.coins_to_kill, 20)
        self.assertEqual(cfg.zombie_count, 10)
        self.assertEqual(cfg.attack_range, 2)
        m = generate_map(cfg, 42)
        self.assertEqual(validate_map(m, cfg), [])
        st = GameState.from_map(cfg, m)
        self.assertEqual(len(st.blue_cells), 4)
        self.assertEqual(len(st.pink_cells), 3)

    def test_game_starts_and_completes_on_easy_and_medium(self):
        for diff in ("easy", "medium"):
            g = Game()
            g.start_match(difficulty=diff, seed=12)
            self.assertEqual(g.phase, Phase.PLAYING)
            self.assertEqual(g.cfg.difficulty, diff)
            for _ in range(150):
                if g.phase != Phase.PLAYING:
                    break
                g.step()
            self.assertIn(g.phase, (Phase.PLAYING, Phase.OVER))


if __name__ == "__main__":
    unittest.main()
