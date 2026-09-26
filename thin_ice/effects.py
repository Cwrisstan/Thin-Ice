"""World-space particles, slash effects, ice projectiles, and combat text."""

import pygame

import math
import random

from .utils import draw_text


class Particle:
    def __init__(
        self,
        position,
        velocity,
        life=0.5,
        radius=4,
        color=(220, 245, 255),
    ):
        self.position = pygame.Vector2(position)
        self.velocity = pygame.Vector2(velocity)

        self.life = life
        self.max_life = life

        self.radius = radius
        self.color = color

    def update(self, dt):
        self.position += self.velocity * dt

        self.velocity *= max(0, 1 - 2.5 * dt)

        self.life -= dt

    def draw(self, surface, offset):
        if self.life <= 0:
            return

        ratio = self.life / self.max_life

        radius = max(1, int(self.radius * ratio))

        pygame.draw.circle(
            surface,
            self.color,
            self.position - offset,
            radius,
        )


class SlashEffect:
    def __init__(self, position, angle, radius=45, life=.16):
        self.position = pygame.Vector2(position)
        self.angle = angle

        self.radius = radius
        self.life = life
        self.max_life = self.life

    def update(self, dt):
        self.life -= dt

    def draw(self, surface, offset):
        if self.life <= 0:
            return

        radius = self.radius

        start_angle = -self.angle - 0.8
        end_angle = -self.angle + 0.8

        rect = pygame.Rect(
            self.position.x - offset.x - radius,
            self.position.y - offset.y - radius,
            radius * 2,
            radius * 2,
        )

        pygame.draw.arc(
            surface,
            (245, 250, 255),
            rect,
            start_angle,
            end_angle,
            5,
        )


def spray(particles, position, count=15, speed=180, color=(215, 244, 255)):
    for _ in range(count):
        angle = random.uniform(0, math.tau)
        velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * random.uniform(speed * .25, speed)
        particles.append(Particle(position, velocity, random.uniform(.2, .55), random.randint(2, 5), color))


class IceChunk:
    def __init__(self, position, velocity):
        self.position = pygame.Vector2(position)
        self.previous = pygame.Vector2(position)
        self.velocity = pygame.Vector2(velocity)
        self.life = 3.0
        self.radius = 9
        self.attack_id = 0
        self.homing = False

    def update(self, dt, player=None):
        self.previous = self.position.copy()
        if self.homing and player is not None:
            target = player.position-self.position
            if target.length_squared() > 1:
                speed = self.velocity.length()
                self.velocity = self.velocity.lerp(target.normalize()*speed, min(1, dt*1.4))
                if self.velocity.length_squared() > 1:
                    self.velocity.scale_to_length(speed)
        self.position += self.velocity * dt
        self.life -= dt

    def draw(self, surface, offset):
        p = self.position - offset
        pygame.draw.line(surface, (94, 163, 182), p-self.velocity*.04, p, 5)
        pygame.draw.polygon(surface, (255, 224, 134), [p+(-10, 0), p+(0, -7), p+(10, 0), p+(0, 7)])


class FloatingText:
    def __init__(self, position, text, color=(240, 249, 255)):
        self.position = pygame.Vector2(position)
        self.text = text
        self.color = color
        self.life = .9

    def update(self, dt):
        self.position.y -= 38 * dt
        self.life -= dt

    def draw(self, surface, offset, font):
        draw_text(surface, self.text, font, self.position-offset, self.color, center=True)
