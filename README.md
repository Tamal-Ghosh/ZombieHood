# ZombieHood — The Last Rise

A Python/Pygame zombie-survival board game with AI vs AI and AI vs Human modes.

| Survivor | Algorithm | Color |
| --- | --- | --- |
| Tamal | Monte Carlo Tree Search | Blue |
| Progga | Fuzzy Logic | Pink |
| Nijhum | Minimax with alpha-beta pruning | Orange |

## Run

```powershell
python -m pip install -r requirements.txt
python zombiehood/main.py
```

Use `--human tamal`, `--human progga`, or `--human nijhum` for direct human control;
`--difficulty easy|medium|hard` and `--seed 42` select a preset and reproducible map.

## Controls

- Arrows / WASD: move one cell on your turn; Space: attack; Z: wait.
- P: pause/resume; R: restart; N: new map; M: menu; +/-: AI turn speed.
- F11: toggle fullscreen; Esc: restore the normal window.
- B / Backspace: return to the previous selection menu.

Agents face their movement direction and animate one footstep per cell. Reaching
the goal shows a front-facing survivor. Zombies have animated full-body sprites;
attack lines show both survivor shots and zombie hits. Music and pickup, kill,
and game-over sounds are bundled with the game.

## Difficulty

| Preset | Grid | Starting lives | Coins to attack | Zombies | Pink cells | Blue cells |
| --- | --- | --- | --- | --- | --- | --- |
| Easy | 10×10 | 3 | 10 | 4 | 1 | 2 |
| Medium | 12×12 | 2 | 15 | 7 | 2 | 3 |
| Hard | 15×15 | 1 | 20 | 10 | 3 | 4 |

Pink/blue penalty tiles have colored borders; agents' occupied tiles use their
own solid colors. Collect coins, shoot zombies to unlock the goal, then escape
alive within 2 minutes 30 seconds. If nobody escapes, the match ends with TIME OUT
and plays the game-over sound. Pausing freezes the countdown. Moving adjacent to each zombie costs one life; coins and score are retained. Shooting and
waiting do not trigger adjacency damage. Every player follows the same rules.

Agent vs agent: moving toward an occupied cell compares both coin balances.
The richer agent wins, regardless of who initiated, and takes all loser coins.
The loser loses one life and retreats if still alive; the winner gains no life.
Equal coin balances block the move. A losing attacker stays in its original cell;
a losing defender can retreat into the attacker's vacated cell if necessary.
Zombie attacks only reduce life and never take coins.


## Validate

```powershell
python -B -m unittest discover -s zombiehood/tests -v
```
