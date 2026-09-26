"""Player movement, combat, and rendering."""

import math
import random

import pygame

from .effects import Particle, SlashEffect, spray
from .settings import (
    ACCELERATION, BRAKE_FRICTION, COAST_FRICTION,
    MAX_SPEED, PLAYER_MAX_HP, PLAYER_RADIUS, TURN_SPEED, VELOCITY_CARVE_STRENGTH,
    SPAWN, WORLD_WIDTH, WORLD_HEIGHT, MAX_STAMINA, JUMP_COST, DODGE_COST,
    SLASH_COST, JUMP_DURATION, PARRY_WINDOW, PARRY_RECOVERY, DODGE_DURATION,
    STAMINA_DELAY,
)
from .utils import clamp, direction_from_angle


class Player:
    def __init__(self, position=SPAWN):
        self.position = pygame.Vector2(position)
        self.bounds = pygame.Rect(0, 0, WORLD_WIDTH, WORLD_HEIGHT)

        self.velocity = pygame.Vector2()

        # Facing upward initially
        self.angle = 0

        self.hp = PLAYER_MAX_HP
        self.stamina = MAX_STAMINA
        self.regen_delay = 0
        self.jump_remaining = 0
        self.jump_duration = JUMP_DURATION
        self.jump_height = 44
        self.parry_timer = 0
        self.parry_lock = 0
        self.dodge_timer = 0
        self.dodge_cooldown = 0
        self.dodge_direction = pygame.Vector2(1, 0)
        self.hit_flash = 0
        self.ramp_bonus = False
        self.rail_bonus = 0
        self.rail = None
        self.rail_direction = 1
        self.rail_cooldown = 0

        self.attack_cooldown = 0
        self.toe_pick_cooldown = 0

        self.invulnerability = 0

        self.last_trail_position = pygame.Vector2(self.position)

    @property
    def speed(self):
        return self.velocity.length()

    @property
    def facing(self):
        return direction_from_angle(self.angle)

    def update(self, dt, keys, trail_surface, particles):
        # ----------------------------------------------------
        # Timers
        # ----------------------------------------------------

        for name in ("attack_cooldown", "toe_pick_cooldown", "invulnerability",
                     "regen_delay", "parry_timer", "parry_lock", "dodge_timer",
                     "dodge_cooldown", "hit_flash", "rail_bonus", "rail_cooldown"):
            setattr(self, name, max(0, getattr(self, name) - dt))
        was_airborne = self.airborne
        self.jump_remaining = max(0, self.jump_remaining - dt)
        if was_airborne and not self.airborne:
            self.ramp_bonus = False
            spray(particles, self.position, 10, 90)
        if self.regen_delay <= 0:
            self.stamina = min(MAX_STAMINA, self.stamina + (15 + 12 * min(1, self.speed / MAX_SPEED)) * dt)
        if self.parry_lock > 0:
            self.velocity.update(0, 0)
            return
        if self.rail is not None:
            start, end = self.rail
            tangent = (end - start).normalize()
            speed = min(620, max(250, self.speed) + 65 * dt)
            self.velocity = tangent * self.rail_direction * speed
            old_position = self.position.copy()
            self.position += self.velocity * dt
            self.angle = math.atan2(self.velocity.y, self.velocity.x)
            self.stamina = min(MAX_STAMINA, self.stamina + 20 * dt)
            pygame.draw.line(trail_surface, (209, 230, 232, 110), old_position, self.position, 2)
            progress = (self.position-start).dot(tangent)
            if progress < 0 or progress > start.distance_to(end):
                self.leave_rail()
            return

        # ----------------------------------------------------
        # Turning
        # ----------------------------------------------------

        turn_input = 0

        if keys[pygame.K_a]:
            turn_input -= 1

        if keys[pygame.K_d]:
            turn_input += 1

        speed_ratio = clamp(
            self.speed / MAX_SPEED,
            0,
            1,
        )

        # Slightly harder to turn at high speeds
        turn_modifier = 1 - 0.35 * speed_ratio

        self.angle += (
            turn_input
            * TURN_SPEED
            * turn_modifier
            * dt
        )

        # ----------------------------------------------------
        # Acceleration
        # ----------------------------------------------------

        if keys[pygame.K_w]:
            self.velocity += (
                self.facing
                * ACCELERATION
                * dt
            )

        # ----------------------------------------------------
        # Carving
        # ----------------------------------------------------

        # Velocity slowly rotates toward facing direction.
        # This creates the drifting/skating feeling.

        if self.speed > 10 and turn_input != 0:

            desired_velocity = (
                self.facing * self.speed
            )

            carve_amount = (
                VELOCITY_CARVE_STRENGTH
                * dt
            )

            self.velocity = self.velocity.lerp(
                desired_velocity,
                clamp(carve_amount, 0, 1),
            )

        # ----------------------------------------------------
        # Brake
        # ----------------------------------------------------

        braking = keys[pygame.K_s] and not self.airborne

        if braking:
            friction = BRAKE_FRICTION

            # Ice spray
            if self.speed > 80:

                for _ in range(2):

                    sideways = self.facing.rotate(
                        random.choice([-90, 90])
                    )

                    velocity = (
                        -self.velocity * 0.25
                        + sideways
                        * random.uniform(40, 120)
                    )

                    particles.append(
                        Particle(
                            self.position,
                            velocity,
                            life=random.uniform(0.25, 0.5),
                            radius=random.randint(2, 5),
                        )
                    )

        else:
            friction = COAST_FRICTION

        self.velocity *= max(
            0,
            1 - friction * dt,
        )

        # ----------------------------------------------------
        # Maximum speed
        # ----------------------------------------------------

        if self.dodge_timer > 0:
            self.velocity = self.dodge_direction * 820

        if self.speed > MAX_SPEED and self.dodge_timer <= 0 and not self.airborne:
            self.velocity.scale_to_length(
                MAX_SPEED
            )

        # ----------------------------------------------------
        # Position
        # ----------------------------------------------------

        old_position = pygame.Vector2(
            self.position
        )

        self.position += self.velocity * dt

        # ----------------------------------------------------
        # Arena boundary
        # ----------------------------------------------------

        self.constrain_to_world()

        # ----------------------------------------------------
        # Permanent skate trail
        # ----------------------------------------------------

        if not self.airborne and old_position.distance_to(
            self.position
        ) > 1:

            trail_color = (
                165,
                205,
                220,
                80,
            )

            pygame.draw.line(
                trail_surface,
                trail_color,
                old_position,
                self.position,
                2,
            )

    @property
    def airborne(self):
        return self.jump_remaining > 0

    @property
    def height(self):
        if not self.airborne:
            return 0
        return self.jump_height * math.sin(math.pi * (1 - self.jump_remaining / self.jump_duration))

    def constrain_to_world(self):
        # Reflect only the outward component; keep tangential skating momentum.
        for axis, minimum, maximum in (("x", self.bounds.left, self.bounds.right), ("y", self.bounds.top, self.bounds.bottom)):
            value = getattr(self.position, axis)
            bounded = clamp(value, minimum + PLAYER_RADIUS + 5, maximum - PLAYER_RADIUS - 5)
            if value != bounded:
                setattr(self.position, axis, bounded)
                velocity = getattr(self.velocity, axis)
                if (value < bounded and velocity < 0) or (value > bounded and velocity > 0):
                    setattr(self.velocity, axis, -velocity * 0.65)
                    if self.dodge_timer > 0:
                        setattr(self.dodge_direction, axis, -getattr(self.dodge_direction, axis))

    def spend_stamina(self, cost):
        if self.stamina < cost:
            return False
        self.stamina -= cost
        self.regen_delay = STAMINA_DELAY
        return True

    def jump(self):
        if self.airborne or self.parry_lock > 0 or self.dodge_timer > 0:
            return False
        if not self.spend_stamina(JUMP_COST):
            return False
        self.launch()
        return True

    def launch(self, duration=JUMP_DURATION, height=44, ramp=False):
        if self.rail is not None:
            self.leave_rail()
        self.jump_duration = duration
        self.jump_remaining = duration
        self.jump_height = height
        self.ramp_bonus = ramp

    def dodge(self):
        if self.dodge_cooldown > 0 or self.parry_lock > 0 or self.airborne:
            return False
        if not self.spend_stamina(DODGE_COST):
            return False
        if self.rail is not None:
            self.leave_rail()
        self.dodge_direction = self.velocity.normalize() if self.speed > 30 else self.facing
        self.velocity = self.dodge_direction * 820
        self.dodge_timer = DODGE_DURATION
        self.dodge_cooldown = 0.5
        return True

    def toe_pick(self, particles):
        if self.toe_pick_cooldown > 0 or self.airborne or self.dodge_timer > 0:
            return False
        if self.rail is not None:
            self.leave_rail(bonus=False)
        self.velocity.update(0, 0)
        self.parry_timer = PARRY_WINDOW
        self.parry_lock = PARRY_RECOVERY
        self.toe_pick_cooldown = 0.85
        spray(particles, self.position, 9, 100)
        return True

    def leave_rail(self, bonus=True):
        self.rail = None
        self.rail_cooldown = .8
        self.rail_bonus = 1.35 if bonus else 0

    def attack(self, boss, slash_effects):
        if self.attack_cooldown > 0 or self.parry_lock > 0:
            return None
        if not self.spend_stamina(SLASH_COST):
            return None
        self.attack_cooldown = 0.48
        slash_effects.append(SlashEffect(self.position - pygame.Vector2(0, self.height), self.angle))
        if self.position.distance_to(boss.position) > 76 + boss.radius:
            return None
        speed_ratio = clamp(self.speed / MAX_SPEED, 0, 1)
        damage = 6 + 64 * speed_ratio ** 2
        label = ""
        if self.airborne:
            progress = 1 - self.jump_remaining / self.jump_duration
            damage *= 1.15 + 0.30 * math.sin(math.pi * progress) + 0.20 * speed_ratio
            label = "AIR EDGE"
        if self.airborne and self.ramp_bonus:
            damage *= 1.5
            label = "RAMP ATTACK x1.5"
        if self.rail_bonus > 0:
            damage *= 1.3
            label = "RAIL EDGE x1.3"
            self.rail_bonus = 0
        dealt = boss.take_damage(damage)
        return dealt, label

    def take_damage(self, damage, *, ignore_dodge=False):
        if self.invulnerability > 0 or (self.dodge_timer > 0 and not ignore_dodge):
            return False
        self.hp = max(0, self.hp - damage)
        self.invulnerability = 0.65
        self.hit_flash = 0.18
        return True

    def draw(self, surface, offset):
        ground = self.position - offset
        p = ground - pygame.Vector2(0, self.height)

        # Visual size only — does NOT affect collisions.
        VISUAL_SCALE = 1.4

        # ======================================================
        # SHADOW
        # ======================================================

        shadow_width = 34 if not self.airborne else 26
        shadow_height = 11 if not self.airborne else 8

        pygame.draw.ellipse(
            surface,
            (12, 27, 34),
            (
                int(ground.x - shadow_width / 2),
                int(ground.y - shadow_height / 2),
                shadow_width,
                shadow_height,
            ),
        )

        # ======================================================
        # SKATER ORIENTATION
        # ======================================================

        forward = self.facing

        if forward.length_squared() == 0:
            forward = pygame.Vector2(0, -1)

        forward = forward.normalize()
        side = pygame.Vector2(-forward.y, forward.x)

        # Lean harder when moving quickly.
        speed_lean = min(4, self.speed / 130)

        body_center = (
                p
                - forward * 3
                + side * math.sin(self.angle * 2) * speed_lean * 0.2
        )

        # ======================================================
        # SKATES
        # ======================================================

        skate_back = body_center - forward * 13

        left_skate = skate_back - side * 7
        right_skate = skate_back + side * 7

        blade_color = (198, 218, 219)
        boot_color = (32, 43, 48)

        for skate in (left_skate, right_skate):
            pygame.draw.line(
                surface,
                boot_color,
                skate - forward * 4,
                skate + forward * 5,
                5,
            )

            pygame.draw.line(
                surface,
                blade_color,
                skate - forward * 7 + side * 3,
                skate + forward * 6 + side * 2,
                2,
            )

        # ======================================================
        # LEGS
        # ======================================================

        hip = body_center + forward * 2

        pygame.draw.line(
            surface,
            (43, 61, 67),
            hip,
            left_skate,
            5,
        )

        pygame.draw.line(
            surface,
            (43, 61, 67),
            hip,
            right_skate,
            5,
        )

        # ======================================================
        # WINTER COAT
        # ======================================================

        coat_color = (65, 126, 142)

        if self.hit_flash > 0:
            coat_color = (224, 103, 108)

        elif self.dodge_timer > 0:
            coat_color = (197, 220, 213)

        body_front = body_center + forward * 10
        body_back = body_center - forward * 8

        coat_points = [
            body_front + side * 10,
            body_front - side * 10,
            body_back - side * 11,
            body_back + side * 11,
        ]

        pygame.draw.polygon(
            surface,
            coat_color,
            coat_points,
        )

        # Dark coat outline
        pygame.draw.lines(
            surface,
            (25, 52, 60),
            True,
            coat_points,
            4,
        )

        # ======================================================
        # SCARF
        # ======================================================

        scarf_base = body_front - forward * 1

        pygame.draw.line(
            surface,
            (198, 104, 77),
            scarf_base - side * 6,
            scarf_base + side * 6,
            4,
        )

        # Scarf tail blows opposite movement/facing.
        scarf_tail = body_back - forward * 9 + side * 5

        pygame.draw.line(
            surface,
            (198, 104, 77),
            body_back + side * 4,
            scarf_tail,
            4,
        )

        # ======================================================
        # HEAD + HOOD
        # ======================================================

        head = body_center + forward * 17
        pygame.draw.circle(
            surface,
            (32, 58, 65),
            (int(head.x), int(head.y)),
            11,
        )

        pygame.draw.circle(
            surface,
            (183, 151, 123),
            (int(head.x), int(head.y)),
            7,
        )

        # Hood highlight
        pygame.draw.line(
            surface,
            (102, 163, 171),
            head - side * 5 - forward * 3,
            head + side * 5 - forward * 3,
            2,
        )

        # ======================================================
        # FACING / SKATE DIRECTION DETAIL
        # ======================================================

        nose = head + forward * 10

        pygame.draw.rect(
            surface,
            (221, 190, 145),
            (
                int(nose.x - 1),
                int(nose.y - 1),
                4,
                4,
            ),
        )

        def visual(point):
            """Scale a point outward from the player's center."""
            point = pygame.Vector2(point)
            return p + (point - p) * VISUAL_SCALE

        # ======================================================
        # PARRY
        # ======================================================

        if self.parry_timer > 0:

            pygame.draw.circle(
                surface,
                (242, 211, 118),
                (int(p.x), int(p.y)),
                20,
                3,
            )

            # Little spark blocks
            for direction in (
                    pygame.Vector2(1, 0),
                    pygame.Vector2(-1, 0),
                    pygame.Vector2(0, 1),
                    pygame.Vector2(0, -1),
            ):
                spark = p + direction * 23

                pygame.draw.rect(
                    surface,
                    (255, 236, 166),
                    (
                        int(spark.x - 2),
                        int(spark.y - 2),
                        4,
                        4,
                    ),
                )

        # ======================================================
        # FAILED / RECOVERING PARRY
        # ======================================================

        elif self.parry_lock > 0:

            pygame.draw.line(
                surface,
                (220, 113, 89),
                p + (-9, 17),
                p + (9, 17),
                3,
            )
