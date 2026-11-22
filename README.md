# ZombieHood — The Last Rise

**Three survivors. Three AI strategies. One escape.**

ZombieHood is a turn-based zombie-survival game built with **Python and Pygame**. Tamal, Progga and Nijhum compete on a procedurally generated isometric board: collect coins, manage health, defeat zombies, challenge other survivors and reach the locked exit before time runs out.

Watch an **AI vs AI** match or take control of any survivor in **AI vs Human** mode. Both modes use the same movement, combat, resource and victory rules.

## Contents

- [Features](#features)
- [Install and run](#install-and-run)
- [Game modes and controls](#game-modes-and-controls)
- [Survivors and AI algorithms](#survivors-and-ai-algorithms)
- [Rules and scoring](#rules-and-scoring)
- [Difficulty presets](#difficulty-presets)
- [Board generation and visuals](#board-generation-and-visuals)
- [Audio](#audio)
- [Project structure](#project-structure)
- [Architecture](#architecture)
- [Tests and headless simulation](#tests-and-headless-simulation)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

## Features

- Two play modes: watch three AIs compete, or play against two AIs.
- Three difficulty presets with different grid sizes, starting health, obstacles and combat thresholds.
- Seeded map generation with placement and reachability validation.
- A fixed isometric board with raised obstacles and depth-sorted objects.
- Personalized survivor characters, four-direction facing and one footstep animation per cell transition.
- Five zombie appearances, assigned across the match, with animated body movement.
- Coin and heart pickups, agent clashes and a goal unlocked individually by defeating a zombie.
- A **2 minute 30 second active-play limit** with a visible countdown.
- Player cards, rank indicators, event log, human-turn feedback and final standings.
- Shot and zombie-hit effects, looping music and event-triggered sound effects.
- A normal resizable window, optional borderless fullscreen and restart/new-map controls.
- A pure Python rules engine, automated regression tests and a headless batch simulator.

## Install and run

### Requirements

- Python; **Python 3.10+ is recommended**. Development validation has used Python 3.13.
- Pygame, installed from [`requirements.txt`](requirements.txt), which declares `pygame>=2.1`.
- A desktop display for the interactive game. Audio output is optional: audio initialization failures disable sound without stopping gameplay.

No API key, database or external game server is required.

### Windows / PowerShell

From a terminal:

```powershell
git clone https://github.com/Tamal-Ghosh/ZombieHood.git
cd ZombieHood
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe zombiehood/main.py
```

Calling the virtual environment's Python directly avoids requiring PowerShell activation scripts.

### Linux / macOS

```bash
git clone https://github.com/Tamal-Ghosh/ZombieHood.git
cd ZombieHood
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python zombiehood/main.py
```

The remaining examples use `python`. Replace it with your virtual environment's Python command when necessary. Run commands from the **repository root**.

### Launch options

```powershell
# Open the mode-selection menu; default difficulty is hard.
python zombiehood/main.py

# Start the menu with a selected preset and reproducible map seed.
python zombiehood/main.py --difficulty medium --seed 42

# Immediately play as a specific survivor.
python zombiehood/main.py --human tamal --difficulty easy --seed 42
python zombiehood/main.py --human progga --difficulty medium
python zombiehood/main.py --human nijhum --difficulty hard

# Display all launch arguments.
python zombiehood/main.py --help
```

A seed reproduces the map layout. It does not promise identical match outcomes: human decisions and time-budgeted AI search can change the match.

## Game modes and controls

### AI vs AI

Choose **AI vs AI**, then Easy, Medium or Hard. All three survivors choose their own actions. You can watch the match, pause, change AI turn speed, restart or generate another map.

### AI vs Human

Choose **AI vs Human**, a difficulty and a survivor. The selected survivor's card displays **YOU**. The other two remain AI-controlled.

The game waits for input on your turn. Invalid moves do not consume your turn, and blocked-move/attack feedback appears on screen. The countdown still runs while you choose an action. If your survivor dies, the remaining AIs can continue playing.

### Controls

| Context | Key / action | Effect |
| --- | --- | --- |
| Main menu | `Space` / `1` | Select AI vs AI |
| Main menu | `Enter` / `H` / `2` | Select AI vs Human |
| Difficulty menu | `1` / `E`, `2` / `M`, `3` / `H` | Easy, Medium, Hard |
| Survivor menu | `1` / `T`, `2` / `P`, `3` / `N` | Tamal, Progga, Nijhum |
| Selection menus | `B` / `Backspace` | Previous selection screen |
| Human turn | Arrow keys / `W A S D` | Move one cell |
| Human turn | `Space` | Shoot a zombie, if eligible |
| Human turn | `Z` | Wait for one turn |
| Match | `P` | Pause / resume |
| Match / results | `R` | Restart with the same map seed and selected human |
| Match / results | `N` | Request a new map, preserving the selected human |
| Match / results | `M` | Return to the main menu |
| Match | `+` / `-` | Increase / decrease AI turn speed |
| Window | `F11` | Toggle borderless fullscreen |
| Window | `Esc` | Leave fullscreen for a normal window |
| Window | Native close button | Exit the application |

Menus and match controls also have clickable buttons. `Esc` does **not** pause or close the game. When a fixed seed is configured, New Map can reproduce the same map; restart without `--seed` to allow random layouts.

## Survivors and AI algorithms

The active assignments in [`zombiehood/config.py`](zombiehood/config.py) are:

| Survivor | Color | Active algorithm | Implementation |
| --- | --- | --- | --- |
| **Tamal** | Blue | Monte Carlo Tree Search | [`ai_mcts.py`](zombiehood/ai_mcts.py) |
| **Progga** | Pink | Fuzzy Logic | [`ai_fuzzy.py`](zombiehood/ai_fuzzy.py) |
| **Nijhum** | Orange | A* Search | [`ai_astar.py`](zombiehood/ai_astar.py) |

### Tamal: intent-based MCTS

Tamal considers strategic intents such as collecting resources, approaching firing positions, clashing with opponents and escaping. The search simulates future actions and uses UCT-style selection and backpropagated rewards to choose a move. Defaults include an iteration budget of 60 and a time budget of 0.02 seconds per decision.

### Progga: fuzzy goal selection

Progga evaluates situations through triangular/trapezoidal membership functions and fuzzy rules. Inputs include resource value, distance, current coin balance and health. Rule strengths are combined using weighted output centroids to rank goals; pathfinding then chooses the next movement action.

### Nijhum: danger-aware A*

Nijhum uses A* with Manhattan-distance guidance and additional costs for dangerous zombie-adjacent cells and penalty tiles. Candidate destinations include coins, hearts, firing positions and the unlocked exit. Goal value and path cost help determine which target to pursue.

### Optional Minimax implementation

[`ai_minimax.py`](zombiehood/ai_minimax.py) remains available, and the agent factory supports `"minimax"`. It is **not Nijhum's active algorithm on the current main branch**. Change the corresponding `AGENTS` entry and label in `config.py` to select it.

All AI agents receive a copied game state and return an action. The rules engine validates that action; an AI returning an invalid action falls back to waiting in the interactive game.

## Rules and scoring

### Turns and movement

- Turn order follows Tamal → Progga → Nijhum, skipping dead survivors.
- Each turn allows one action: move, attack or wait.
- Movement is orthogonal: up, down, left or right. No diagonal moves.
- Obstacles, live-zombie cells and buried/death cells block entry. The exit blocks entry until unlocked for that survivor.
- Moving toward another living survivor can trigger a clash; see below.
- Animation does not add extra game actions. Each cell transition displays one footstep, and the character faces its movement direction.

### Coins and hearts

| Event | Coins | Health |
| --- | --- | --- |
| Collect a coin worth `v` | +v | Unchanged |
| Collect a heart below the health cap | Unchanged | +1 life |
| Shoot a zombie | Unchanged | Unchanged |
| Take a zombie hit | Unchanged | Lose one life per adjacent zombie by default |
| Win an agent clash | Take the loser's coins | Unchanged |
| Lose an agent clash | Balance becomes zero | Lose one life |
| Enter a blue or pink penalty cell | Lose up to one or two coins respectively | Unchanged |

A heart is consumed only when it increases health.

### Zombie combat

1. Moving onto a cell orthogonally adjacent to a living zombie causes damage.
2. Each adjacent zombie hits once for that movement action. Two adjacent zombies therefore cost two lives with the default damage setting.
3. Zombie attacks remove **health only**, including lethal attacks; carried coins are retained.
4. Shooting and waiting do not trigger adjacency damage.
5. To shoot, the survivor must have the preset's required coin balance and a zombie within Manhattan attack range.
6. The nearest eligible zombie is killed, with zombie ID used to break equal-distance ties.
7. The required coins are an eligibility threshold, **not ammunition spent per shot**.
8. Killing a zombie opens its cell, adds one kill.

A shot effect shows the agent attacking a zombie. Red attack lines show which adjacent zombies damaged an agent.

### Agent vs agent clashes

A clash is triggered by attempting to move into another living agent's cell. It is separate from the `Space` action, which shoots zombies.

- **Unequal coin balances:** the richer agent wins, regardless of who initiated the move.
- The winner receives all loser coins; the loser's coin balance becomes **zero**.
- The loser loses exactly **one life**. That life is not added to the winner.
- A surviving loser retreats. A losing initiator stays in its original cell; a losing defender can use the winner's vacated cell when necessary.
- **Equal coin balances:** the move is blocked; no clash, coin transfer or life loss occurs.
- A lethal clash emits a death event and records a blocked burial cell.

Example: an agent with 7 coins challenges an agent with 12. The richer agent finishes with 19 coins; the challenger has 0 coins and one fewer life. The same winner is chosen if the richer agent initiates instead.

A winning mover can still encounter destination pickups, tile penalties or adjacent-zombie damage afterward. These are separate events in the log.

### Exit, victory and timeout

- The exit unlocks **for each survivor individually** after the configured kill requirement: one zombie kill in all shipped presets.
- Reaching the unlocked exit alive wins immediately, regardless of who has the most coins.
- The winner faces the camera at the exit. A four-second celebration precedes the result screen.
- A live match has **150 seconds / 2 minutes 30 seconds of active play**.
- Pausing freezes the countdown; waiting for human input does not.
- If nobody reaches the goal before the deadline, the result is **TIME OUT**, with no winner, rather than a draw or a coin-based victory.
- If everyone dies first, the live match ends in defeat.
- Final standings rank survivors by coins; they do not replace the goal-based victory condition.

The headless simulator uses different stopping safeguards; see [Tests and headless simulation](#tests-and-headless-simulation).

## Difficulty presets

| Setting | Easy | Medium | Hard |
| --- | --- | --- | --- |
| Grid | 10 × 10 | 12 × 12 | 15 × 15 |
| Starting lives | 3 | 2 | 1 |
| Maximum lives | 5 | 3 | 3 |
| Zombies | 4 | 7 | 10 |
| Hearts | 5 | 5 | 5 |
| Obstacles | 3 | 6 | 9 |
| Coin pickups | 10 | 12 | 15 |
| Required coin balance to shoot | 10 | 15 | 20 |
| Attack range, Manhattan cells | 3 | 2 | 2 |
| Blue penalty cells | 2 | 3 | 4 |
| Pink penalty cells | 1 | 2 | 3 |
| Kills required to unlock exit | 1 | 1 | 1 |
| Interactive match time | 2:30 | 2:30 | 2:30 |

Default AI turn delay is 420 ms. Changing AI speed changes the action pace, not the 150-second active-play budget.

## Board generation and visuals

Map generation is implemented in [`map.py`](zombiehood/map.py) and validated before a match starts:

- Survivors start in different rows.
- Hearts and zombies are placed outside survivors' starting rows.
- Zombies occupy distinct rows and columns.
- Each row receives one coin pickup in the shipped presets; high-value coin placement favors locations near zombies and away from survivor starts.
- Starts, goal, pickups, obstacles and zombies do not share an initial placement cell.
- Reachability checks prevent obstacles from isolating the required map locations, treating zombies as removable through combat.
- Blue/pink penalty sets are assigned in `state.py`, retain their designated starting cells and add deterministic empty cells to reach the preset counts.

The board uses a fixed **isometric 2D projection**, not a movable 3D camera. Colored borders identify penalty cells; solid agent colors identify their occupied tiles. These visual markers have different meanings: an agent-colored occupied tile is not automatically a penalty tile.

Sprites, pickups and raised objects are drawn back-to-front so objects behind characters remain behind them. Survivor cards show identity, life, kills, carried coins, rank and exit readiness. The event log explains pickups, damage, clashes and match outcomes.

## Audio

Audio files live beside `main.py` and are loaded relative to the module location.

| File | Trigger |
| --- | --- |
| `game_bhad_a_always_game_a.mpeg` | Low-volume ambient loop across game screens |
| `game_cola_time_a.mpeg` | Match loop; pauses with gameplay and stops outside the match |
| `coin_gain_or_live_gain.mpeg` | Coin or life pickup |
| `Zombie_or_player_kill.mpeg` | Zombie kill or survivor death |
| `game_over.mpeg` | Plays once on entering the result screen, including TIME OUT |

Returning to the menu or starting another match stops the result sound. Audio is triggered by real match events, not by the AI's hypothetical search states.

## Project structure

```text
ZombieHood/
├── README.md
├── requirements.txt
└── zombiehood/
    ├── main.py                 # CLI, window, input and main rendering loop
    ├── config.py               # Presets, agent assignments and tunable settings
    ├── game.py                 # Match lifecycle, timer, input, events and outcomes
    ├── state.py                # Rules engine and copyable simulation state
    ├── map.py                  # Seeded generation and map validation
    ├── survivor.py             # Survivor data, life and facing
    ├── zombie.py               # Zombie data and adjacency/range helpers
    ├── ai.py                   # Agent interface, human agent and factory
    ├── ai_mcts.py              # Tamal's active MCTS agent
    ├── ai_fuzzy.py             # Progga's active fuzzy agent
    ├── ai_astar.py             # Nijhum's active A* agent
    ├── ai_minimax.py           # Optional alternative agent
    ├── ui.py                   # Board, HUD, menus, effects and sprite animation
    ├── audio.py                # Music channels and event sounds
    ├── simulate.py             # Headless AI batch runner
    ├── assets/
    │   ├── agent_survivors_upright.png
    │   ├── agent_walk_frames.png
    │   ├── agent_directions_tamal.png
    │   ├── agent_directions_progga.png
    │   ├── agent_directions_nijhum.png
    │   └── zombie_fullbody.png
    ├── tests/
    │   └── test_game.py
    ├── Creepster-Regular.ttf
    ├── PressStart2P-Regular.ttf
    └── *.mpeg                  # Bundled sound files
```

Keep the fonts, sound files and `assets/` directory with the Python files when copying or distributing the game.

## Architecture

```text
main.py
  ├── reads configuration and input
  ├── Game.update(elapsed_ms)
  │     ├── HumanAgent reads a queued action, or AI examines a state copy
  │     ├── GameState.apply() validates and resolves the action
  │     └── Game records events, visual effects and the outcome
  ├── Audio syncs playback with game phase and real events
  └── Renderer draws board, characters, HUD and dialogs
```

`state.py` is independent of Pygame. Its copied states allow algorithms to evaluate alternatives without changing the live match. `Game` owns the wall-clock deadline and presentation events; `Renderer` owns visual animation state, which does not change game rules.

## Tests and headless simulation

### Regression tests

From the repository root:

```powershell
python -B -m unittest discover -s zombiehood/tests -v
```

The suite covers map generation, movement, combat, coin retention on zombie hits, agent-clash transfers and retreats, difficulty presets, human input, goal outcomes, the live deadline, pause behavior and restart behavior.

To inspect a specific area:

```powershell
python -B -m unittest discover -s zombiehood/tests -p test_game.py -k AgentClash -v
python -B -m unittest discover -s zombiehood/tests -p test_game.py -k MatchDeadlineTests -v
```

### Headless AI matches

```powershell
# 20 matches, starting at seed 1 (defaults).
python zombiehood/simulate.py

# 5 matches using seeds 10 through 14.
python zombiehood/simulate.py 5 10
```

The simulator prints match counts, average rounds, termination reasons and each agent's wins, deaths, average coin balance and thinking time. It uses the default `Config()` preset, which is Hard.

**The simulator does not run the live 2:30 wall-clock countdown.** It creates `GameState` directly, retaining round-limit and unwinnable-state safeguards. Those simulated runs can finish with a draw or a coin-based round-limit result. The interactive `Game` enables the active-play deadline and suppresses those early draw/round-limit endings.

Search uses timing budgets, so batch results are measurements from that run, not a guarantee that one algorithm always wins. A repeated seed is primarily a layout-reproduction tool.

## Configuration

Edit [`zombiehood/config.py`](zombiehood/config.py):

| Setting | Purpose |
| --- | --- |
| `AGENTS` | Survivor names, algorithm keys, labels and colors |
| `rows`, `cols`, `goal` | Board dimensions and exit coordinate |
| `zombie_count`, `heart_count`, `obstacle_count` | Initial entity counts |
| `coin_values` | Coin pickup values; shipped presets supply one per row |
| `blue_cell_count`, `pink_cell_count` | Penalty-cell counts |
| `start_lives`, `max_lives` | Starting health and health cap |
| `coins_to_kill`, `attack_range` | Shot eligibility and range |
| `zombie_damage` | Zombie damage |
| `kills_to_unlock` | Personal kill requirement for the exit |
| `match_time_limit_ms` | Live active-play deadline; default `150_000` |
| `step_delay_ms` | Default interval between AI actions |
| `mcts_iterations`, `mcts_time_limit` | MCTS search budgets |
| `minimax_depth` | Optional Minimax search depth |
| `max_rounds` | Non-live simulation stopping safeguard |

`make_config()` supplies difficulty-specific overrides. Change a preset there when a setting differs between Easy, Medium and Hard. Keep placement counts compatible with the grid; invalid combinations can prevent map generation.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `No module named pygame` | Install `requirements.txt` with the same Python interpreter used to launch the game. |
| No sound | Check system volume and audio output. An `Audio unavailable` warning means the mixer or a bundled audio file could not load. Gameplay continues silently. |
| Missing or fallback character art | Restore the complete `zombiehood/assets/` directory from the repository. |
| Human character does not move | Wait for YOUR TURN, then use a legal move. Check the feedback panel; coins, obstacles, locked cells or an equal-coin opponent can affect legality. |
| Cannot shoot | Reach the preset's required coin balance and bring a living zombie within attack range. |
| Cannot enter the exit | That survivor must first meet `kills_to_unlock`; another survivor's kill does not unlock your exit. |
| Window is too small or fullscreen | Use normal window resizing/maximize, or `F11`. `Esc` restores windowed mode. |
| New Map keeps the same layout | A fixed `--seed` or configured seed reproduces the map; relaunch without it for random layouts. |
| Game exits with an error | Launch from a terminal to see the traceback. Unexpected launcher errors are also written to `zombiehood/crash.log` when possible. |
| Custom preset fails to generate | Check available rows/columns, entity counts and free cells against the placement constraints. |

## Project contributors and assets

The game features survivor characters named **Tamal, Progga and Nijhum**. Git history records code contributions. Custom character artwork and bundled audio are included in the repository; no separate asset-license declarations are provided here.
