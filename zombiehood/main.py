# GLOBAL COMMIT: 27
# OWNER: Nijhum
# COMMIT MESSAGE: Add launcher input mapping and display scaling
# REPOSITORY DESTINATION: zombiehood/main.py
# Cumulative snapshot: replace destination contents with this file.
# Partial stage; follow GLOBAL_SERIAL.md before running.

"""ZombieHood - The Last Rise.   Run:  python main.py [--seed N] [--human NAME]"""
import argparse
import sys
import pygame
from config import Config, make_config
from game import Game, Phase
from ui import H, W, Renderer

KEY_ACTIONS = {
    pygame.K_UP: "UP", pygame.K_w: "UP", pygame.K_DOWN: "DOWN", pygame.K_s: "DOWN",
    pygame.K_LEFT: "LEFT", pygame.K_a: "LEFT", pygame.K_RIGHT: "RIGHT", pygame.K_d: "RIGHT",
    pygame.K_SPACE: "ATTACK", pygame.K_z: "WAIT",
}


def run_action(game, ui, act):
    """Menu / control actions shared by keyboard shortcuts and buttons."""
    if act == "choose_diff_ai":
        ui.chosen_mode = "ai"
        ui.menu_mode = "select_difficulty"
    elif act == "choose_diff_human":
        ui.chosen_mode = "human"
        ui.menu_mode = "select_difficulty"
    elif act == "menu_main":
        ui.menu_mode = "main"
    elif act == "menu_diff":
        ui.menu_mode = "select_difficulty"
    elif act.startswith("diff_"):
        diff = act.split("_")[1]
        ui.chosen_diff = diff
        if ui.chosen_mode == "ai":
            ui.menu_mode = "main"
            game.start_match(None, difficulty=diff)
        else:
            ui.menu_mode = "select_human"
    elif act in ("h0", "h1", "h2"):
        ui.menu_mode = "main"
        game.start_match(int(act[1]), difficulty=ui.chosen_diff)
    elif act == "ai":
        ui.menu_mode = "main"
        game.start_match(None, difficulty=ui.chosen_diff)
    elif act == "pause":
        game.toggle_pause()
    elif act == "restart" and game.state:
        game.restart()
    elif act == "new" and game.state:
        game.new_map()
    elif act == "menu":
        ui.menu_mode = "main"
        game.to_menu()


def main():
    ap = argparse.ArgumentParser(description="ZombieHood - The Last Rise")
    ap.add_argument("--seed", type=int, help="reproduce a specific map")
    ap.add_argument("--difficulty", choices=["easy", "medium", "hard"], default="hard",
                    help="choose difficulty level (easy: 10x10, medium: 12x12, hard: 15x15)")
    ap.add_argument("--human", choices=["tamal", "progga", "nijhum"],
                    help="take control of one survivor")
    args = ap.parse_args()

    cfg = make_config(difficulty=args.difficulty, seed=args.seed)
    pygame.init()
    pygame.display.set_caption("ZombieHood - The Last Rise")
    desktop_w, desktop_h = pygame.display.get_desktop_sizes()[0]
    scale = min(1.0, (desktop_w - 80) / W, (desktop_h - 120) / H)
    window = pygame.display.set_mode((int(W * scale), int(H * scale)), pygame.RESIZABLE)
    screen = pygame.Surface((W, H))

    def viewport():
        ww, wh = window.get_size()
        factor = min(ww / W, wh / H)
        return pygame.Rect((ww - int(W * factor)) // 2,
                           (wh - int(H * factor)) // 2,
                           max(1, int(W * factor)), max(1, int(H * factor)))

    def logical_mouse(pos):
        area = viewport()
        return ((pos[0] - area.x) * W / area.width,
                (pos[1] - area.y) * H / area.height)
    clock = pygame.time.Clock()
    game = Game(cfg)
    ui = Renderer(screen, cfg)
    if args.human:
        game.start_match([a["name"].lower() for a in cfg.agents].index(args.human), difficulty=args.difficulty)

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for rect, act in ui.buttons:
                    if rect.collidepoint(logical_mouse(e.pos)):
                        run_action(game, ui, act)
                        break
            if e.type != pygame.KEYDOWN:
                continue
            k = e.key
            if k == pygame.K_ESCAPE:
                if game.phase == Phase.MENU:
                    if ui.menu_mode == "select_human":
                        run_action(game, ui, "menu_diff")
                        continue
                    elif ui.menu_mode == "select_difficulty":
                        run_action(game, ui, "menu_main")
                        continue
                pygame.quit()
                sys.exit()
            if game.phase == Phase.MENU:
                if ui.menu_mode == "select_difficulty":
                    if k in (pygame.K_1, pygame.K_e):
                        run_action(game, ui, "diff_easy")
                    elif k in (pygame.K_2, pygame.K_m):
                        run_action(game, ui, "diff_medium")
                    elif k in (pygame.K_3, pygame.K_h):
                        run_action(game, ui, "diff_hard")
                    elif k in (pygame.K_b, pygame.K_BACKSPACE):
                        run_action(game, ui, "menu_main")
                elif ui.menu_mode == "select_human":
                    if k in (pygame.K_1, pygame.K_t):
                        run_action(game, ui, "h0")
                    elif k in (pygame.K_2, pygame.K_p):
                        run_action(game, ui, "h1")
                    elif k in (pygame.K_3, pygame.K_n):
                        run_action(game, ui, "h2")
                    elif k in (pygame.K_b, pygame.K_BACKSPACE):
                        run_action(game, ui, "menu_diff")
                else:  # "main"
                    if k in (pygame.K_SPACE, pygame.K_1):
                        run_action(game, ui, "choose_diff_ai")
                    elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_h, pygame.K_2):
                        run_action(game, ui, "choose_diff_human")
                continue
            if k == pygame.K_p:
                game.toggle_pause()
            elif k == pygame.K_r:
                run_action(game, ui, "restart")
            elif k == pygame.K_n:
                run_action(game, ui, "new")
            elif k == pygame.K_m:
                run_action(game, ui, "menu")
            elif k in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                game.change_speed(True)
            elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                game.change_speed(False)
            elif k in KEY_ACTIONS:
                game.human_input(KEY_ACTIONS[k])
        game.update(clock.tick(60))
        ui.mouse_pos = logical_mouse(pygame.mouse.get_pos())
        ui.draw(game)
        area = viewport()
        window.fill((0, 0, 0))
        window.blit(pygame.transform.smoothscale(screen, area.size), area)
        pygame.display.flip()


if __name__ == "__main__":
    main()
