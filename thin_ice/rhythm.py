"""Vertical beat-synced rhythm system for Thin Ice.

Every note is a single D/F/J/K press.

The rhythm chart shares timing constants with music.py so notes
are generated on the same 144 BPM musical grid as the soundtrack.
"""

from dataclasses import dataclass

import pygame

from .combat import ATTACK_DURATION, HEAT_DURATION
from .utils import draw_text
from .music import BEAT, EIGHTH, SIXTEENTH


# ============================================================
# INPUT / VISUAL CONSTANTS
# ============================================================

INPUTS = {
    pygame.K_d: 'D',
    pygame.K_f: 'F',
    pygame.K_j: 'J',
    pygame.K_k: 'K',
}

LANES = {
    'D': 350,
    'F': 450,
    'J': 550,
    'K': 650,
}

COLORS = {
    'D': (171, 225, 242),
    'F': (210, 239, 239),
    'J': (149, 199, 225),
    'K': (224, 232, 244),
}

HIT_Y = 590
TOP_Y = 280

LEAD_IN = 2.0


# ============================================================
# NOTE PATTERNS
# ============================================================

CHUNKS = (
    ('D', 'F', 'J', 'K', 'J', 'F'),
    ('F', 'D', 'J', 'F', 'K', 'J'),
    ('J', 'K', 'F', 'D', 'F', 'J'),
    ('K', 'J', 'D', 'F', 'J', 'K'),
)


# ============================================================
# NOTE
# ============================================================

@dataclass
class Note:
    key: str
    target: float
    judgment: str | None = None


# ============================================================
# RHYTHM SEQUENCE
# ============================================================

