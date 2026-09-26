"""Battle phases, difficulty and easily tuned jam constants. No defense score."""
from dataclasses import dataclass
from enum import Enum


class Phase(str, Enum):
    DIFFICULTY_SELECT = 'DIFFICULTY_SELECT'
    INTRO = 'INTRO'
    ANNOUNCE = 'ANNOUNCE'
    BOX_EXPAND = 'BOX_EXPAND'
    BOSS_PHASE = 'BOSS_PHASE'
    BOX_CONTRACT = 'BOX_CONTRACT'
    FLAVOR = 'FLAVOR'
    COMMAND = 'COMMAND'
    BOX_ACTION = 'BOX_ACTION'
    RHYTHM_ATTACK = 'RHYTHM_ATTACK'
    RHYTHM_HEAT = 'RHYTHM_HEAT'
    TAUNT_CHOICES = 'TAUNT_CHOICES'
    RESULT = 'RESULT'
    BREAKDOWN = 'BREAKDOWN'
    DEAD = 'DEAD'
    VICTORY = 'VICTORY'


@dataclass(frozen=True)
class Difficulty:
    name: str
    attack_speed: float
    telegraph_scale: float
    density: int
    spacing: float
    note_speed: float
    perfect_window: float
    good_window: float
    traffic_gap: int


DIFFICULTIES = {
    'CHILL': Difficulty('CHILL', .80, 1.20, 3, .80, 180, .115, .230, 200),
    'STANDARD': Difficulty('STANDARD', 1.0, 1.0, 5, .52, 220, .080, .165, 170),
    'BLACK ICE': Difficulty('BLACK ICE', 1.18, .85, 7, .36, 260, .050, .115, 145),
}
ATTACK_DURATION = 18.0
HEAT_DURATION = 9.0
ATTACK_MAX_DAMAGE = 240
HEAT_PERFECT_HP = 6
HEAT_GOOD_HP = 4
TAUNT_BONUS = 1.4
ENRAGE_SPEED = 1.15
RESIZE_SECONDS = .5
RESULT_SECONDS = 0.65
PERFECT_DODGE_WINDOW = .09
TYPEWRITER_SPEED = 52
MENU_BOX = (230, 330, 540, 205)
HEAT_BOX = (65, 325, 205, 225)
RHYTHM_BOX = (295, 265, 410, 370)
BOXES = {
    'traffic': (85, 280, 830, 290),
    'chain': (245, 280, 510, 290),
    'wave': (205, 250, 590, 335),
    'whiteout': (155, 270, 690, 305),
    'swarm': (80, 300, 840, 265),
}
PATTERN_ORDER = ('traffic', 'chain', 'wave', 'whiteout', 'swarm')
PATTERN_NAMES = {'traffic':'ONCOMING TRAFFIC', 'chain':'CHAIN SWEEP', 'wave':'GLACIAL WAVE', 'whiteout':'WHITEOUT', 'swarm':'ICE SWARM'}
PATTERN_HINTS = {
    'traffic':'Carve through the gaps. SHIFT can save a late turn.',
    'chain':'Low chains. SPACE jumps them. Watch the edge warning.',
    'wave':'Build speed, then cross the gold ramp as the wall approaches.',
    'whiteout':'Find the open lanes. Only GOLD shards can be parried.',
    'swarm':'Catch the gold rail at speed. Grind until the swarm scatters.',
}

# Original writing; pools cycle rather than immediately repeating.
FLAVOR = (
    'The engine idles with the confidence of a very expensive mistake.',
    'A tiny snowflake lands on the plow. It is immediately evicted.',
    'The fuel gauge points to a hand-drawn picture of a skull.',
    'Somewhere in the machinery, a loose bolt is having a career.',
    'Your skate blades sign a complaint into the ice.',
    'The Plowman adjusts a mirror made from another, smaller plow.',
    'His machine has a cup holder. The cup appears to be welded in.',
    'The ice holds. It sounds annoyed about it.',
    'An exhaust pipe coughs out what might once have been a warranty.',
    'He taps the dashboard like it owes him money.',
)
DIALOGUE = {
    'begin': ('ROAD CLOSED. MANAGEMENT HAS ARRIVED.', 'WELCOME TO MY VERY PERSONAL WINTER.'),
    'normal': ('THAT WAS THE ECONOMY SETTING.', 'THE PLOW IS CUSTOM. SO IS THE DAMAGE.', 'I HAVE RIGHT OF WAY. I BROUGHT MY OWN.'),
    'hit': ('SCRATCHED THE ICE. AND YOU. EFFICIENT.', 'THAT SOUND? PRECISION ENGINEERING.'),
    'counter': ('THE BRAKES WERE A DESIGN CHOICE.', 'STOP FINDING THE GAPS IN MY AUTHORITY.'),
    'heat': ('WARMING UP? I HAVE BEEN IDLING FOR YEARS.', 'THAT BARREL HAS LESS TORQUE THAN MY CUP HOLDER.'),
    'half': ('NO. THE ENGINE IS SUPPOSED TO SOUND LIKE THAT.', 'ENOUGH SKATING LESSONS. HOLD STILL.'),
    'near': ('SHE ONLY NEEDS ONE MORE GOOD RUN.', 'I CAN STILL CLEAR THIS ROAD. WITH YOU ON IT.'),
}
TAUNTS = (
    ('Does it come with a smaller ego?', 'THE EGO IS FACTORY STANDARD.'),
    ('Your headlights look nervous.', 'THEY HAVE SEEN MY DRIVING.'),
    ('I have met quieter avalanches.', 'THEY COULD NOT AFFORD THIS EXHAUST.'),
    ('Is reverse a paid upgrade?', 'I DO NOT ACKNOWLEDGE REVERSE.'),
    ('Wave politely at the cup holder.', 'LEAVE THE CUP HOLDER OUT OF THIS.'),
    ('That plow has excellent parking energy.', 'I WILL PARK IT ON YOUR OPINION.'),
)
