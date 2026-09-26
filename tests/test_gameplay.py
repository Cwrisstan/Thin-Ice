"""Behavior tests for the final box battle; no assets or native display required."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT','1')
import unittest
from collections import defaultdict
import pygame
from thin_ice.game import GameManager
from thin_ice.combat import Phase,DIFFICULTIES,BOXES,PATTERN_ORDER,MENU_BOX,TAUNT_BONUS
from thin_ice.rhythm import RhythmSequence,INPUTS,HIT_Y
from thin_ice.patterns import Pattern,TrafficRow,Sweep,Shard
from thin_ice.player import Player
from thin_ice.world import BattleBox
from thin_ice.settings import BOSS_MAX_HP


class BattleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init();cls.screen=pygame.display.set_mode((1000,700))
    @classmethod
    def tearDownClass(cls):pygame.quit()
    def setUp(self):
        self.g=GameManager();self.g.choose_difficulty('STANDARD')
    def tap(self,key):
        self.g.handle_event(pygame.event.Event(pygame.KEYDOWN,key=key))
        self.g.handle_event(pygame.event.Event(pygame.KEYUP,key=key))
    def defense(self,name='traffic'):
        g=self.g;g.pattern_name=name;g.box.morph(BOXES[name])
        g.box.update(.5,g.player);g.start_boss_phase();g.player.invulnerability=0
    def action(self,name='ATTACK'):
        self.g.state=Phase.COMMAND;self.g.command=name;self.g.choose_action()
        if name!='TAUNT':self.g.update(.5)
    def perfect_sequence(self):
        for note in self.g.rhythm.notes:
            self.g.rhythm.elapsed=note.target
            self.tap(next(k for k,v in INPUTS.items() if v==note.key))
        self.g.update(2)
    def test_difficulty_selection_all_start(self):
        for i,name in enumerate(DIFFICULTIES):
            self.g=GameManager();self.tap((pygame.K_1,pygame.K_2,pygame.K_3)[i])
            self.assertEqual(self.g.difficulty.name,name)
            self.g.line_time=100;self.tap(pygame.K_RETURN)
            self.assertEqual(self.g.state,Phase.ANNOUNCE)
            self.g.line_time=100;self.tap(pygame.K_RETURN)
            self.assertEqual(self.g.state,Phase.BOX_EXPAND)
            self.g.update(.5);self.assertEqual(self.g.state,Phase.BOSS_PHASE)
    def test_no_defense_score_or_multiplier(self):
        self.assertFalse(hasattr(self.g,'flow'))
        self.assertFalse(hasattr(self.g,'opening_multiplier'))
        self.defense();hp=self.g.boss.hp
        self.g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=1))
        self.assertEqual(self.g.boss.hp,hp)
        self.assertEqual(self.g.boss.take_damage(999),0)
    def test_morph_smooth_contained_and_momentum_retained(self):
        p=self.g.player;box=self.g.box;p.velocity.update(300,120)
        for target in BOXES.values():
            before=box.rect.copy();box.morph(target);box.update(.1,p)
            self.assertNotEqual(box.rect,before);self.assertNotEqual(box.rect,pygame.Rect(target))
            for _ in range(25):
                box.update(.02,p)
                self.assertTrue(box.rect.inflate(-24,-24).collidepoint(p.position))
            self.assertEqual(box.rect,pygame.Rect(target));self.assertGreater(p.speed,100)
    def test_original_skating_acceleration_and_carve(self):
        p=Player((300,300));p.bounds=pygame.Rect(0,0,2200,1800)
        trail=pygame.Surface((2200,1800),pygame.SRCALPHA)
        for _ in range(120):p.update(1/60,defaultdict(bool,{pygame.K_w:True}),trail,[])
        self.assertGreater(p.speed,490)
        old_angle=p.angle
        p.update(.1,defaultdict(bool,{pygame.K_d:True}),trail,[])
        self.assertGreater(p.angle,old_angle);self.assertGreater(p.velocity.y,0)
        old_speed=p.speed;p.update(.1,defaultdict(bool,{pygame.K_s:True}),trail,[])
        self.assertLess(p.speed,old_speed*.7)
    def test_jump_dodge_parry_stamina(self):
        self.defense();p=self.g.player
        self.tap(pygame.K_SPACE);self.assertTrue(p.airborne);self.assertEqual(p.stamina,85)
        p.jump_remaining=0;self.tap(pygame.K_LSHIFT);self.assertEqual(p.stamina,55)
        self.assertFalse(p.take_damage(20));p.dodge_timer=0
        self.g.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN,button=3))
        self.assertEqual(p.speed,0);self.assertGreater(p.parry_timer,0)
        p.parry_lock=0;p.stamina=14
        self.assertFalse(p.jump());self.assertFalse(p.dodge())
    def test_boundary_keeps_tangential_velocity(self):
        p=self.g.player;p.position.update(p.bounds.right-1,p.bounds.centery);p.velocity.update(400,180)
        p.constrain_to_world();self.assertLess(p.velocity.x,0);self.assertEqual(p.velocity.y,180)
    def test_traffic_gap_and_collision(self):
        self.defense();g=self.g;p=g.player
        h=TrafficRow(g.box.rect,p.position.x,160,100,0)
        h.y=h.previous_y=p.position.y-10;g.pattern.hazards=[h]
        g.resolve_hazards(p.position.copy());self.assertEqual(p.hp,100)
        h.gap=g.box.rect.left+90;g.resolve_hazards(p.position.copy());self.assertEqual(p.hp,78)
    def test_major_last_second_dodge_ends_pattern(self):
        self.defense();g=self.g;p=g.player
        h=TrafficRow(g.box.rect,g.box.rect.left+90,150,100,0,major=True)
        h.y=h.previous_y=p.position.y-10;g.pattern.hazards=[h]
        p.dodge_timer=.19;g.resolve_hazards(p.position.copy())
        self.assertTrue(g.pattern.early_end);self.assertEqual(p.hp,100)
    def test_chain_jump_and_ground_damage(self):
        for jump,hp in ((True,100),(False,80)):
            self.setUp();self.defense('chain');g=self.g;p=g.player
            if jump:p.jump()
            h=Sweep(g.box.rect,200,0);h.previous_y=p.position.y-10;h.y=p.position.y+10
            g.pattern.hazards=[h];g.resolve_hazards(p.position.copy());self.assertEqual(p.hp,hp)
    def test_wave_requires_ramp_air_not_dodge(self):
        for ramp,hp in ((True,100),(False,74)):
            self.setUp();self.defense('wave');g=self.g;p=g.player
            if ramp:p.launch(1.35,90,True)
            else:p.dodge()
            h=Sweep(g.box.rect,200,0,tall=True);h.previous_y=p.position.y-10;h.y=p.position.y+10
            g.pattern.hazards=[h];g.resolve_hazards(p.position.copy());self.assertEqual(p.hp,hp)
    def test_only_gold_shards_parry(self):
        for marked,hp in ((True,100),(False,90)):
            self.setUp();self.defense('whiteout');g=self.g;p=g.player;p.toe_pick([])
            h=Shard(p.position,(0,0),g.box.rect,0,parryable=marked,major=True)
            g.pattern.hazards=[h];g.resolve_hazards(p.position.copy())
            self.assertEqual(p.hp,hp);self.assertEqual(g.pattern.early_end,marked)
    def test_ramp_and_rail_exist_only_in_patterns(self):
        self.defense('wave');g=self.g;p=g.player
        p.position.update(g.box.ramps[0].center);p.velocity.update(350,0)
        self.assertEqual(g.box.update_traversal(p,p.position),'RAMP LAUNCH')
        self.assertTrue(p.ramp_bonus)
        p.jump_remaining=0;self.defense('swarm')
        p.position=g.box.rail[0]+pygame.Vector2(100,5);p.velocity.update(300,0)
        self.assertIsNotNone(g.box.update_traversal(p,p.position))
        p.update(.1,defaultdict(bool),g.trail_surface,[]);self.assertGreater(p.speed,300)
        self.assertTrue(p.jump());self.assertIsNone(p.rail)
        g.end_pattern();self.assertFalse(g.box.ramps);self.assertIsNone(g.box.rail)
    def test_swarm_rail_escape(self):
        self.defense('swarm');g=self.g;p=g.player
        p.rail=g.box.rail
        h=Shard(p.position+pygame.Vector2(180,0),(-180,0),g.box.rect,0,homing=True)
        g.pattern.spawned=1;g.pattern.hazards=[h]
        for _ in range(25):g.pattern.update(.02,p)
        self.assertTrue(g.pattern.swarm_scattered);self.assertFalse(g.pattern.hazards)
    def test_all_patterns_end_and_render(self):
        for name in PATTERN_ORDER:
            self.setUp();self.defense(name);g=self.g
            for _ in range(680):
                g.player.invulnerability=100
                g.update(1/60)
                if _%20==0:g.draw(self.screen)
                if g.state==Phase.COMMAND:break
            self.assertIn(g.state,(Phase.FLAVOR,Phase.COMMAND))
            self.assertFalse(g.pattern.hazards)
    def test_flavor_every_turn_and_commands_unconditional(self):
        self.defense();g=self.g;g.end_pattern();g.update(.5)
        self.assertEqual(g.state,Phase.FLAVOR);self.assertTrue(g.line)
        first=g.line;g.line_time=100;self.tap(pygame.K_RETURN)
        self.assertEqual(g.state,Phase.COMMAND)
        for key,name in ((pygame.K_a,'ATTACK'),(pygame.K_h,'HEAT'),(pygame.K_t,'TAUNT')):
            self.tap(key);self.assertEqual(g.command,name)
        g.turn=1;g.begin_flavor();self.assertNotEqual(g.line,first)
    def test_attack_duration_density_and_vertical_motion(self):
        sizes=[]
        for cfg in DIFFICULTIES.values():
            r=RhythmSequence(cfg,'ATTACK');sizes.append(len(r.notes))
            self.assertTrue(15<=r.duration<=20)
            targets=[n.target for n in r.notes];self.assertEqual(len(targets),len(set(targets)))
            first=r.notes[0];y=r.note_y(first);r.update(.1);self.assertGreater(r.note_y(first),y)
            r.elapsed=first.target;self.assertEqual(r.note_y(first),HIT_Y)
        self.assertLess(sizes[0],sizes[1]);self.assertLess(sizes[1],sizes[2])
    def test_perfect_good_miss_and_auto_miss(self):
        r=RhythmSequence(DIFFICULTIES['STANDARD'],'ATTACK')
        r.elapsed=r.notes[0].target;self.assertEqual(r.press(r.notes[0].key),'PERFECT')
        r.elapsed=r.notes[1].target+.12;self.assertEqual(r.press(r.notes[1].key),'GOOD')
        r.elapsed=r.notes[2].target-.6;self.assertEqual(r.press(r.notes[2].key),'MISS')
        self.assertFalse(r.done);r.update(30);self.assertTrue(r.done)
    def test_held_key_cannot_hit_multiple_notes(self):
        self.action();r=self.g.rhythm;n=r.notes[0];r.elapsed=n.target
        key=next(k for k,v in INPUTS.items() if v==n.key)
        e=pygame.event.Event(pygame.KEYDOWN,key=key)
        self.g.handle_event(e);self.g.handle_event(e)
        self.assertEqual(sum(n.judgment is not None for n in r.notes),1)
    def test_attack_damage_equal_potential_all_difficulties(self):
        for name in DIFFICULTIES:
            self.g.choose_difficulty(name);self.action();self.perfect_sequence()
            self.assertEqual(self.g.state,Phase.RESULT)
            self.assertEqual(self.g.result['damage'],240)
            self.assertEqual(self.g.boss.hp,BOSS_MAX_HP-240)
    def test_attack_misses_do_not_end_sequence(self):
        self.action();g=self.g;g.rhythm.notes[0].judgment='MISS'
        self.assertFalse(g.rhythm.done)
        for note in g.rhythm.notes[1:]:note.judgment='GOOD'
        g.update(20)
        self.assertGreater(g.result['damage'],100);self.assertLess(g.result['damage'],160)
        self.assertEqual(g.player.hp,100)
    def test_heat_heals_immediately_per_note(self):
        self.g.player.hp=50;self.action('HEAT');g=self.g;r=g.rhythm
        self.assertTrue(8<=r.duration<=10)
        n=r.notes[0];r.elapsed=n.target
        self.tap(next(k for k,v in INPUTS.items() if v==n.key))
        self.assertEqual(g.player.hp,56);self.assertEqual(g.state,Phase.RHYTHM_HEAT)
        n=r.notes[1];r.elapsed=n.target+(r.perfect_window+r.good_window)/2
        self.tap(next(k for k,v in INPUTS.items() if v==n.key));self.assertEqual(g.player.hp,60)
        self.assertEqual(g.boss.hp,BOSS_MAX_HP)
        g.player.hp=99;n=r.notes[2];r.elapsed=n.target
        self.tap(next(k for k,v in INPUTS.items() if v==n.key));self.assertEqual(g.player.hp,100)
    def test_taunt_dialogue_not_rhythm(self):
        self.action('TAUNT');g=self.g
        self.assertEqual(g.state,Phase.TAUNT_CHOICES);self.assertIsNone(g.rhythm)
        self.assertEqual(len(set(a for a,b in g.taunt_options)),3)
        self.tap(pygame.K_2)
        self.assertEqual(g.state,Phase.RESULT);self.assertTrue(g.next_enraged)
        self.assertEqual(g.taunt_bonus,TAUNT_BONUS);self.assertTrue(g.boss_line)
        g.update(4);self.assertTrue(g.enraged);self.assertFalse(g.next_enraged)
    def test_taunt_bonus_only_consumed_on_successful_attack(self):
        self.g.taunt_bonus=1.4;self.action();self.g.update(20)
        self.assertEqual(self.g.taunt_bonus,1.4);self.assertEqual(self.g.result['damage'],0)
        self.action();self.perfect_sequence();self.assertEqual(self.g.result['damage'],336)
        self.assertEqual(self.g.taunt_bonus,1)
    def test_enrage_difficulty_and_remix(self):
        cfg=DIFFICULTIES['STANDARD'];rect=pygame.Rect(BOXES['traffic'])
        base=Pattern('traffic',rect,cfg);angry=Pattern('traffic',rect,cfg,True,2)
        self.assertGreater(angry.speed_scale,base.speed_scale)
        self.assertLess(angry.warning_scale,base.warning_scale)
        self.assertGreater(angry.density,base.density)
        angry.spawn(1);self.assertTrue(any(h.kind=='shard' for h in angry.hazards))
    def test_death_restart_keeps_difficulty_resets_fight(self):
        self.defense();g=self.g;g.player.hp=0;g.taunt_bonus=1.4;g.next_enraged=True;g.turn=4
        g.update(.01);self.assertEqual(g.state,Phase.DEAD)
        self.tap(pygame.K_r)
        self.assertEqual(g.state,Phase.INTRO);self.assertEqual(g.difficulty.name,'STANDARD')
        self.assertEqual(g.player.hp,100);self.assertEqual(g.player.stamina,100)
        self.assertEqual(g.player.position,g.checkpoint);self.assertEqual(g.boss.hp,BOSS_MAX_HP)
        self.assertEqual(g.taunt_bonus,1);self.assertFalse(g.next_enraged);self.assertEqual(g.turn,0)
    def test_victory_after_result_and_breakdown(self):
        self.g.boss.hp=1;self.action();self.perfect_sequence()
        self.assertEqual(self.g.state,Phase.RESULT)
        self.g.update(3);self.assertEqual(self.g.state,Phase.BREAKDOWN)
        self.g.update(3);self.assertEqual(self.g.state,Phase.VICTORY)
        self.g.draw(self.screen);self.tap(pygame.K_r);self.assertEqual(self.g.state,Phase.INTRO)
    def test_all_actions_return_to_next_pattern(self):
        for name in ('ATTACK','HEAT','TAUNT'):
            self.setUp();self.action(name)
            if name=='TAUNT':self.g.select_taunt(0)
            else:self.perfect_sequence()
            self.g.update(4)
            self.assertEqual(self.g.state,Phase.ANNOUNCE)
            self.assertEqual(self.g.turn,1)
            self.g.line_time=100;self.tap(pygame.K_RETURN);self.g.update(.5)
            self.assertEqual(self.g.state,Phase.BOSS_PHASE)
            self.assertEqual(self.g.pattern.name,'chain')


if __name__=='__main__':unittest.main()
