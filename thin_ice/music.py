"""Procedural soundtrack for Thin Ice.

Original frozen-industrial boss music generated entirely with Python + pygame.

IMPORTANT:
The rhythm game imports the timing constants from this module so the
soundtrack and D/F/J/K note charts share the exact same musical grid.
"""

import math
import random
import struct
import tempfile
import wave
from pathlib import Path

import pygame


# ============================================================
# MASTER MUSICAL CLOCK
# ============================================================

BATTLE_BPM = 144

SAMPLE_RATE = 22050
MUSIC_VOLUME = 0.46

BEAT = 60.0 / BATTLE_BPM
EIGHTH = BEAT / 2
SIXTEENTH = BEAT / 4
BAR = BEAT * 4

BATTLE_BARS = 8
BATTLE_LOOP_DURATION = BAR * BATTLE_BARS


# ============================================================
# NOTES
# D minor / frozen-industrial palette
# ============================================================

NOTES = {
    "D2": 73.42,
    "F2": 87.31,
    "G2": 98.00,
    "A2": 110.00,
    "Bb2": 116.54,
    "C3": 130.81,

    "D3": 146.83,
    "F3": 174.61,
    "G3": 196.00,
    "A3": 220.00,
    "Bb3": 233.08,
    "C4": 261.63,

    "D4": 293.66,
    "F4": 349.23,
    "G4": 392.00,
    "A4": 440.00,
    "Bb4": 466.16,
    "C5": 523.25,

    "D5": 587.33,
    "F5": 698.46,
    "A5": 880.00,
}


# ============================================================
# SYNTH WAVEFORMS
# ============================================================

def _square(freq, t):
    return 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0


def _triangle(freq, t):
    return (
        2 / math.pi
    ) * math.asin(
        math.sin(2 * math.pi * freq * t)
    )


def _saw(freq, t):
    phase = (freq * t) % 1.0
    return 2.0 * phase - 1.0


def _envelope(local_t, duration):
    """Fast attack and controlled release."""

    attack = min(
        1.0,
        local_t / 0.008,
    )

    release_start = duration * 0.66

    if local_t > release_start:
        release = max(
            0.0,
            1.0
            - (
                local_t - release_start
            )
            / max(
                0.001,
                duration - release_start,
            ),
        )
    else:
        release = 1.0

    return attack * release


def _add_note(
    buffer,
    start,
    duration,
    freq,
    volume,
    waveform="square",
):
    start_sample = int(start * SAMPLE_RATE)

    end_sample = min(
        len(buffer),
        int(
            (start + duration)
            * SAMPLE_RATE
        ),
    )

    for i in range(
        start_sample,
        end_sample,
    ):
        local_t = (
            i / SAMPLE_RATE
            - start
        )

        if waveform == "triangle":
            value = _triangle(
                freq,
                local_t,
            )

        elif waveform == "saw":
            value = _saw(
                freq,
                local_t,
            )

        else:
            value = _square(
                freq,
                local_t,
            )

        buffer[i] += (
            value
            * volume
            * _envelope(
                local_t,
                duration,
            )
        )


# ============================================================
# PERCUSSION
# ============================================================

def _add_engine_hit(
    buffer,
    start,
    volume=0.30,
):
    """Low mechanical THUMP."""

    start_sample = int(
        start * SAMPLE_RATE
    )

    length = int(
        0.20 * SAMPLE_RATE
    )

    for j in range(length):
        i = start_sample + j

        if i >= len(buffer):
            break

        t = j / SAMPLE_RATE

        decay = math.exp(
            -18 * t
        )

        freq = (
            82
            - 40
            * min(
                1.0,
                t / 0.20,
            )
        )

        tone = math.sin(
            2
            * math.pi
            * freq
            * t
        )

        # Tiny distorted secondary pulse.
        grind = _square(
            freq * 0.5,
            t,
        )

        buffer[i] += (
            tone * 0.8
            + grind * 0.2
        ) * decay * volume


