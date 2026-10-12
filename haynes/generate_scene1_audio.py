#!/usr/bin/env python3
"""
Generate Kokoro narration for Euphemia Haynes Scene 1 and synchronize
PAM wait actions to the measured WAV durations.

Run from the PAM repository root:

    python haynes/generate_scene1_audio.py \
        --scene haynes/haynes_scene1.json \
        --voice af_heart \
        --speed 0.94

Outputs:
    haynes/audio/scene01/s01_narr_01.wav
    haynes/audio/scene01/s01_narr_02.wav
    haynes/audio/scene01/audio_manifest.json

The script also updates the two narration wait durations in the JSON file.
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
    "s01_narr_01": (
        "I spent much of my life teaching mathematics. "
        "But teaching mathematics requires us to ask a question "
        "before the first problem is written on the board: "
        "what opportunities are we willing to give the child sitting before us?"
    ),
    "s01_narr_02": (
        "A school may call a decision administrative. "
        "To the student who must live inside that decision, "
        "it can become something much larger."
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


def patch_scene(scene_path: Path, durations: dict[str, float]) -> None:
    data = json.loads(scene_path.read_text())
    wav_to_duration = {
        "audio/scene01/s01_narr_01.wav": durations["s01_narr_01"],
        "audio/scene01/s01_narr_02.wav": durations["s01_narr_02"],
    }

    patched = set()
    for step in data:
        if not isinstance(step, dict):
            continue
        sfx = step.get("sfx")
        if sfx in wav_to_duration:
            step["rt"] = round(wav_to_duration[sfx] + 0.20, 3)
            patched.add(sfx)

    missing = set(wav_to_duration) - patched
    if missing:
        raise RuntimeError(
            "Could not find narration action(s) in JSON: "
            + ", ".join(sorted(missing))
        )

    scene_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scene",
        default="haynes/haynes_scene1.json",
        help="PAM Scene 1 JSON file to patch.",
    )
    parser.add_argument("--voice", default="af_heart", help="Kokoro voice ID.")
    parser.add_argument("--speed", type=float, default=0.94, help="Kokoro speech speed.")
    parser.add_argument("--lang", default="a", help="Kokoro language code; 'a' is American English.")
    args = parser.parse_args()

    scene_path = Path(args.scene).resolve()
    project_dir = scene_path.parent
    audio_dir = project_dir / "audio" / "scene01"
    audio_dir.mkdir(parents=True, exist_ok=True)

    pipeline = KPipeline(lang_code=args.lang)

    durations: dict[str, float] = {}
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
        durations[clip_id] = duration
        manifest["clips"][clip_id] = {
            "file": str(wav_path.relative_to(project_dir)),
            "duration": round(duration, 3),
            "text": text,
        }
        print(f"  {wav_path}  ({duration:.3f} s)")

    manifest_path = audio_dir / "audio_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    patch_scene(scene_path, durations)
    print(f"Patched narration waits in {scene_path}")
    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
