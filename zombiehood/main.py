import pygame


def main():
    pygame.init()
    screen = pygame.display.set_mode((1000, 600), pygame.RESIZABLE)
    pygame.display.set_caption("ZombieHood")
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
        screen.fill((11, 15, 20))
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()


if __name__ == "__main__":
    main()
