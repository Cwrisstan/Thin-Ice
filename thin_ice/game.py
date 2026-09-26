"""Existing skating prototype, directed as a box-based turn battle.

Only BOSS_PHASE advances skating/hazards. Resizes are safe, hazard-free states.
ATTACK/HEAT share the timed-note engine; TAUNT is dialogue, never rhythm.
No defensive score exists: survival always earns a command turn.
"""
import copy
import math
import random
import textwrap
import pygame

from .boss import Boss
from .combat import (
    Phase,DIFFICULTIES,BOXES,MENU_BOX,HEAT_BOX,RHYTHM_BOX,PATTERN_ORDER,
    PATTERN_NAMES,PATTERN_HINTS,FLAVOR,DIALOGUE,TAUNTS,TYPEWRITER_SPEED,
    ATTACK_MAX_DAMAGE,HEAT_PERFECT_HP,HEAT_GOOD_HP,TAUNT_BONUS,
    RESULT_SECONDS,PERFECT_DODGE_WINDOW,
)
from .effects import Particle,SlashEffect,FloatingText,spray
from .patterns import Pattern
from .player import Player
from .rhythm import RhythmSequence,INPUTS
from .settings import WIDTH,HEIGHT,BOSS_MAX_HP,PLAYER_MAX_HP,MAX_STAMINA,DODGE_DURATION,PLAYER_RADIUS
from .utils import clamp,draw_text,segment_distance
from .world import BattleBox,draw_beacon
from .music import MusicManager


