"""The old world is now a bounded, smoothly morphing ice battle box.

Traversal retains the prototype's ramp launch and automatic grind behavior.
Only the current pattern installs a ramp or rail; there is no overworld.
"""
import math
import pygame
from .combat import MENU_BOX, RESIZE_SECONDS
from .utils import clamp, draw_text, segment_distance


class BattleBox:
    def __init__(self):
        self.rect=pygame.Rect(MENU_BOX)
        self.start=list(MENU_BOX)
        self.target=self.start.copy()
        self.elapsed=RESIZE_SECONDS
        self.ramps=[]
        self.rail=None
        self.font=pygame.font.Font(None,21)

    @property
    def morphing(self):
        return self.elapsed<RESIZE_SECONDS

    def morph(self,rect):
        self.start=list(self.rect)
        self.target=list(rect)
        self.elapsed=0
        self.ramps=[]
        self.rail=None

    def update(self,dt,player):
        old=self.rect.copy()
        if self.morphing:
            self.elapsed=min(RESIZE_SECONDS,self.elapsed+dt)
            t=self.elapsed/RESIZE_SECONDS
            t=t*t*(3-2*t)  # Smoothstep: ease both ends, no box snapping.
            values=[a+(b-a)*t for a,b in zip(self.start,self.target)]
            self.rect=pygame.Rect(*(round(v) for v in values))
            # Carry the skater's relative place through the resize; velocity survives.
            u=clamp((player.position.x-old.left)/max(1,old.width),0,1)
            v=clamp((player.position.y-old.top)/max(1,old.height),0,1)
            player.position.update(self.rect.left+u*self.rect.width,self.rect.top+v*self.rect.height)
        player.bounds=self.rect.copy()
        player.constrain_to_world()

    def install(self,name):
        self.ramps=[]; self.rail=None
        if name=='wave':
            self.ramps=[pygame.Rect(self.rect.centerx-70,self.rect.centery-20,140,60)]
        elif name=='swarm':
            self.rail=(pygame.Vector2(self.rect.left+65,self.rect.centery+25),pygame.Vector2(self.rect.right-65,self.rect.centery+25))

    def update_traversal(self,player,previous):
        if player.airborne or player.parry_lock>0 or player.dodge_timer>0 or player.rail is not None:
            return None
        if player.speed>=250:
            for ramp in self.ramps:
                if ramp.clipline(previous,player.position) or ramp.collidepoint(player.position):
                    player.launch(1.35,90,ramp=True)
                    return 'RAMP LAUNCH'
        if self.rail and player.speed>=230 and player.rail_cooldown<=0:
            start,end=self.rail
            tangent=(end-start).normalize()
            aligned=player.velocity.normalize().dot(tangent)
            if abs(aligned)>.9 and segment_distance(player.position,start,end)<20:
                along=clamp((player.position-start).dot(tangent),0,start.distance_to(end))
                if (aligned>0 and along>=start.distance_to(end)-10) or (aligned<0 and along<=10):
                    return None
                player.position=start+tangent*along
                player.rail=self.rail
                player.rail_direction=1 if aligned>0 else -1
                player.velocity=tangent*player.rail_direction*player.speed
                return 'GRIND / SPACE TO JUMP OFF'
        return None

    def draw(self, surface, time):
        rect = self.rect

        # ------------------------------------------------------
        # SHADOW
        # Gives the arena a little RPG-panel depth.
        # ------------------------------------------------------

        shadow = rect.move(7, 8)

        pygame.draw.rect(
            surface,
            (5, 12, 17),
            shadow,
        )

        # ------------------------------------------------------
        # DARK FROZEN FLOOR
        # ------------------------------------------------------

        pygame.draw.rect(
            surface,
            (17, 35, 44),
            rect,
        )

        # Inner icy tint
        inner = rect.inflate(-10, -10)

        pygame.draw.rect(
            surface,
            (24, 48, 57),
            inner,
        )

        # ------------------------------------------------------
        # SUBTLE ICE STRIPES
        # ------------------------------------------------------

        old_clip = surface.get_clip()
        surface.set_clip(inner)

        for i in range(7):
            y = (
                    rect.top
                    + 25
                    + i * 47
                    + int(math.sin(time * 0.35 + i) * 3)
            )

            pygame.draw.line(
                surface,
                (35, 65, 74),
                (rect.left + 15, y),
                (rect.right - 15, y - 13),
                2,
            )

        # Tiny cracks inside arena
        for i in range(5):
            x = rect.left + 55 + i * 113
            y = rect.top + 70 + (i % 3) * 55

            pygame.draw.lines(
                surface,
                (13, 31, 39),
                False,
                [
                    (x, y),
                    (x + 12, y + 9),
                    (x + 7, y + 21),
                    (x + 20, y + 31),
                ],
                2,
            )

        surface.set_clip(old_clip)

        # ------------------------------------------------------
        # CHUNKY ICE BORDER
        # ------------------------------------------------------

        pygame.draw.rect(
            surface,
            (116, 164, 176),
            rect,
            6,
        )

        pygame.draw.rect(
            surface,
            (190, 211, 211),
            rect,
            2,
        )

        # Highlight along top/left edges
        pygame.draw.line(
            surface,
            (216, 226, 218),
            (rect.left + 5, rect.top + 5),
            (rect.right - 5, rect.top + 5),
            2,
        )

        pygame.draw.line(
            surface,
            (180, 207, 207),
            (rect.left + 5, rect.top + 5),
            (rect.left + 5, rect.bottom - 5),
            2,
        )

        # ------------------------------------------------------
        # ICE CHUNKS AROUND BORDER
        # ------------------------------------------------------

        chunk_positions = [
            (rect.left + 30, rect.top),
            (rect.left + 110, rect.top),
            (rect.right - 75, rect.top),

            (rect.left + 60, rect.bottom),
            (rect.right - 130, rect.bottom),

            (rect.left, rect.top + 60),
            (rect.left, rect.bottom - 70),

            (rect.right, rect.top + 90),
            (rect.right, rect.bottom - 45),
        ]

        for i, (x, y) in enumerate(chunk_positions):
            size = 5 + (i % 3) * 2

            pygame.draw.rect(
                surface,
                (157, 192, 198),
                (
                    int(x - size / 2),
                    int(y - size / 2),
                    size,
                    size,
                ),
            )
        # ======================================================
        # SPECIAL TRAVERSAL OBJECTS
        # ======================================================

        # ------------------------------------------------------
        # GLACIAL WAVE RAMPS
        # ------------------------------------------------------

        for ramp in self.ramps:

            # Shadow
            pygame.draw.rect(
                surface,
                (8, 20, 27),
                ramp.move(5, 6),
            )

            # Main frozen ramp
            pygame.draw.rect(
                surface,
                (91, 137, 150),
                ramp,
            )

            # Snow / ice border
            pygame.draw.rect(
                surface,
                (199, 222, 221),
                ramp,
                5,
            )

            # Direction arrows
            for x in (25, 65, 105):
                p = pygame.Vector2(
                    ramp.x + x,
                    ramp.centery
                )

                pygame.draw.lines(
                    surface,
                    (232, 211, 133),
                    False,
                    [
                        p + (-8, -12),
                        p + (5, 0),
                        p + (-8, 12),
                    ],
                    4,
                )

            draw_text(
                surface,
                "RAMP / SPEED 250+",
                self.font,
                (ramp.centerx, ramp.y - 16),
                (232, 211, 133),
                center=True,
            )

        # ------------------------------------------------------
        # ICE SWARM GRIND RAIL
        # ------------------------------------------------------

        if self.rail:

            start, end = self.rail

            # Rail shadow
            pygame.draw.line(
                surface,
                (8, 19, 25),
                start + pygame.Vector2(0, 7),
                end + pygame.Vector2(0, 7),
                9,
            )

            # Dark metal body
            pygame.draw.line(
                surface,
                (83, 111, 119),
                start,
                end,
                7,
            )

            # Frozen-metal highlight
            pygame.draw.line(
                surface,
                (225, 216, 157),
                start,
                end,
                3,
            )

            # Supports
            direction = end - start

            for amount in (0.18, 0.5, 0.82):
                point = start + direction * amount

                pygame.draw.line(
                    surface,
                    (71, 91, 96),
                    point,
                    point + pygame.Vector2(0, 18),
                    5,
                )

                pygame.draw.line(
                    surface,
                    (71, 91, 96),
                    point + pygame.Vector2(-8, 18),
                    point + pygame.Vector2(8, 18),
                    4,
                )

            draw_text(
                surface,
                "GRIND / ALIGN + SPEED 230+",
                self.font,
                (
                    self.rect.centerx,
                    start.y + 28,
                ),
                (232, 211, 133),
                center=True,
            )


def draw_beacon(surface,position,time,strength=0):
    p=pygame.Vector2(position)
    pygame.draw.ellipse(surface,(37,43,44),(p.x-24,p.y+12,48,15))
    pygame.draw.rect(surface,(100,70,52),(p.x-16,p.y-12,32,37),border_radius=4)
    for y in (-5,13):
        pygame.draw.line(surface,(179,140,91),p+(-16,y),p+(16,y),3)
    height=30+min(28,strength*2)+math.sin(time*16)*4
    pygame.draw.polygon(surface,(239,128,63),[p+(-15,-10),p+(-6,-height),p+(0,-22),p+(9,-height-8),p+(15,-10)])
    pygame.draw.polygon(surface,(255,231,151),[p+(-8,-10),p+(0,-height+7),p+(8,-10)])
