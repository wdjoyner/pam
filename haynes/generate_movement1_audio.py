#!/usr/bin/env python3
"""Generate Kokoro narration WAV files for the Manim Movement I prototype.

Run from the repository root::

    python haynes/generate_movement1_audio.py --voice af_heart --speed 0.94

Outputs are written to ``haynes/audio/movement1`` together with an
``audio_manifest.json`` file containing measured durations.  The Manim scene
reads that manifest at render time, so narration timing does not need to be
hard-coded into the animation source.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24000

NARRATION = {
    "m1_00_opening": (
        "For Euphemia Haynes, mathematics was never merely a collection of calculations. "
        "She wrote that mathematics is no more the art of reckoning and computation than "
        "architecture is the art of making bricks, or painting the art of mixing colors. "
        "The pieces matter. But mathematics begins when we discover the structure that joins them."
    ),
    "m1_01_reason": (
        "A correct answer was not enough. Haynes wanted the student to discover why a statement is true. "
        "She wrote: He understands it, he will retain it for it is his belief. It has not been imposed. "
        "The difference is the difference between receiving an answer and constructing an idea for oneself."
    ),
    "m1_02_inquiry": (
        "Her classroom ideal was active: observation, experimentation, construction, reflection, and then another look. "
        "A mathematical object could be changed, tested, and examined from another direction. "
        "Learning meant participating in the mathematical process rather than watching it from outside."
    ),
    "m1_03_constant_variable": (
        "Haynes also used mathematical concepts as ways of thinking. Consider constant and variable. "
        "Some features of a problem remain fixed while others change. "
        "The important question is not simply what changed, but what the change allows us to see."
    ),
    "m1_04_relationships": (
        "Mathematics is also a study of relationship and dependence. "
        "Change one quantity and another responds. A function records that dependence. "
        "The emphasis shifts from isolated facts toward connections, consequences, and structure."
    ),
    "m1_05_freedom": (
        "And then there is dimension: the number of independent directions in which movement is possible. "
        "A point has no freedom of motion. On a line it gains one direction. On a plane it gains another. "
        "In space, possibility expands again. This gives us a visual metaphor for the larger promise of education: "
        "knowledge can open paths that were previously closed. Mathematics can become an open door."
    ),
}


def _audio_to_numpy(audio) -> np.ndarray:
    if hasattr(audio, "detach"):
        audio = audio.detach()
    if hasattr(audio, "cpu"):
        audio = audio.cpu()
    if hasattr(audio, "numpy"):
        audio = audio.numpy()
    return np.asarray(audio, dtype=np.float32).reshape(-1)


def synthesize(pipeline: KPipeline, text: str, voice: str, speed: float) -> np.ndarray:
    chunks: list[np.ndarray] = []
    for result in pipeline(text, voice=voice, speed=speed):
        audio = result.audio if hasattr(result, "audio") else result[2]
        if audio is not None:
            chunks.append(_audio_to_numpy(audio))
    if not chunks:
        raise RuntimeError("Kokoro returned no audio.")
    return np.concatenate(chunks)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--voice", default="af_heart", help="Kokoro voice ID")
    parser.add_argument("--speed", type=float, default=0.94, help="Speech speed")
    parser.add_argument("--lang", default="a", help="Kokoro language code; a = American English")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    audio_dir = here / "audio" / "movement1"
    audio_dir.mkdir(parents=True, exist_ok=True)

    pipeline = KPipeline(lang_code=args.lang)
    manifest = {
        "engine": "kokoro",
        "language": args.lang,
        "voice": args.voice,
        "speed": args.speed,
        "sample_rate": SAMPLE_RATE,
        "clips": {},
    }

    for clip_id, text in NARRATION.items():
        print(f"Synthesizing {clip_id}...")
        audio = synthesize(pipeline, text, args.voice, args.speed)
        wav_path = audio_dir / f"{clip_id}.wav"
        sf.write(wav_path, audio, SAMPLE_RATE, subtype="PCM_16")
        duration = len(audio) / SAMPLE_RATE
        manifest["clips"][clip_id] = {
            "file": wav_path.name,
            "duration": round(duration, 3),
            "text": text,
        }
        print(f"  {wav_path.relative_to(here)} ({duration:.3f} s)")

    manifest_path = audio_dir / "audio_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {manifest_path.relative_to(here)}")


if __name__ == "__main__":
    main()
