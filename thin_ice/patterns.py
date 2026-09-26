"""Handcrafted box hazards. Pattern owns time; GameManager owns damage.

No chasing boss AI. One deterministic schedule runs, then hazards are cleared
before the box contracts. Difficulty changes execution, never base damage.
"""
import pygame
from .combat import ENRAGE_SPEED
from .effects import IceChunk


class TrafficRow:
    kind='traffic'
    def __init__(self,box,gap_center,gap_width,speed,warning,major=False):
        self.box=box.copy()
        self.y=self.previous_y=box.top-32.0
        self.gap=gap_center
        self.gap_width=gap_width
        self.speed=speed
        self.warning=warning
        self.major=major
        self.resolved=False
        self.life=10

    @property
    def blocks(self):
        left=self.gap-self.gap_width/2
        right=self.gap+self.gap_width/2
        return [pygame.Rect(self.box.left,self.y,max(0,left-self.box.left),28),pygame.Rect(right,self.y,max(0,self.box.right-right),28)]

    def update(self,dt,player):
        self.previous_y=self.y
        if self.warning>0:
            self.warning-=dt
            return
        self.y+=self.speed*dt
        if self.y>self.box.bottom+40: self.life=0

    def draw(self,surface,time):
        if self.warning>0:
            pygame.draw.line(surface,(163,203,218),(self.gap-self.gap_width/2,self.box.top+12),(self.gap+self.gap_width/2,self.box.top+12),4)
            return
        for rect in self.blocks:
            pygame.draw.rect(surface,(120,147,161),rect,border_radius=3)
            pygame.draw.line(surface,(219,235,235),rect.topleft,rect.topright,3)
            for x in range(rect.left+12,rect.right-5,36):
                pygame.draw.line(surface,(51,75,91),(x,rect.y+7),(x+12,rect.y+21),5)


class Pattern:
    def __init__(self,name,box,difficulty,enraged=False,escalation=0):
        self.name=name
        self.box=box.copy()
        self.difficulty=difficulty
        self.speed_scale=difficulty.attack_speed*(ENRAGE_SPEED if enraged else 1)
        self.warning_scale=difficulty.telegraph_scale/(1.1 if enraged else 1)
        self.density=difficulty.density+(1 if enraged else 0)
        self.escalation=escalation
        self.elapsed=0
        self.duration={'traffic':8.8,'chain':7.8,'wave':8.4,'whiteout':9.3,'swarm':8.7}[name]
        self.hazards=[]
        self.spawned=0
        self.early_end=False
        self.counter_count=0
        self.rail_time=0
        self.swarm_scattered=False
        self.extra_spawned=False
        self.schedule={
            'traffic': (.7, 2.5, 4.3, 6.1, 7.5)[:3 if self.density <= 3 else 4 if self.density <= 5 else 5],            'chain':(.4,2.6,4.8) if self.density<7 else (.4,2.1,3.8,5.5),
            'wave':(.4,),
            'whiteout':(.4,1.8,3.2,4.6,5.8)[:4 if self.density<=3 else 5],
            'swarm':(1.0,),
        }[name]

    @property
    def done(self):
        completed=self.spawned==len(self.schedule) and not self.hazards and self.elapsed>=6
        return self.early_end or self.elapsed>=self.duration or completed or (self.swarm_scattered and self.elapsed>=6.2)

    def spawn(self,index):
        box=self.box
        if self.name=='traffic':
            fraction = (.30, .62, .42, .68, .34)[index]
            self.hazards.append(TrafficRow(box,box.left+box.width*fraction,self.difficulty.traffic_gap,130*self.speed_scale,.7*self.warning_scale,index==len(self.schedule)-1))
            if self.escalation and index%2==1:
                self.hazards.append(Shard((box.left+box.width*fraction,box.top-15),(0,165*self.speed_scale),box,1.1,parryable=True))
        elif self.name=='chain':
            self.hazards.append(Sweep(box,420*self.speed_scale,.85*self.warning_scale,reverse=index%2==1))
        elif self.name=='wave':
            self.hazards.append(Sweep(box,130*self.speed_scale,max(2.1,2.2*self.warning_scale),tall=True))
        elif self.name=='whiteout':
            # Alternating edge volleys with a deliberately omitted lane.
            horizontal=index%4>=2 and self.density>=7
            count=self.density+2
            gap_index=(index*2+1)%count
            for i in range(count):
                if abs(i-gap_index)<=0:continue
                fraction=(i+.5)/count
                parryable=i%3==1
                if horizontal:
                    start=(box.left-14 if index%2==0 else box.right+14,box.top+box.height*fraction)
                    velocity=(185*self.speed_scale*(1 if index%2==0 else -1),(-1 if index%2 else 1)*22)
                else:
                    start=(box.left+box.width*fraction,box.top-14 if index%2==0 else box.bottom+14)
                    velocity=((1 if index%2==0 else -1)*22,185*self.speed_scale*(1 if index%2==0 else -1))
                self.hazards.append(Shard(start,velocity,box,.62*self.warning_scale,parryable,major=parryable and index==len(self.schedule)-1))
        elif self.name=='swarm':
            for i in range(self.density+3):
                start=pygame.Vector2(box.left+35+i*(box.width-70)/(self.density+2),box.top-12)
                self.hazards.append(Shard(start,(0,210*self.speed_scale),box,.85*self.warning_scale,parryable=i%4==0,homing=True))

    def update(self,dt,player):
        self.elapsed+=dt
        while self.spawned<len(self.schedule) and self.elapsed>=self.schedule[self.spawned]:
            self.spawn(self.spawned)
            self.spawned+=1
        # Sparse low-health remixes arrive after the main low sweep/wave has passed.
        if self.escalation>=2 and self.name in ('chain','wave') and self.elapsed>6.8 and not self.extra_spawned:
            self.extra_spawned=True
            self.hazards.append(Shard((self.box.left+25,self.box.top-12),(85,150),self.box,.65,parryable=True))
        for hazard in self.hazards:hazard.update(dt,player)
        if self.name=='swarm' and not self.swarm_scattered:
            pursuing=any(h.kind=='shard' and h.warning<=0 and h.life>0 and h.position.distance_to(player.position)<290 for h in self.hazards)
            self.rail_time=self.rail_time+dt if player.rail is not None and pursuing else 0
            if self.rail_time>=.4:
                self.swarm_scattered=True
                for h in self.hazards:h.life=0
        self.hazards[:]=[h for h in self.hazards if h.life>0]


