"""Shared math and text drawing helpers."""

import math

import pygame


def clamp(value, minimum, maximum):
    return max(minimum, min(value, maximum))


def direction_from_angle(angle):
    return pygame.Vector2(math.cos(angle), math.sin(angle))


def draw_text(surface, text, font, position, color=(240, 245, 255), center=False):
    img = font.render(text, True, color)

    rect = img.get_rect()

    if center:
        rect.center = position
    else:
        rect.topleft = position

    surface.blit(img, rect)


def segment_distance(point, start, end):
    """Distance to a swept movement segment, avoiding fast-object tunneling."""
    delta = end - start
    if delta.length_squared() < 0.0001:
        return point.distance_to(start)
    t = clamp((point - start).dot(delta) / delta.length_squared(), 0, 1)
    return point.distance_to(start + delta * t)
