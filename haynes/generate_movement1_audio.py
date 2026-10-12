#!/usr/bin/env python3
"""Generate Kokoro narration WAV files for the Manim Movement I prototype.

Run from the repository root::

    python haynes/generate_movement1_audio.py --voice af_heart --speed 0.94

Outputs are written to ``haynes/audio/movement1`` together with an
``audio_manifest.json`` file containing measured durations.  The Manim scene
reads that manifest at render time, so narration timing does not need to be
hard-coded into the animation source.

The narration text itself lives in ``haynes_movement1_text.json``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24000

TEXT_PATH = Path(__file__).resolve().parent / "haynes_movement1_text.json"


def load_narration(path: Path = TEXT_PATH) -> dict[str, str]:
    """Read the narration from the shared text file.

    Each clip may be one string or a list of sentences; lists are joined
    with single spaces.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        clip_id: " ".join(text) if isinstance(text, list) else text
        for clip_id, text in data["narration"].items()
    }


NARRATION = load_narration()


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
