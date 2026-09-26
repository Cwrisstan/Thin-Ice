"""Smoothed, world-clamped follow camera; gameplay never uses screen coordinates."""

import math
import pygame

from .settings import WIDTH, HEIGHT, WORLD_WIDTH, WORLD_HEIGHT
from .utils import clamp


class Camera:
    def __init__(self, position):
        self.offset = self.target(position)

    @staticmethod
    def target(position):
        return pygame.Vector2(
            clamp(position.x - WIDTH / 2, 0, WORLD_WIDTH - WIDTH),
            clamp(position.y - HEIGHT / 2, 0, WORLD_HEIGHT - HEIGHT),
        )

    def update(self, position, dt):
        self.offset = self.offset.lerp(self.target(position), 1 - math.exp(-7 * dt))