class RhythmSequence:

    def __init__(self, difficulty, action, turn=0):

        self.action = action
        self.elapsed = 0.0

        self.duration = (
            HEAT_DURATION
            if action == 'HEAT'
            else ATTACK_DURATION
        )

        self.feedback = 'READY'
        self.feedback_timer = 1.2

        self.combo = 0

        # ----------------------------------------------------
        # HIT WINDOWS
        # ----------------------------------------------------

        self.perfect_window = difficulty.perfect_window
        self.good_window = difficulty.good_window
        self.note_speed = difficulty.note_speed

        # HEAT is more forgiving.
        if action == 'HEAT':

            self.note_speed *= 0.72

            self.perfect_window = max(
                0.12,
                self.perfect_window * 1.3,
            )

            self.good_window = max(
                0.22,
                self.good_window * 1.3,
            )

        # ----------------------------------------------------
        # GENERATE NOTES
        # ----------------------------------------------------

        self.notes = []

        target = LEAD_IN
        note_index = 0

        while target < self.duration - 0.35:

            # Rotate note patterns between turns.
            chunk = CHUNKS[
                (turn + note_index // 6)
                % len(CHUNKS)
            ]

            key = chunk[
                note_index % len(chunk)
            ]

            # Normal note.
            self.notes.append(
                Note(
                    key=key,
                    target=target,
                )
            )

            # ------------------------------------------------
            # SLIDER
            #
            # Every so often, create another note in the
            # same lane one eighth-note later.
            #
            # Visually these two notes are connected.
            # Mechanically the player taps the key twice.
            # ------------------------------------------------

            if (
                action == 'ATTACK'
                and note_index % 8 == 5
            ):

                slider_target = target + EIGHTH

                if slider_target < self.duration - 0.35:

                    self.notes.append(
                        Note(
                            key=key,
                            target=slider_target,
                        )
                    )

            note_index += 1

            # ------------------------------------------------
            # HEAT
            # Quarter notes.
            # ------------------------------------------------

            if action == 'HEAT':

                target += BEAT

            # ------------------------------------------------
            # CHILL
            # Quarter notes.
            # ------------------------------------------------

            elif difficulty.name == 'CHILL':

                target += BEAT

            # ------------------------------------------------
            # STANDARD
            # Mostly eighth notes with some breathing room.
            # ------------------------------------------------

            elif difficulty.name == 'STANDARD':

                if note_index % 6 in (1, 4):

                    target += BEAT

                else:

                    target += EIGHTH

            # ------------------------------------------------
            # BLACK ICE
            # Fast eighths with sixteenth-note bursts.
            # ------------------------------------------------

            else:

                if note_index % 6 in (2, 5):

                    target += SIXTEENTH

                else:

                    target += EIGHTH


    # ========================================================
    # JUDGMENT
    # ========================================================

    def judge(self, note, result):

        note.judgment = result

        self.feedback = result
        self.feedback_timer = 0.42

        if result != 'MISS':
            self.combo += 1

        else:
            self.combo = 0

        return result


    # ========================================================
    # INPUT
    # ========================================================

    def press(self, key):

        if key not in LANES:
            return None

        # Get the next unresolved note.
        note = next(
            (
                n
                for n in self.notes
                if n.judgment is None
            ),
            None,
        )

        if note is None:
            return None

        error = abs(
            self.elapsed
            - note.target
        )

        # Wrong key or outside timing window.
        if (
            note.key != key
            or error > self.good_window
        ):

            return self.judge(
                note,
                'MISS',
            )

        # Perfect.
        if error <= self.perfect_window:

            return self.judge(
                note,
                'PERFECT',
            )

        # Otherwise Good.
        return self.judge(
            note,
            'GOOD',
        )


    # ========================================================
    # UPDATE
    # ========================================================

    def update(self, dt):

        # Rhythm clock never pauses.
        self.elapsed += dt

        self.feedback_timer = max(
            0,
            self.feedback_timer - dt,
        )

        missed = []

        # Automatically miss notes that passed the hit window.
        for note in self.notes:

            if (
                note.judgment is None
                and self.elapsed
                > note.target + self.good_window
            ):

                self.judge(
                    note,
                    'MISS',
                )

                missed.append(
                    note
                )

        return missed


    # ========================================================
    # FINISHED?
    # ========================================================

    @property
    def done(self):

        return (
            self.elapsed >= self.duration
            and all(
                note.judgment is not None
                for note in self.notes
            )
        )


    # ========================================================
    # RESULTS
    # ========================================================

    @property
    def counts(self):

        return {
            grade: sum(
                note.judgment == grade
                for note in self.notes
            )
            for grade in (
                'PERFECT',
                'GOOD',
                'MISS',
            )
        }


    @property
    def hit_units(self):

        counts = self.counts

        return (
            counts['PERFECT']
            + 0.65 * counts['GOOD']
        )


    # ========================================================
    # NOTE POSITION
    # ========================================================

    def note_y(self, note):

        return (
            HIT_Y
            - (
                note.target
                - self.elapsed
            )
            * self.note_speed
        )


    # ========================================================
    # DRAW
    # ========================================================

    def draw(
        self,
        surface,
        font,
        small_font,
    ):

        # ----------------------------------------------------
        # LANES
        # ----------------------------------------------------

        for key, x in LANES.items():

            pygame.draw.rect(
                surface,
                (14, 29, 39),
                (
                    x - 44,
                    TOP_Y,
                    88,
                    HIT_Y - TOP_Y + 34,
                ),
            )

            pygame.draw.line(
                surface,
                (69, 101, 117),
                (
                    x - 44,
                    TOP_Y,
                ),
                (
                    x - 44,
                    HIT_Y + 30,
                ),
                1,
            )

            # Timing window.
            window = (
                self.good_window
                * self.note_speed
            )

            pygame.draw.rect(
                surface,
                (42, 62, 68),
                (
                    x - 42,
                    HIT_Y - window,
                    84,
                    window * 2,
                ),
            )

            draw_text(
                surface,
                key,
                font,
                (
                    x,
                    HIT_Y + 25,
                ),
                COLORS[key],
                center=True,
            )

        # ----------------------------------------------------
        # HIT / BLADE LINE
        # ----------------------------------------------------

        pygame.draw.line(
            surface,
            (237, 250, 252),
            (
                304,
                HIT_Y,
            ),
            (
                696,
                HIT_Y,
            ),
            4,
        )

        pygame.draw.line(
            surface,
            (121, 181, 206),
            (
                308,
                HIT_Y + 5,
            ),
            (
                692,
                HIT_Y + 5,
            ),
            1,
        )

        # ----------------------------------------------------
        # NOTE DRAWING AREA
        # ----------------------------------------------------

        old_clip = surface.get_clip()

        surface.set_clip(
            pygame.Rect(
                303,
                TOP_Y,
                394,
                HIT_Y - TOP_Y + 10,
            )
        )

        # ====================================================
        # SLIDER TRAILS
        # ====================================================

        for i in range(
            len(self.notes) - 1
        ):

            first = self.notes[i]
            second = self.notes[i + 1]

            # A slider is two consecutive notes:
            #
            # - same lane
            # - exactly one eighth-note apart
            is_slider = (
                first.key == second.key
                and abs(
                    (
                        second.target
                        - first.target
                    )
                    - EIGHTH
                ) < 0.001
            )

            if not is_slider:
                continue

            # Once both ends have been hit/missed,
            # stop drawing the slider.
            if (
                first.judgment is not None
                and second.judgment is not None
            ):
                continue

            x = LANES[
                first.key
            ]

            y1 = self.note_y(
                first
            )

            y2 = self.note_y(
                second
            )

            # Only draw the visible part.
            y1 = max(
                TOP_Y,
                min(
                    HIT_Y,
                    y1,
                ),
            )

            y2 = max(
                TOP_Y,
                min(
                    HIT_Y,
                    y2,
                ),
            )

            # Thick icy body.
            pygame.draw.line(
                surface,
                COLORS[first.key],
                (
                    x,
                    y1,
                ),
                (
                    x,
                    y2,
                ),
                10,
            )

            # Bright center highlight.
            pygame.draw.line(
                surface,
                (235, 250, 255),
                (
                    x,
                    y1,
                ),
                (
                    x,
                    y2,
                ),
                3,
            )

        # ====================================================
        # FALLING NOTES
        # ====================================================

        for note in self.notes:

            if note.judgment is not None:
                continue

            x = LANES[
                note.key
            ]

            y = self.note_y(
                note
            )

            if (
                TOP_Y - 20
                <= y
                <= HIT_Y + 20
            ):

                # Chunky ice shard.
                pygame.draw.polygon(
                    surface,
                    COLORS[note.key],
                    [
                        (
                            x - 26,
                            y - 7,
                        ),
                        (
                            x + 20,
                            y - 12,
                        ),
                        (
                            x + 27,
                            y + 6,
                        ),
                        (
                            x - 17,
                            y + 12,
                        ),
                    ],
                )

                # Ice highlight.
                pygame.draw.line(
                    surface,
                    (248, 253, 255),
                    (
                        x - 18,
                        y - 5,
                    ),
                    (
                        x + 19,
                        y - 8,
                    ),
                    2,
                )

        surface.set_clip(
            old_clip
        )

        # ----------------------------------------------------
        # FEEDBACK
        # ----------------------------------------------------

        if self.feedback_timer > 0:

            if self.feedback == 'MISS':

                feedback_color = (
                    255,
                    148,
                    130,
                )

            else:

                feedback_color = (
                    230,
                    245,
                    210,
                )

            draw_text(
                surface,
                self.feedback,
                font,
                (
                    805,
                    425,
                ),
                feedback_color,
                center=True,
            )

        # ----------------------------------------------------
        # TIMER
        # ----------------------------------------------------

        draw_text(
            surface,
            f'{max(0, self.duration - self.elapsed):.1f}s',
            small_font,
            (
                805,
                467,
            ),
            (149, 180, 196),
            center=True,
        )

        # ----------------------------------------------------
        # CONTROLS
        # ----------------------------------------------------

        draw_text(
            surface,
            'D   F   J   K  /  TAP AT THE BLADE LINE',
            small_font,
            (
                500,
                658,
            ),
            center=True,
        )