class GameManager:
    def __init__(self):
        self.font=pygame.font.Font(None,29)
        self.small_font=pygame.font.Font(None,22)
        self.big_font=pygame.font.Font(None,64)
        self.difficulty=None
        self.music = MusicManager()
        self.reset()

    def reset(self):
        """The flame is the fight checkpoint. Keep difficulty, reset everything else."""
        self.box=BattleBox()
        self.checkpoint=pygame.Vector2(self.box.rect.center)
        self.player=Player(self.checkpoint)
        self.player.bounds=self.box.rect.copy()
        self.boss=Boss()
        self.state=Phase.INTRO if self.difficulty else Phase.DIFFICULTY_SELECT
        self.time=0
        self.turn=0
        self.pattern=None
        self.pattern_name='traffic'
        self.enraged=self.next_enraged=False
        self.taunt_bonus=1.0
        self.command='ATTACK'
        self.rhythm=None
        self.rhythm_keys_down=set()
        self.result={}
        self.result_timer=0
        self.shake=self.hit_stop=0
        self.particles=[];self.slash_effects=[];self.texts=[]
        self.trail_surface=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA)
        self.line='The northern interchange is closed. The man in charge has brought a plow.'
        self.line_time=0
        self.boss_line=DIALOGUE['begin'][0]
        self.dialogue_indices={}
        self.hit_this_turn=False
        self.counter_this_turn=False
        self.combo_position=pygame.Vector2(370,200)
        self.combo_from=self.combo_position.copy()
        self.combo_target=self.combo_position.copy()
        self.combo_elapsed=1
        self.combo_key='D'
        self.combo_stumble=False
        self.heat_hits=0
        self.healed=0
        self.taunt_options=[]
        self.taunt_selected=0
        self.action_pending=None

    def choose_difficulty(self,name):
        self.difficulty=DIFFICULTIES[name]
        self.reset()
        self.music.start_battle()

    def dialogue(self,context):
        pool=DIALOGUE[context]
        index=self.dialogue_indices.get(context,0)
        self.dialogue_indices[context]=index+1
        return pool[index%len(pool)]

    def begin_announcement(self):
        self.state=Phase.ANNOUNCE
        self.pattern_name=PATTERN_ORDER[self.turn%len(PATTERN_ORDER)]
        self.enraged,self.next_enraged=self.next_enraged,False
        context='begin' if self.turn==0 else 'near' if self.boss.hp<BOSS_MAX_HP*.22 else 'half' if self.boss.hp<BOSS_MAX_HP*.5 else 'normal'
        self.boss_line=self.dialogue(context)
        self.line=PATTERN_NAMES[self.pattern_name]+'. '+PATTERN_HINTS[self.pattern_name]
        self.line_time=0
        self.boss.attack_kind=self.pattern_name
        self.boss.react('ANGRY' if self.enraged else 'REVVING',3)

    def begin_expand(self):
        target=pygame.Rect(BOXES[self.pattern_name])
        if self.pattern_name=='whiteout' and self.boss.hp<BOSS_MAX_HP*.5:
            target.inflate_ip(-70,0)
        self.player.rail=None
        self.box.morph(target)
        self.state=Phase.BOX_EXPAND

    def start_boss_phase(self):
        self.state=Phase.BOSS_PHASE
        escalation=2 if self.boss.hp<BOSS_MAX_HP*.25 else 1 if self.boss.hp<BOSS_MAX_HP*.5 else 0
        self.pattern=Pattern(self.pattern_name,self.box.rect,self.difficulty,self.enraged,escalation)
        self.box.install(self.pattern_name)
        self.hit_this_turn=self.counter_this_turn=False
        self.player.stamina=min(MAX_STAMINA,self.player.stamina+25)
        self.player.invulnerability=.4
        self.player.constrain_to_world()
        self.boss.react('ANGRY' if self.enraged else 'REVVING',self.pattern.duration)

    def end_pattern(self):
        if self.state!=Phase.BOSS_PHASE:return
        self.pattern.hazards.clear()
        self.player.rail=None
        self.player.jump_remaining=0
        self.box.morph(MENU_BOX)
        self.state=Phase.BOX_CONTRACT
        self.boss.react('STUNNED' if self.counter_this_turn else 'IDLE',.7)
        self.trail_surface.fill((0,0,0,0))

    def begin_flavor(self):
        self.state=Phase.FLAVOR
        if self.boss.hp<BOSS_MAX_HP*.22:
            self.line=('The plow drags a bright scar across its own shadow.' if self.turn%2 else 'One headlight gives up. The other looks embarrassed.')
        else:self.line=FLAVOR[self.turn%len(FLAVOR)]
        if self.counter_this_turn:self.boss_line=self.dialogue('counter')
        elif self.hit_this_turn:self.boss_line=self.dialogue('hit')
        else:self.boss_line=''
        self.line_time=0
        self.command='ATTACK'

    def choose_action(self):
        if self.command=='TAUNT':
            self.state=Phase.TAUNT_CHOICES
            self.taunt_options=[TAUNTS[(self.turn+i*2)%len(TAUNTS)] for i in range(3)]
            self.taunt_selected=0
            self.boss.react('LAUGHING',2)
            self.music.taunt_drop()
            return
        self.action_pending=self.command
        self.player.rail=None
        self.box.morph(HEAT_BOX if self.command=='HEAT' else RHYTHM_BOX)
        self.state=Phase.BOX_ACTION

    def start_rhythm(self):
        self.command=self.action_pending or self.command
        self.state=Phase.RHYTHM_HEAT if self.command=='HEAT' else Phase.RHYTHM_ATTACK
        self.rhythm=RhythmSequence(self.difficulty,self.command,self.turn)
        self.rhythm_keys_down.clear()
        self.combo_position=pygame.Vector2(370,200)
        self.combo_from=self.combo_position.copy();self.combo_target=self.combo_position.copy()
        self.combo_elapsed=1
        self.combo_stumble=False
        self.heat_hits=self.healed=0
        self.particles.clear();self.slash_effects.clear();self.texts.clear()
        if self.command=='HEAT':
            self.boss_line=self.dialogue('heat')
            self.boss.react('LAUGHING',2)
            self.music.heat()

    def select_taunt(self,index):
        self.taunt_selected=index
        words,response=self.taunt_options[index]
        self.next_enraged=True
        self.taunt_bonus=max(self.taunt_bonus,TAUNT_BONUS)
        self.boss.react('ANGRY',4)
        self.boss_line=response
        self.music.restore_volume()
        self.result={'action':'TAUNT','message':'THE PLOWMAN IS ENRAGED.','detail':f'Next successful ATTACK x{TAUNT_BONUS:g}','taunt':words}
        self.result_timer=3.2
        self.state=Phase.RESULT
        self.shake=3

    def rhythm_feedback(self,judgment,key):
        if judgment is None:return
        self.combo_key=key
        self.combo_from=self.combo_position.copy()
        self.combo_elapsed=0
        self.combo_stumble=judgment=='MISS'
        if judgment=='MISS':
            self.combo_target=self.combo_position+pygame.Vector2(-26,16)
            self.combo_target.x=clamp(self.combo_target.x,325,670)
            self.combo_target.y=clamp(self.combo_target.y,110,230)
            self.boss.react('LAUGHING',.3)
            return
        remaining=sum(n.judgment is None for n in self.rhythm.notes)
        if self.command=='HEAT':
            before=self.player.hp
            amount=HEAT_PERFECT_HP if judgment=='PERFECT' else HEAT_GOOD_HP
            self.player.hp=min(PLAYER_MAX_HP,self.player.hp+amount)
            gained=self.player.hp-before
            self.healed+=gained
            self.heat_hits+=1
            point=pygame.Vector2(self.box.rect.centerx,self.box.rect.centery)
            self.texts.append(FloatingText(point+(0,-65),f'+{gained} HP',(255,221,153)))
            spray(self.particles,point+(0,-20),9,85,(255,197,113))
        else:
            targets={'D':(375,154),'F':(440,214),'J':(625,158),'K':(555,217)}
            self.combo_target=pygame.Vector2(targets[key])
            final=remaining==0
            strong=judgment=='PERFECT'
            radius=110 if final else 70 if remaining<=3 else 57 if strong else 40
            self.slash_effects.append(SlashEffect(self.combo_target,{'D':-.7,'F':0,'J':2.7,'K':1.3}[key],radius,.28 if final else .18))
            spray(self.particles,self.combo_target,42 if final else 18 if strong else 9,260)
            self.boss.react('DAMAGED',.45 if final else .18)
            self.shake=9 if final else 3 if strong else 1
            if final:self.hit_stop=.06  # Only combo animation pauses, never notes/timing.

    def finish_rhythm(self):
        counts=self.rhythm.counts
        self.result=dict(counts,action=self.command)
        if self.command=='ATTACK':
            # Equal perfect potential across difficulties; every successful note contributes.
            per_note=ATTACK_MAX_DAMAGE/len(self.rhythm.notes)
            damage=round(per_note*self.rhythm.hit_units*self.taunt_bonus)
            dealt=round(self.boss.take_damage(damage,rhythm=True))
            if dealt>0:self.taunt_bonus=1.0
            self.result.update(damage=dealt,message='COMBO COMPLETE',detail=f'DAMAGE: {dealt}')
            self.boss_line=''
        else:
            self.result.update(healed=self.healed,message='HEAT RESTORED',detail=f'+{self.healed} HP')
        self.result_timer=RESULT_SECONDS
        self.box.morph(MENU_BOX)
        self.state=Phase.RESULT
        if self.command == 'HEAT':
            self.music.resume_battle()

    def handle_event(self,event):
        if event.type==pygame.KEYUP:
            self.rhythm_keys_down.discard(event.key);return
        if event.type==pygame.KEYDOWN and getattr(event,'repeat',False):return
        if self.state==Phase.DIFFICULTY_SELECT:
            if event.type==pygame.KEYDOWN and event.key in (pygame.K_1,pygame.K_2,pygame.K_3):
                self.choose_difficulty(('CHILL','STANDARD','BLACK ICE')[(pygame.K_1,pygame.K_2,pygame.K_3).index(event.key)])
            return
        if self.state in (Phase.DEAD,Phase.VICTORY):
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_r:self.reset()
                elif event.key==pygame.K_m:self.difficulty=None;self.reset()
            return
        if self.state in (Phase.INTRO,Phase.ANNOUNCE,Phase.FLAVOR):
            if event.type==pygame.KEYDOWN and event.key==pygame.K_RETURN:
                if self.line_time*TYPEWRITER_SPEED<len(self.line):self.line_time=len(self.line)/TYPEWRITER_SPEED
                elif self.state==Phase.INTRO:self.begin_announcement()
                elif self.state==Phase.ANNOUNCE:self.begin_expand()
                else:self.state=Phase.COMMAND
            return
        if self.state==Phase.COMMAND:
            if event.type==pygame.KEYDOWN:
                if event.key in (pygame.K_a,pygame.K_LEFT):self.command='ATTACK'
                elif event.key in (pygame.K_h,pygame.K_DOWN):self.command='HEAT'
                elif event.key in (pygame.K_t,pygame.K_RIGHT):self.command='TAUNT'
                elif event.key==pygame.K_RETURN:self.choose_action()
            return
        if self.state==Phase.TAUNT_CHOICES:
            if event.type==pygame.KEYDOWN:
                if event.key in (pygame.K_1,pygame.K_2,pygame.K_3):self.select_taunt((pygame.K_1,pygame.K_2,pygame.K_3).index(event.key))
                elif event.key==pygame.K_UP:self.taunt_selected=(self.taunt_selected-1)%3
                elif event.key==pygame.K_DOWN:self.taunt_selected=(self.taunt_selected+1)%3
                elif event.key==pygame.K_RETURN:self.select_taunt(self.taunt_selected)
            return
        if self.state in (Phase.RHYTHM_ATTACK,Phase.RHYTHM_HEAT):
            if event.type==pygame.KEYDOWN and event.key in INPUTS and event.key not in self.rhythm_keys_down:
                self.rhythm_keys_down.add(event.key)
                key=INPUTS[event.key]
                self.rhythm_feedback(self.rhythm.press(key),key)
            return
        if self.state==Phase.BOSS_PHASE:
            if event.type==pygame.KEYDOWN:
                if event.key==pygame.K_SPACE:self.player.jump()
                elif event.key in (pygame.K_LSHIFT,pygame.K_RSHIFT):self.player.dodge()
            elif event.type==pygame.MOUSEBUTTONDOWN and event.button==3:self.player.toe_pick(self.particles)

    def hurt(self,amount,ignore_dodge=False):
        if self.player.take_damage(amount,ignore_dodge=ignore_dodge):
            self.hit_this_turn=True
            self.shake=6
            spray(self.particles,self.player.position,14,150,(242,146,128))
            return True
        return False

    def resolve_hazards(self,previous):
        p=self.player
        for h in self.pattern.hazards:
            if h.life<=0 or getattr(h,'warning',0)>0:continue
            if h.kind=='traffic' and not h.resolved:
                # Relative motion catches both fast rows and fast skaters.
                start=(previous.x,previous.y-h.previous_y)
                end=(p.position.x,p.position.y-h.y)
                collided=any(pygame.Rect(block.x,0,block.width,28).inflate(PLAYER_RADIUS*2,PLAYER_RADIUS*2).clipline(start,end) for block in h.blocks if block.width>0)
                if collided:
                    h.resolved=True
                    if p.dodge_timer>0:
                        self.counter_this_turn=True
                        if h.major and DODGE_DURATION-p.dodge_timer<=PERFECT_DODGE_WINDOW:
                            self.pattern.early_end=True
                            self.boss.react('STUNNED',1)
                    else:self.hurt(22)
            elif h.kind in ('chain','wave') and not h.resolved:
                before=previous.y-h.previous_y
                after=p.position.y-h.y
                if before*after<=0 or min(abs(before),abs(after))<PLAYER_RADIUS+10:
                    h.resolved=True
                    if h.kind=='chain':
                        if p.airborne:
                            self.counter_this_turn=True
                            spray(self.particles,p.position,8,80)
                        else:self.hurt(20)
                    elif p.airborne and p.ramp_bonus:
                        self.counter_this_turn=True
                        self.texts.append(FloatingText(p.position+(0,-60),'CLEAN AIR'))
                        spray(self.particles,p.position,20,150)
                    else:self.hurt(26,ignore_dodge=True)
            elif h.kind=='shard':
                distance=segment_distance(pygame.Vector2(),h.previous-previous,h.position-p.position)
                if distance<h.radius+PLAYER_RADIUS:
                    h.life=0
                    if h.parryable and p.parry_timer>0:
                        p.parry_timer=0
                        p.stamina=min(MAX_STAMINA,p.stamina+15)
                        p.invulnerability=max(p.invulnerability,.25)
                        self.counter_this_turn=True
                        self.pattern.counter_count+=1
                        self.boss.react('STUNNED',.6)
                        self.shake=6
                        spray(self.particles,p.position,30,240,(248,226,161))
                        self.texts.append(FloatingText(p.position+(0,-50),'PARRY'))
                        if h.major or self.pattern.counter_count>=3:self.pattern.early_end=True
                    else:self.hurt(10)

    def update_effects(self,dt):
        for collection in (self.particles,self.slash_effects,self.texts):
            for effect in collection:effect.update(dt)
            collection[:]=[e for e in collection if e.life>0]
        self.particles[:]=self.particles[-450:]

    def update(self,dt):
        self.time+=dt
        self.shake=max(0,self.shake-25*dt)
        self.boss.update(dt)
        if self.difficulty and self.boss.hp > 0:
            self.music.update_intensity(self.boss.hp / BOSS_MAX_HP)
        self.update_effects(dt)
        self.box.update(dt,self.player)
        if self.state in (Phase.DIFFICULTY_SELECT,Phase.DEAD,Phase.VICTORY,Phase.COMMAND,Phase.TAUNT_CHOICES):return
        if self.state in (Phase.INTRO,Phase.ANNOUNCE,Phase.FLAVOR):
            self.line_time+=dt
            if self.line_time>len(self.line)/TYPEWRITER_SPEED+1.2:
                if self.state==Phase.INTRO:self.begin_announcement()
                elif self.state==Phase.ANNOUNCE:self.begin_expand()
                else:self.state=Phase.COMMAND
            return
        if self.state in (Phase.BOX_EXPAND,Phase.BOX_CONTRACT,Phase.BOX_ACTION):
            if not self.box.morphing:
                if self.state==Phase.BOX_EXPAND:self.start_boss_phase()
                elif self.state==Phase.BOX_CONTRACT:self.begin_flavor()
                else:self.start_rhythm()
            return
        if self.state in (Phase.RHYTHM_ATTACK,Phase.RHYTHM_HEAT):
            missed=self.rhythm.update(dt)
            for note in missed:self.rhythm_feedback('MISS',note.key)
            if self.hit_stop>0:self.hit_stop=max(0,self.hit_stop-dt)
            else:self.combo_elapsed=min(1,self.combo_elapsed+dt*7)
            t=self.combo_elapsed
            self.combo_position=self.combo_from.lerp(self.combo_target,t*t*(3-2*t))
            if self.rhythm.done:self.finish_rhythm()
            return
        if self.state==Phase.RESULT:
            self.result_timer-=dt
            if self.result_timer<=0:
                if self.boss.hp<=0:
                    self.state=Phase.BREAKDOWN;self.result_timer=2.0;self.boss.breakdown=0
                    self.music.stop(700)
                else:
                    self.turn+=1
                    self.box.morph(MENU_BOX)
                    self.begin_announcement()
            return
        if self.state==Phase.BREAKDOWN:
            self.result_timer-=dt
            self.boss.breakdown+=dt
            self.shake=max(0,self.result_timer*3)
            if int(self.time*30)%3==0:spray(self.particles,(500,170),3,130,(250,185,107))
            if self.result_timer<=0:self.state=Phase.VICTORY
            return
        if self.state==Phase.BOSS_PHASE:
            step=min(dt,.033)
            previous=self.player.position.copy()
            self.player.update(step,pygame.key.get_pressed(),self.trail_surface,self.particles)
            self.player.constrain_to_world()
            traversal=self.box.update_traversal(self.player,previous)
            if traversal:
                spray(self.particles,self.player.position,12,110)
                self.texts.append(FloatingText(self.player.position+(0,-35),traversal))
            self.pattern.update(step,self.player)
            if self.pattern.swarm_scattered and not getattr(self.pattern,'escape_shown',False):
                self.pattern.escape_shown=True
                self.counter_this_turn=True
                self.texts.append(FloatingText(self.player.position+(0,-40),'SWARM SCATTERED'))
                spray(self.particles,self.player.position,24,190)
            self.resolve_hazards(previous)
            if self.player.hp<=0:
                self.state=Phase.DEAD
                self.pattern.hazards.clear()
                self.boss.react('LAUGHING',2)
                self.music.stop(600)
            elif self.pattern.done:self.end_pattern()

    def text(self,surface,text,y,color=(230,241,245),big=False,x=500):
        draw_text(surface,text,self.big_font if big else self.font,(x,y),color,center=True)

    def bar(self,surface,rect,ratio,color):
        pygame.draw.rect(surface,(31,48,60),rect)
        fill=pygame.Rect(rect);fill.width=round(fill.width*clamp(ratio,0,1))
        if fill.width:pygame.draw.rect(surface,color,fill)

    def draw_line(self,surface):
        shown=self.line[:int(self.line_time*TYPEWRITER_SPEED)]
        lines=textwrap.wrap(shown,62)
        for i,line in enumerate(lines[:3]):
            draw_text(surface,line,self.small_font,(self.box.rect.left+24,self.box.rect.top+25+i*27))

    def draw_header(self,surface):
        draw_text(surface,'THIN ICE',self.font,(22,20),(169,214,233))
        self.text(surface,'THE PLOWMAN',22)
        if self.difficulty:draw_text(surface,self.difficulty.name,self.small_font,(808,22))
        self.bar(surface,(395,43,210,7),self.boss.hp/BOSS_MAX_HP,(190,132,112))

    def draw_hud(self,surface):
        pygame.draw.line(surface,(54,86,105),(22,613),(978,613),1)
        draw_text(surface,f'HEALTH {self.player.hp:.0f}',self.small_font,(22,627))
        self.bar(surface,(22,650,185,12),self.player.hp/PLAYER_MAX_HP,(168,221,237))
        draw_text(surface,f'STAMINA {self.player.stamina:.0f}',self.small_font,(245,627))
        self.bar(surface,(245,650,185,12),self.player.stamina/MAX_STAMINA,(206,215,157))
        if self.state==Phase.BOSS_PHASE:
            draw_text(surface,f'{PATTERN_NAMES[self.pattern_name]}  {max(0,self.pattern.duration-self.pattern.elapsed):.1f}s',self.small_font,(470,628))
            draw_text(surface,'ENRAGED' if self.enraged else 'SURVIVE THE PATTERN',self.small_font,(470,651),(237,175,139))
        draw_text(surface,'W push   A/D carve   S brake   SPACE jump   SHIFT dodge   RMB parry   ESC quit',self.small_font,(500,684),(146,178,197),center=True)

    def draw_commands(self,surface):
        for index,(action,key) in enumerate((('ATTACK','A / LEFT'),('HEAT','H / DOWN'),('TAUNT','T / RIGHT'))):
            rect=pygame.Rect(135+index*250,591,230,59)
            pygame.draw.rect(surface,(21,37,49),rect)
            selected=action==self.command
            pygame.draw.rect(surface,(231,224,173) if selected else (84,118,139),rect,3 if selected else 1)
            draw_text(surface,action,self.font,(rect.centerx,611),(244,236,187) if selected else (194,216,230),center=True)
            draw_text(surface,key,self.small_font,(rect.centerx,636),center=True)
        self.text(surface,'ENTER TO CONFIRM',679,(159,192,209))

    def draw_rhythm(self,surface):
        self.box.draw(surface,self.time)
        self.rhythm.draw(surface,self.font,self.small_font)
        if self.command=='HEAT':
            p=pygame.Vector2(self.box.rect.centerx,self.box.rect.centery+25)
            draw_beacon(surface,p,self.time,self.heat_hits)
            skater=copy.copy(self.player);skater.position=p+(-45,25);skater.jump_remaining=0
            skater.draw(surface,pygame.Vector2())
            self.text(surface,'HEAT',282,(244,214,152),x=self.box.rect.centerx)
            draw_text(surface,f'HP {self.player.hp:.0f}',self.font,(self.box.rect.centerx,self.box.rect.bottom-20),center=True)
        else:
            skater=copy.copy(self.player)
            skater.position=self.combo_position.copy()
            skater.jump_remaining=0
            skater.parry_timer=skater.parry_lock=skater.dodge_timer=skater.hit_flash=0
            skater.angle=self.time*19 if self.combo_key=='K' and not self.combo_stumble else math.pi if self.combo_key=='J' else 0
            if self.combo_stumble:skater.angle+=math.sin(self.time*25)*.6
            skater.draw(surface,pygame.Vector2())
            self.text(surface,'EDGE COMBO',370,(185,219,233),x=155)
            draw_text(surface,f'HITS {self.rhythm.counts["PERFECT"]+self.rhythm.counts["GOOD"]}',self.small_font,(155,405),center=True)
            if self.taunt_bonus>1:draw_text(surface,f'TAUNT x{self.taunt_bonus:g}',self.small_font,(155,441),(237,188,135),center=True)

    def draw(self,surface):
        # ==========================================================
        # FROZEN INTERCHANGE BACKGROUND
        # ==========================================================

        surface.fill((11, 23, 31))

        # Distant snow / ice fields
        pygame.draw.rect(
            surface,
            (24, 43, 53),
            (0, 70, WIDTH, HEIGHT - 70),
        )

        # Frozen highway
        road = pygame.Rect(80, 70, WIDTH - 160, HEIGHT - 70)

        pygame.draw.rect(
            surface,
            (30, 47, 55),
            road,
        )

        # Dark road edges
        pygame.draw.rect(
            surface,
            (16, 31, 39),
            road,
            8,
        )

        # ----------------------------------------------------------
        # SNOWBANKS
        # Chunky irregular edges instead of perfectly straight road.
        # ----------------------------------------------------------

        for i in range(18):
            y = 75 + i * 38

            wobble_left = int(math.sin(i * 2.1) * 9)
            wobble_right = int(math.cos(i * 1.7) * 9)

            pygame.draw.circle(
                surface,
                (106, 137, 146),
                (80 + wobble_left, y),
                20,
            )

            pygame.draw.circle(
                surface,
                (106, 137, 146),
                (WIDTH - 80 + wobble_right, y),
                20,
            )

            pygame.draw.circle(
                surface,
                (158, 180, 184),
                (76 + wobble_left, y - 5),
                12,
            )

            pygame.draw.circle(
                surface,
                (158, 180, 184),
                (WIDTH - 76 + wobble_right, y - 5),
                12,
            )

        # ----------------------------------------------------------
        # OLD HIGHWAY LANE MARKINGS
        # ----------------------------------------------------------

        for y in range(100, HEIGHT, 85):
            pygame.draw.rect(
                surface,
                (105, 116, 105),
                (WIDTH // 2 - 3, y, 6, 38),
            )

        # ----------------------------------------------------------
        # ICE PATCHES
        # ----------------------------------------------------------

        ice_patches = [
            (145, 160, 110, 35),
            (690, 215, 135, 42),
            (250, 410, 150, 38),
            (615, 520, 105, 30),
        ]

        for x, y, w, h in ice_patches:
            pygame.draw.ellipse(
                surface,
                (51, 82, 91),
                (x, y, w, h),
            )

            pygame.draw.arc(
                surface,
                (91, 132, 142),
                (x + 8, y + 5, w - 16, h - 10),
                0,
                math.pi,
                3,
            )

        # ----------------------------------------------------------
        # CRACKS IN THE ICE
        # ----------------------------------------------------------

        cracks = [
            [(180, 115), (196, 133), (189, 151), (213, 171)],
            [(790, 330), (770, 347), (781, 364), (758, 382)],
            [(320, 550), (340, 530), (358, 541), (380, 516)],
            [(670, 110), (650, 127), (658, 146), (635, 161)],
        ]

        for crack in cracks:
            pygame.draw.lines(
                surface,
                (18, 35, 43),
                False,
                crack,
                3,
            )

        # ----------------------------------------------------------
        # LITTLE FROZEN DEBRIS
        # ----------------------------------------------------------

        debris = [
            (122, 245),
            (846, 185),
            (137, 510),
            (866, 440),
        ]

        for x, y in debris:
            pygame.draw.rect(
                surface,
                (69, 71, 67),
                (x - 9, y - 5, 18, 10),
            )

            pygame.draw.rect(
                surface,
                (120, 105, 78),
                (x - 6, y - 8, 12, 4),
            )

        # ----------------------------------------------------------
        # FALLING SNOW
        # ----------------------------------------------------------

        for i in range(40):
            x = (
                        i * 137
                        + math.sin(self.time * 0.3 + i) * 12
                ) % WIDTH

            y = (
                        i * 71
                        + self.time * (8 + i % 5)
                ) % HEIGHT

            radius = 2 if i % 7 == 0 else 1

            pygame.draw.circle(
                surface,
                (174, 198, 204),
                (int(x), int(y)),
                radius,
            )
        self.draw_header(surface)
        nudge=pygame.Vector2(random.uniform(-self.shake,self.shake),random.uniform(-self.shake,self.shake))
        self.boss.draw(surface,self.time,self.box.rect.width,(500+nudge.x,127+nudge.y if self.box.rect.top<270 else 136+nudge.y))
        if self.state==Phase.DIFFICULTY_SELECT:
            self.text(surface,'CHOOSE YOUR EDGE',279,(227,233,204))
            for index,(name,hint) in enumerate((('CHILL','Roomy gaps / gentler notes'),('STANDARD','The intended winter'),('BLACK ICE','Dense patterns / tighter timing'))):
                self.text(surface,f'[{index+1}] {name}',350+index*87)
                draw_text(surface,hint,self.small_font,(500,378+index*87),(147,181,201),center=True)
            self.text(surface,'A SKATER. A PLOW. A VERY SMALL ROAD.',649,(158,199,218))
            return
        rhythm=self.state in (Phase.RHYTHM_ATTACK,Phase.RHYTHM_HEAT)
        if rhythm:self.draw_rhythm(surface)
        else:
            self.box.draw(surface,self.time)
            if self.state==Phase.BOSS_PHASE:
                old_clip=surface.get_clip();surface.set_clip(self.box.rect.inflate(-6,-6))
                surface.blit(self.trail_surface,(0,0))
                for hazard in self.pattern.hazards:hazard.draw(surface,self.time)
                self.player.draw(surface,pygame.Vector2())
                surface.set_clip(old_clip)
                self.text(surface,PATTERN_NAMES[self.pattern_name],self.box.rect.top-15,(218,233,235))
            elif self.state in (Phase.BOX_EXPAND,Phase.BOX_CONTRACT,Phase.BOX_ACTION):
                old_clip=surface.get_clip();surface.set_clip(self.box.rect)
                self.player.draw(surface,pygame.Vector2());surface.set_clip(old_clip)
            elif self.state in (Phase.INTRO,Phase.ANNOUNCE,Phase.FLAVOR,Phase.COMMAND):
                self.draw_line(surface)
                skater=copy.copy(self.player);skater.position=pygame.Vector2(self.box.rect.centerx,self.box.rect.bottom-30);skater.jump_remaining=0
                skater.draw(surface,pygame.Vector2())
            elif self.state==Phase.TAUNT_CHOICES:
                for i,(words,_) in enumerate(self.taunt_options):
                    color=(252,227,169) if i==self.taunt_selected else (213,232,239)
                    draw_text(surface,f'[{i+1}] {words}',self.small_font,(self.box.rect.left+20,self.box.rect.top+34+i*43),color)
            elif self.state==Phase.RESULT:
                if self.result.get('action') == 'ATTACK':
                    self.text(
                        surface,
                        self.result.get('detail', ''),
                        self.box.rect.top + 80,
                        (233, 228, 185),
                        x=self.box.rect.centerx
                    )
                elif self.result.get('action') == 'HEAT':
                    self.text(
                        surface,
                        self.result.get('detail', ''),
                        self.box.rect.top + 80,
                        (244, 214, 152),
                        x=self.box.rect.centerx
                    )
                elif self.result.get('action') == 'TAUNT':
                    self.text(
                        surface,
                        self.result.get('message', ''),
                        self.box.rect.top + 80,
                        (237, 175, 139),
                        x=self.box.rect.centerx
                    )
            if self.boss_line and self.state in (Phase.INTRO,Phase.ANNOUNCE,Phase.FLAVOR,Phase.COMMAND,Phase.TAUNT_CHOICES,Phase.RESULT):
                self.text(surface,self.boss_line,263,(188,219,231))
        for effect in self.particles+self.slash_effects:effect.draw(surface,pygame.Vector2())
        for text in self.texts:text.draw(surface,pygame.Vector2(),self.small_font)
        if self.state==Phase.COMMAND:self.draw_commands(surface)
        elif not rhythm:self.draw_hud(surface)
        if self.state in (Phase.INTRO,Phase.ANNOUNCE,Phase.FLAVOR):
            draw_text(surface,'ENTER: REVEAL / CONTINUE',self.small_font,(500,577),(146,178,197),center=True)
        if self.state==Phase.TAUNT_CHOICES:self.text(surface,'1 / 2 / 3 TO SAY IT',575,(231,219,174))
        if self.state in (Phase.DEAD,Phase.VICTORY):
            overlay=pygame.Surface((WIDTH,HEIGHT),pygame.SRCALPHA);overlay.fill((5,12,19,225));surface.blit(overlay,(0,0))
            if self.state==Phase.DEAD:
                self.text(surface,'THIN ICE',272,big=True)
                self.text(surface,'YOU FROZE.',355,(231,164,143))
                self.text(surface,'R — RETURN TO THE FLAME',441)
            else:
                self.text(surface,'THE PLOWMAN',251,big=True)
                self.text(surface,'HAS FALLEN',317,big=True)
                self.text(surface,'THE NORTHERN INTERCHANGE IS FREE.',406,(169,220,223))
                self.text(surface,'R — RUN IT BACK',480)
            self.text(surface,'M — CHANGE DIFFICULTY',554,(147,182,202))
