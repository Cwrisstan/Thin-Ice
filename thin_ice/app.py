"""Pygame initialization and application loop."""

import pygame

from .game import GameManager
from .settings import FPS, HEIGHT, WIDTH, RENDER_WIDTH, RENDER_HEIGHT


def main():
    pygame.init()

    try:
        # Actual game window
        screen = pygame.display.set_mode((WIDTH, HEIGHT))

        # Game still renders internally using the ORIGINAL coordinates.
        game_surface = pygame.Surface((WIDTH, HEIGHT))

        # Low-resolution surface used to create the pixel-art effect.
        pixel_surface = pygame.Surface(
            (RENDER_WIDTH, RENDER_HEIGHT)
        )

        pygame.display.set_caption("Thin Ice")

        clock = pygame.time.Clock()
        game = GameManager()

        running = True

        while running:
            # Prevent giant physics jumps if the window freezes/is dragged.
            dt = min(clock.tick(FPS) / 1000, 0.033)

            for event in pygame.event.get():
                if (
                    event.type == pygame.QUIT
                    or (
                        event.type == pygame.KEYDOWN
                        and event.key == pygame.K_ESCAPE
                    )
                ):
                    running = False

                game.handle_event(event)

            game.update(dt)

            # ---------------------------------------
            # NORMAL GAME RENDER
            # ---------------------------------------

            game.draw(game_surface)

            # ---------------------------------------
            # PIXEL-ART PASS
            #
            # 1000x700
            #     ↓
            # 500x350
            #     ↓
            # 1000x700
            #
            # Nearest-neighbor scaling gives us
            # hard pixel edges.
            # ---------------------------------------

            pygame.transform.scale(
                game_surface,
                (RENDER_WIDTH, RENDER_HEIGHT),
                pixel_surface,
            )

            pygame.transform.scale(
                pixel_surface,
                (WIDTH, HEIGHT),
                screen,
            )

            pygame.display.flip()

    finally:
        pygame.quit()