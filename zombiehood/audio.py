"""Sound playback for real game events (never AI simulations)."""
from pathlib import Path
import warnings
import pygame


class Audio:
    def __init__(self):
        self.enabled = False
        self.phase = None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(max(8, pygame.mixer.get_num_channels()))
            pygame.mixer.set_reserved(3)
            base = Path(__file__).resolve().parent
            self.sounds = {}
            for key, filename in {
                "ambient": "game_bhad_a_always_game_a.mpeg",
                "match": "game_cola_time_a.mpeg",
                "pickup": "coin_gain_or_live_gain.mpeg",
                "kill": "Zombie_or_player_kill.mpeg",
                "game_over": "game_over.mpeg",
            }.items():
                self.sounds[key] = pygame.mixer.Sound(str(base / filename))
            self.sounds["ambient"].set_volume(0.22)
            self.sounds["match"].set_volume(0.32)
            self.sounds["pickup"].set_volume(0.75)
            self.sounds["kill"].set_volume(0.8)
            self.sounds["game_over"].set_volume(0.85)
            self.ambient = pygame.mixer.Channel(0)
            self.match = pygame.mixer.Channel(1)
            self.game_over = pygame.mixer.Channel(2)
            self.ambient.play(self.sounds["ambient"], loops=-1)
            self.enabled = True
        except (pygame.error, OSError) as exc:
            warnings.warn(f"Audio unavailable: {exc}", RuntimeWarning)

    def sync(self, phase):
        if not self.enabled or phase == self.phase:
            return
        previous = self.phase
        self.phase = phase
        if previous == "over":
            self.game_over.stop()
        if phase == "playing":
            if previous == "paused":
                self.match.unpause()
            else:
                self.match.play(self.sounds["match"], loops=-1)
        elif phase == "paused":
            self.match.pause()
        else:
            self.match.stop()
            if phase == "over":
                self.game_over.play(self.sounds["game_over"])

    def event(self, kind):
        if not self.enabled:
            return
        key = "pickup" if kind in ("coin", "heart") else "kill" if kind in ("kill", "death") else None
        if key:
            self.sounds[key].play()