def _add_metal_hit(
    buffer,
    start,
    volume=0.10,
):
    """Short metallic scrap percussion."""

    rng = random.Random(
        int(start * 100000)
        + 773
    )

    start_sample = int(
        start * SAMPLE_RATE
    )

    length = int(
        0.09 * SAMPLE_RATE
    )

    for j in range(length):
        i = start_sample + j

        if i >= len(buffer):
            break

        t = j / SAMPLE_RATE

        decay = math.exp(
            -35 * t
        )

        noise = rng.uniform(
            -1,
            1,
        )

        ring = math.sin(
            2
            * math.pi
            * 1150
            * t
        )

        buffer[i] += (
            noise * 0.55
            + ring * 0.45
        ) * decay * volume


def _add_ice_tick(
    buffer,
    start,
    volume=0.045,
):
    """Tiny high-frequency icy percussion."""

    rng = random.Random(
        int(start * 100000)
        + 9182
    )

    start_sample = int(
        start * SAMPLE_RATE
    )

    length = int(
        0.035 * SAMPLE_RATE
    )

    for j in range(length):
        i = start_sample + j

        if i >= len(buffer):
            break

        decay = (
            1.0
            - j / length
        ) ** 2

        buffer[i] += (
            rng.uniform(-1, 1)
            * decay
            * volume
        )


# ============================================================
# WAV OUTPUT
# ============================================================

def _write_wav(path, samples):
    peak = max(
        1.0,
        max(
            abs(x)
            for x in samples
        ),
    )

    with wave.open(
        str(path),
        "w",
    ) as wav:

        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(
            SAMPLE_RATE
        )

        frames = bytearray()

        for sample in samples:

            normalized = (
                sample / peak
            )

            value = int(
                max(
                    -1,
                    min(
                        1,
                        normalized,
                    ),
                )
                * 27000
            )

            frames.extend(
                struct.pack(
                    "<h",
                    value,
                )
            )

        wav.writeframes(frames)


# ============================================================
# BATTLE THEME
# ============================================================

