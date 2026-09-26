# Thin Ice — the battle box

An ice skater, a wasteland warlord, and a snowplow with an ego. All visuals are
Pygame primitives. The existing acceleration, carving, braking, defensive actions,
stamina, skate trails and particles are retained. Combat now takes place inside
an animated battle box, with The Plowman and his rider above it.

## Run

Run `main.py` with the project's `.venv` in PyCharm, or:

```sh
.venv/bin/python main.py
.venv/bin/python -m unittest discover -s tests -v
```

Only `pygame==2.6.1` is required. `python -m thin_ice` also launches the game.

## Loop and controls

Difficulty → Intro → Announcement → Box expands → Boss pattern → Box contracts
→ Flavor → Command → Action → Result → Next announcement.

ATTACK and HEAT resize into their rhythm layouts. TAUNT opens dialogue choices.
Lethal boss damage finishes its result, then a two-second breakdown leads to victory.
Death interrupts defense. R resets the fight at the flame checkpoint while keeping
difficulty; temporary bonuses, hazards, HP and stamina reset.

| Screen | Controls |
| --- | --- |
| Difficulty | 1 CHILL / 2 STANDARD / 3 BLACK ICE |
| Narration | Enter reveals text, then continues; text also advances automatically |
| Skating | W push, A/D carve, S brake |
| Defense | Space jump, Shift dodge, RMB toe-pick parry |
| Commands | A/Left ATTACK, H/Down HEAT, T/Right TAUNT; Enter confirms |
| Rhythm | D F J K, one tap per falling note |
| Taunt dialogue | 1/2/3, or Up/Down then Enter |
| Death / Victory | R retry, M change difficulty |
| Anywhere | Escape quits |

Jump costs 15 stamina, dodge 30. Toe-pick stops momentum and has a short parry
window. Gold flashing shards are parryable; cyan shards are not. Stamina recovers
faster at speed. LMB does not damage the boss during defense.

## Battle box and patterns

Boxes smoothly morph over 0.5 seconds. The player's relative position moves with
the box and boundaries preserve tangential momentum. The menu box is 540 × 205;
attack boxes range from 510 × 290 to 840 × 265. The follow camera and overworld
are inactive because the entire battle is on screen.

Five handcrafted schedules rotate; each ends after its sequence, generally 6–10 seconds:

- **Oncoming Traffic:** a wide box, descending wreck rows and alternating gaps.
  The final heavy row can be interrupted by a last-second dodge.
- **Chain Sweep:** a tighter box, alternating low chains with clear edge warnings.
  Jump when a chain reaches you.
- **Glacial Wave:** a taller box and central ramp. Cross the ramp at speed 250+
  for a longer jump over the tall wave. Ordinary jump/dodge does not clear it.
- **Whiteout:** alternating streams from box edges with missing lanes. Gold shards
  can be parried; a major parry or three parries can finish a pattern early.
- **Ice Swarm:** homing shards and a horizontal rail. Approach along the rail at
  speed 230+. Grinding for 0.4 seconds with an active swarm nearby disperses it.
  Space jumps off. Skating around the swarm is also possible.

Below half HP, traffic gains occasional shards and Whiteout narrows. Below quarter
HP, chain/wave schedules gain a late projectile. Difficulty and enrage adjust
speed/density without changing player/boss health or base attack damage.

There is no defensive performance score, grade or opening multiplier. Surviving
always earns ATTACK / HEAT / TAUNT. Hazards clear before the command turn.

## Player actions

**ATTACK:** 18 seconds, four vertical D/F/J/K lanes, intentional repeating chunks
with variations between turns. Inputs animate the skater carving/slashing around
the machine; final hits get larger effects. PERFECT contributes 1 damage unit,
GOOD 0.65, MISS 0. Final damage is `240 × hit_units / note_count`, rounded, with a
banked taunt bonus if present. Every difficulty has the same perfect damage potential.
Misses do not end the sequence or cause a separate damage penalty. Result shows
PERFECT / GOOD / MISS counts and damage, without a grade.

**HEAT:** 9 seconds, slower notes and wider windows, with a smaller box and burning
barrel beside the lanes. Each PERFECT immediately restores 6 HP; GOOD restores 4;
MISS restores nothing. HP caps at 100. The flame grows with successful notes.

**TAUNT:** choose one of three original lines. The Plowman answers, becomes enraged
for the next defensive pattern, and banks a ×1.4 bonus for the next successful
ATTACK. Enrage means ×1.15 speed, slightly shorter warnings and one extra density
step. Bonuses do not stack, survive HEAT, and are not consumed by an all-miss attack.

Rhythm is visual, without music synchronization or chords. Release each key between
notes. Wrong/early input consumes the next note as MISS; overdue notes miss
automatically. Hit-stop affects the combo animation only, never rhythm timing.

## Difficulty

| Tuning | CHILL | STANDARD | BLACK ICE |
| --- | --- | --- | --- |
| Attack duration | 18 s | 18 s | 18 s |
| Approximate notes | 20 | 30 | 43 |
| Note interval | .80 s | .52 s | .36 s, syncopated |
| Fall speed | 180 px/s | 220 px/s | 260 px/s |
| PERFECT window | ±115 ms | ±80 ms | ±50 ms |
| GOOD window | ±230 ms | ±165 ms | ±115 ms |
| Hazard speed | ×.80 | ×1 | ×1.18 |
| Telegraph duration | ×1.20 | ×1 | ×.85 |
| Traffic gap | 200 px | 170 px | 145 px |

HEAT uses slower spacing and at least ±120/220 ms PERFECT/GOOD windows.

## Files and tuning

- `thin_ice/combat.py`: phases, box sizes, difficulty, duration, damage, healing,
  enrage/taunt constants and original narration/dialogue pools. Start tuning here.
- `thin_ice/patterns.py`: handcrafted schedules, gaps, warnings, speeds, collision
  shapes and escalation. Pattern lengths live in `Pattern.__init__`.
- `thin_ice/rhythm.py`: note chunks, timing, vertical lanes and feedback.
- `thin_ice/game.py`: state transitions, commands, hazard resolution and combo visuals.
- `thin_ice/boss.py`: primitive vehicle/rider and reaction states.
- `thin_ice/world.py`: animated box, contextual ramp/rail and heat beacon.
- `thin_ice/player.py`: existing skating; containment now uses the current box.
- `thin_ice/settings.py`: original movement, stamina and health constants.
- `thin_ice/effects.py`: reused particles/trails/slashes; configurable slash size.
- `tests/test_gameplay.py`: 27 behavioral tests covering the loop and defense.

The old giant world, free real-time damage and defensive scoring were removed from
the active battle. No assets, APIs, extra enemies, inventory, chords or music were added.

Manual tuning priorities: carving comfort in the tight chain box; ramp approach
from either end; rail capture at oblique angles; Black Ice readability; keyboard
latency; and whether HEAT/TAUNT are attractive over a whole fight. Automated tests
verify rules and transitions, not subjective timing or difficulty balance.
