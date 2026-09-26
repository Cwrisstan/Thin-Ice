"""The existing Plowman is now a theatrical primitive model above the box.

Attack scheduling moved to patterns.py; he no longer chases the skater.
"""
import math
import pygame
from .settings import BOSS_MAX_HP, BOSS_RADIUS, BOSS_SPAWN


class Boss:
    def __init__(self):
        self.hp=BOSS_MAX_HP
        self.radius=BOSS_RADIUS
        self.position=pygame.Vector2(BOSS_SPAWN)
        self.state='IDLE'
        self.flash_timer=0
        self.reaction_timer=0
        self.attack_kind='traffic'
        self.breakdown=0

    def react(self,state,duration=.6):
        self.state=state
        self.reaction_timer=duration
        if state=='DAMAGED':
            self.flash_timer=.18

    def update(self,dt):
        self.flash_timer=max(0,self.flash_timer-dt)
        self.reaction_timer=max(0,self.reaction_timer-dt)
        if self.reaction_timer<=0:
            self.state='NEAR_DEATH' if self.hp<BOSS_MAX_HP*.22 else 'IDLE'

    def take_damage(self,damage,*,rhythm=False):
        if not rhythm or self.hp<=0:
            return 0
        dealt=min(self.hp,max(0,damage))
        self.hp-=dealt
        self.react('DAMAGED',.7)
        return dealt

    def draw(self,surface,time,box_width=540,center=None):
        # Draw at a local origin, then modestly scale with box width.
        canvas=pygame.Surface((380,225),pygame.SRCALPHA)
        angry=self.state=='ANGRY'
        revving=self.state=='REVVING'
        near=self.hp<BOSS_MAX_HP*.22
        broken=self.hp<=0
        bounce=math.sin(time*(21 if revving or angry else 5))*(3 if revving or angry else 1)
        if self.state=='DAMAGED': bounce+=math.sin(time*95)*5
        if self.state=='LAUGHING': bounce+=abs(math.sin(time*12))*5
        y=int(bounce)
        metal=(231,239,231) if self.flash_timer>0 else (94,114,127)
        # Pipes and exhaust; extra smoke when angry or close to failure.
        for x in (97,283):
            pygame.draw.rect(canvas,(80,95,104),(x,76+y,13,58),border_radius=3)
            pygame.draw.rect(canvas,(154,174,181),(x-3,75+y,19,8))
            for i in range(4 if angry or near or broken else 2):
                rise=(time*40+i*18)%66
                pygame.draw.circle(canvas,(74,87,95,max(0,int(135-rise))),(int(x+6+math.sin(time*3+i)*9),int(72+y-rise)),int(5+rise*.15))
        # Armored vehicle, treads, scrap seams and enormous plow.
        for x in (73, 265):

            # Square, brutal tread housing
            pygame.draw.rect(
                canvas,
                (24, 34, 40),
                (x, 115 + y, 44, 74),
            )

            pygame.draw.rect(
                canvas,
                (75, 94, 103),
                (x + 4, 119 + y, 36, 66),
                3,
            )

            # Individual chunky tread plates
            for tread_y in range(123, 182, 12):
                pygame.draw.rect(
                    canvas,
                    (104, 124, 132),
                    (x + 3, tread_y + y, 38, 6),
                )

                pygame.draw.rect(
                    canvas,
                    (44, 58, 64),
                    (x + 8, tread_y + 2 + y, 27, 2),
                )
        pygame.draw.polygon(canvas,metal,[(112,94+y),(265,94+y),(287,159+y),(247,184+y),(130,184+y),(95,150+y)])
        pygame.draw.rect(canvas,(41,62,76),(137,100+y,105,52),border_radius=5)
        pygame.draw.line(canvas,(186,141,86),(126,142+y),(257,142+y),5)
        for x in (119,257):
            for yy in (111,137,160): pygame.draw.circle(canvas,(166,182,184),(x,yy+y),3)
        # Operator: bulky coat, absurd shoulder armor, face and improvised crown.
        head_shift=math.sin(time*3)*2 if self.state!='STUNNED' else math.sin(time*15)*7
        pygame.draw.polygon(canvas,(91,67,65),[(145,91+y),(156,61+y),(222,61+y),(237,94+y)])
        pygame.draw.polygon(canvas,(155,171,177),[(137,72+y),(153,60+y),(168,75+y),(156,93+y)])
        pygame.draw.polygon(canvas,(155,171,177),[(215,75+y),(232,58+y),(246,75+y),(226,93+y)])
        hx=190+head_shift
        pygame.draw.circle(canvas,(189,160,128),(int(hx),48+y),19)
        pygame.draw.polygon(canvas,(104,125,140),[(hx-23,38+y),(hx-19,13+y),(hx-8,24+y),(hx+2,9+y),(hx+10,24+y),(hx+22,15+y),(hx+23,38+y)])
        pygame.draw.rect(canvas,(27,36,43),(hx-18,42+y,36,9))
        eyes=(255,132,85) if angry or near else (248,216,135)
        for x in (-9,9): pygame.draw.line(canvas,eyes,(hx+x-3,46+y),(hx+x+3,46+y),3)
        pygame.draw.line(canvas,(57,49,47),(hx-8,58+y),(hx+8,58+y),3)
        # Steering wheel held above the cab.
        pygame.draw.ellipse(canvas,(33,40,47),(167,81+y,47,15),4)
        for x in (163,214): pygame.draw.circle(canvas,(183,155,127),(x,85+y),7)
        # Headlights visibly fail at defeat and flicker near death.
        lamps=(255,249,177) if not broken and (not near or math.sin(time*20)>.1) else (58,69,70)
        for x in (121, 262):

            if angry and not broken:
                pygame.draw.rect(
                    canvas,
                    (178, 112, 59, 80),
                    (x - 17, 132 + y, 34, 34),
                )

            # Dark housing
            pygame.draw.rect(
                canvas,
                (32, 42, 45),
                (x - 13, 136 + y, 26, 26),
            )

            # Lamp
            pygame.draw.rect(
                canvas,
                lamps,
                (x - 9, 140 + y, 18, 18),
            )

            # Hot center
            if not broken:
                pygame.draw.rect(
                    canvas,
                    (255, 245, 189),
                    (x - 4, 145 + y, 8, 8),
                )
        slam=8*max(0,math.sin(time*14)) if revving and self.attack_kind=='wave' else 0
        # ======================================================
        # THE PLOW
        # ======================================================

        plow_points = [
            (48, 166 + y + slam),
            (190, 181 + y + slam),
            (330, 166 + y + slam),

            (314, 210 + y + slam),
            (190, 221 + y + slam),
            (64, 210 + y + slam),
        ]

        pygame.draw.polygon(
            canvas,
            (135, 164, 174),
            plow_points,
        )

        # Bright frozen upper edge
        pygame.draw.lines(
            canvas,
            (215, 231, 228),
            False,
            [
                (51, 169 + y + slam),
                (190, 185 + y + slam),
                (327, 169 + y + slam),
            ],
            5,
        )

        # Rust stripe
        pygame.draw.line(
            canvas,
            (145, 92, 67),
            (76, 193 + y + slam),
            (301, 193 + y + slam),
            5,
        )

        # Bolts
        for x in range(86, 310, 38):
            pygame.draw.rect(
                canvas,
                (63, 84, 92),
                (x, 181 + y + slam, 5, 5),
            )

        # Bottom teeth
        for x in range(74, 315, 30):
            pygame.draw.polygon(
                canvas,
                (79, 107, 117),
                [
                    (x, 205 + y + slam),
                    (x + 13, 207 + y + slam),
                    (x + 7, 220 + y + slam),
                ],
            )
        pygame.draw.lines(canvas,(228,240,242),False,[(55,171+y+slam),(190,185+y+slam),(323,171+y+slam)],4)
        for x in range(85,310,43): pygame.draw.line(canvas,(95,128,146),(x,180+y),(x-5,202+y),3)
        if near or broken:
            pygame.draw.lines(canvas,(21,32,39),False,[(214,100+y),(205,122+y),(225,133+y),(217,156+y)],4)
            for i in range(3):
                a=time*12+i*2
                start=pygame.Vector2(226,135+y)
                end=start+pygame.Vector2(math.cos(a)*18,math.sin(a)*14)
                pygame.draw.line(canvas,(255,208,113),start,end,2)
        if revving and self.attack_kind=='chain':
            for i in range(9):
                x=284+i*8; yy=111+y+math.sin(time*12+i*.4)*14
                pygame.draw.circle(canvas,(205,223,231),(int(x),int(yy)),5,2)
        if self.state=='STUNNED':
            for i in range(3): pygame.draw.circle(canvas,(251,224,137),(int(166+i*23),8+int(math.sin(time*9+i)*4)),4)
        scale=.79+.08*min(1,box_width/830)
        if broken: scale*=1-.05*min(1,self.breakdown)
        size=(int(380*scale),int(225*scale))
        model = pygame.transform.scale(canvas, size)
        point=pygame.Vector2(center or (500,136))
        if broken: point.x+=math.sin(time*70)*max(0,5-self.breakdown*2)
        surface.blit(model,model.get_rect(center=point))