def _battle_track(path, stage):
    """Create the 8-bar Plowman battle loop."""

    bars = BATTLE_BARS

    duration = (
        BAR * bars
    )

    samples = [
        0.0
    ] * int(
        duration
        * SAMPLE_RATE
    )

    # --------------------------------------------------------
    # ENGINE / BASS
    #
    # Deliberately repetitive.
    # The Plowman should sound like machinery.
    # --------------------------------------------------------

    bass_roots = [
        "D2",
        "D2",
        "Bb2",
        "C3",
        "D2",
        "F2",
        "C3",
        "A2",
    ]

    for bar in range(bars):

        root = bass_roots[bar]

        bar_start = (
            bar * BAR
        )

        # Sustained low engine drone.
        _add_note(
            samples,
            bar_start,
            BAR * 0.92,
            NOTES[root],
            0.105,
            "saw",
        )

        # Mechanical pulses.
        for beat in range(4):

            start = (
                bar_start
                + beat * BEAT
            )

            volume = (
                0.28
                if beat in (0, 2)
                else 0.16
            )

            _add_engine_hit(
                samples,
                start,
                volume,
            )

    # --------------------------------------------------------
    # MAIN PLOWMAN MOTIF
    #
    # Sparse on purpose.
    #
    # D -- F A
    # D -- C Bb
    #
    # gives us an identifiable little boss motif without
    # filling every eighth note.
    # --------------------------------------------------------

    motif = [
        # BAR 1
        (0.0, "D4"),
        (0.5, "F4"),
        (1.0, "A4"),
        (1.5, "F4"),
        (2.0, "G4"),
        (2.5, "A4"),
        (3.0, "F4"),
        (3.5, "D4"),

        # BAR 2
        (4.0, "D4"),
        (4.5, "F4"),
        (5.0, "A4"),
        (5.5, "C5"),
        (6.0, "Bb4"),
        (6.5, "A4"),
        (7.0, "F4"),
        (7.5, "A4"),
    ]

    # Motif occupies two bars.
    phrase_length = BAR * 2

    for phrase in range(4):

        phrase_start = (
            phrase
            * phrase_length
        )

        for beat_offset, note in motif:

            start = (
                phrase_start
                + beat_offset
                * BEAT
            )

            _add_note(
                samples,
                start,
                EIGHTH * 0.72,
                NOTES[note],
                0.115,
                "square",
            )

            # Little frozen overtone.
            _add_note(
                samples,
                start,
                BEAT * 0.32,
                NOTES[note] * 2,
                0.022,
                "triangle",
            )

    # --------------------------------------------------------
    # SCRAP METAL BACKBEAT
    # --------------------------------------------------------

    for bar in range(bars):

        bar_start = (
            bar * BAR
        )

        # Beats 2 and 4.
        for beat in (1, 3):

            _add_metal_hit(
                samples,
                bar_start
                + beat * BEAT,
                0.095
                if stage == 1
                else 0.13,
            )

    # --------------------------------------------------------
    # STAGE TWO
    #
    # Plowman is getting serious.
    # Add offbeat machinery and a low response.
    # --------------------------------------------------------

    if stage >= 2:

        for i in range(
            bars * 8
        ):

            start = (
                i * EIGHTH
            )

            # Offbeat ice percussion.
            if i % 2 == 0:
                _add_ice_tick(
                    samples,
                    start,
                    0.052,
                )

            # Low alternating mechanical pulse.
            if i % 4 == 2:

                freq = (
                    NOTES["D3"]
                    if (i // 4) % 2 == 0
                    else NOTES["C3"]
                )

                _add_note(
                    samples,
                    start,
                    EIGHTH * 0.55,
                    freq,
                    0.055,
                    "square",
                )

    # --------------------------------------------------------
    # STAGE THREE
    #
    # Same song, but machinery is coming apart.
    # --------------------------------------------------------

    if stage >= 3:

        for i in range(
            bars * 16
        ):

            start = (
                i * SIXTEENTH
            )

            # Don't fill every sixteenth.
            # Uneven pattern makes it feel unstable.
            if i % 4 in (1, 3):

                _add_ice_tick(
                    samples,
                    start,
                    0.042,
                )

        # High distress response.
        distress = [
            "D5",
            "A5",
            "F5",
            "D5",
        ]

        for bar in range(bars):

            if bar % 2 == 0:

                start = (
                    bar * BAR
                    + 3 * BEAT
                )

                note = distress[
                    (bar // 2)
                    % len(distress)
                ]

                _add_note(
                    samples,
                    start,
                    BEAT * 0.40,
                    NOTES[note],
                    0.055,
                    "square",
                )

        # Extra metallic crashes at phrase boundaries.
        for bar in (2, 4, 6):

            _add_metal_hit(
                samples,
                bar * BAR,
                0.18,
            )

    _write_wav(
        path,
        samples,
    )


# ============================================================
# HEAT
# ============================================================

def _heat_track(path):
    """Warm, sparse version of the same musical world."""

    bars = 4

    duration = (
        BAR * bars
    )

    samples = [
        0.0
    ] * int(
        duration
        * SAMPLE_RATE
    )

    roots = [
        "D3",
        "Bb2",
        "F3",
        "C3",
    ]

    # Warm sustained harmony.
    for bar in range(bars):

        start = (
            bar * BAR
        )

        root = roots[bar]

        _add_note(
            samples,
            start,
            BAR * 0.92,
            NOTES[root],
            0.10,
            "triangle",
        )

        # Soft fifth.
        _add_note(
            samples,
            start,
            BAR * 0.92,
            NOTES[root] * 1.5,
            0.035,
            "triangle",
        )

    # Recognizable echo of the Plowman motif,
    # but much slower and softer.
    heat_melody = [
        "D4",
        "F4",
        "A4",
        "F4",
        "Bb4",
        "A4",
        "F4",
        "C4",
    ]

    for i, note in enumerate(
        heat_melody
    ):

        start = (
            i * BEAT * 2
        )

        if start >= duration:
            break

        _add_note(
            samples,
            start,
            BEAT * 1.35,
            NOTES[note],
            0.085,
            "triangle",
        )

        # Quiet little ice sparkle on the pulse.
        _add_ice_tick(
            samples,
            start,
            0.018,
        )

    _write_wav(
        path,
        samples,
    )


# ============================================================
# MUSIC MANAGER
# ============================================================

class MusicManager:

    def __init__(self):

        self.enabled = False

        self.current_stage = 1

        self.mode = None

        self.music_dir = (
            Path(
                tempfile.gettempdir()
            )
            / "thin_ice_music"
        )

        try:

            if not pygame.mixer.get_init():
                pygame.mixer.init()

            self.music_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._generate_music()

            self.enabled = True

            print(
                "THIN ICE AUDIO: READY"
            )

        except Exception as exc:

            print(
                "THIN ICE AUDIO DISABLED:",
                exc,
            )

    # --------------------------------------------------------
    # Shared rhythm timing
    # --------------------------------------------------------

    @property
    def beat_duration(self):
        return BEAT

    @property
    def eighth_duration(self):
        return EIGHTH

    @property
    def sixteenth_duration(self):
        return SIXTEENTH

    # --------------------------------------------------------

    def _generate_music(self):

        tracks = {
            "battle_1.wav":
                lambda p:
                _battle_track(p, 1),

            "battle_2.wav":
                lambda p:
                _battle_track(p, 2),

            "battle_3.wav":
                lambda p:
                _battle_track(p, 3),

            "heat.wav":
                _heat_track,
        }

        for (
            filename,
            generator,
        ) in tracks.items():

            path = (
                self.music_dir
                / filename
            )

            # Regenerate every launch during development.
            generator(path)

    # --------------------------------------------------------

    def _play(
        self,
        filename,
        volume=MUSIC_VOLUME,
    ):

        if not self.enabled:
            return

        path = (
            self.music_dir
            / filename
        )

        try:

            pygame.mixer.music.load(
                str(path)
            )

            pygame.mixer.music.set_volume(
                volume
            )

            pygame.mixer.music.play(
                -1
            )

        except pygame.error as exc:

            print(
                "MUSIC PLAYBACK ERROR:",
                exc,
            )

    # --------------------------------------------------------

    def start_battle(self):

        self.mode = "battle"

        self.current_stage = 1

        self._play(
            "battle_1.wav"
        )

    # --------------------------------------------------------

    def update_intensity(
        self,
        hp_ratio,
    ):

        if self.mode != "battle":
            return

        if hp_ratio <= 0.30:
            wanted = 3

        elif hp_ratio <= 0.60:
            wanted = 2

        else:
            wanted = 1

        if wanted == self.current_stage:
            return

        self.current_stage = wanted

        pygame.mixer.music.fadeout(
            120
        )

        self._play(
            f"battle_{wanted}.wav"
        )

    # --------------------------------------------------------

    def heat(self):

        if not self.enabled:
            return

        self.mode = "heat"

        pygame.mixer.music.fadeout(
            120
        )

        self._play(
            "heat.wav",
            volume=0.36,
        )

    # --------------------------------------------------------

    def resume_battle(self):

        if not self.enabled:
            return

        self.mode = "battle"

        self._play(
            f"battle_{self.current_stage}.wav"
        )

    # --------------------------------------------------------

    def taunt_drop(self):

        if self.enabled:

            pygame.mixer.music.set_volume(
                0.055
            )

    # --------------------------------------------------------

    def restore_volume(self):

        if self.enabled:

            pygame.mixer.music.set_volume(
                MUSIC_VOLUME
            )

    # --------------------------------------------------------

    def stop(
        self,
        fade_ms=500,
    ):

        if self.enabled:

            pygame.mixer.music.fadeout(
                fade_ms
            )

            self.mode = None