class Sweep:
    def __init__(self,box,speed,warning,tall=False,reverse=False):
        self.kind='wave' if tall else 'chain'
        self.box=box.copy()
        self.y=self.previous_y=float(box.bottom+25 if reverse else box.top-25)
        self.speed=-speed if reverse else speed
        self.warning=warning
        self.resolved=False
        self.life=12

    def update(self,dt,player):
        self.previous_y=self.y
        if self.warning>0:
            self.warning-=dt
            return
        self.y+=self.speed*dt
        if self.y>self.box.bottom+40 or self.y<self.box.top-40:self.life=0

    def draw(self,surface,time):
        if self.warning>0:
            y=self.box.bottom-7 if self.speed<0 else self.box.top+7
            color=(172,225,239) if self.kind=='chain' else (227,233,190)
            for x in range(self.box.left+8,self.box.right-8,26):
                pygame.draw.line(surface,color,(x,y),(x+14,y),3)
            return
        if self.kind=='wave':
            pygame.draw.rect(surface,(83,163,190),(self.box.left,self.y-14,self.box.width,28))
            for x in range(self.box.left,self.box.right,32):
                pygame.draw.polygon(surface,(192,238,248),[(x,self.y-12),(x+16,self.y+26),(x+30,self.y-12)])
            pygame.draw.line(surface,(240,250,251),(self.box.left,self.y-14),(self.box.right,self.y-14),3)
        else:
            pygame.draw.line(surface,(151,196,214),(self.box.left,self.y),(self.box.right,self.y),4)
            for x in range(self.box.left,self.box.right,22):
                pygame.draw.ellipse(surface,(216,236,245),(x,self.y-6,17,12),2)


class Shard(IceChunk):
    kind='shard'
    def __init__(self,position,velocity,box,warning=.5,parryable=False,homing=False,major=False):
        super().__init__(position,velocity)
        self.box=box.copy()
        self.warning=warning
        self.parryable=parryable
        self.homing=homing
        self.major=major
        self.life=6 if homing else 3.7
        self.flash=False

    def update(self,dt,player):
        self.previous=self.position.copy()
        if self.warning>0:
            self.warning-=dt
            return
        super().update(dt,player)
        self.flash=self.parryable and self.position.distance_to(player.position)<145
        if not self.homing and not self.box.inflate(90,90).collidepoint(self.position):self.life=0

    def draw(self,surface,time):
        if self.warning>0:
            p=pygame.Vector2(max(self.box.left+5,min(self.box.right-5,self.position.x)),max(self.box.top+5,min(self.box.bottom-5,self.position.y)))
            pygame.draw.circle(surface,(235,210,137) if self.parryable else (100,166,191),p,5,1)
            return
        p=self.position
        color=(246,215,137) if self.parryable else (139,213,238)
        if self.flash and int(time*16)%2==0:color=(255,252,222)
        pygame.draw.line(surface,(62,101,123),p-self.velocity*.055,p,3)
        pygame.draw.polygon(surface,color,[p+(-9,0),p+(0,-9),p+(10,0),p+(0,9)])
        if self.parryable:pygame.draw.circle(surface,(255,238,175),p,13,1)
