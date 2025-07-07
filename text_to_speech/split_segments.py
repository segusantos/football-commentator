#!/usr/bin/env python3
"""
split_segments.py
---------------------
Splits an audio file into 4-8 second fragments, cutting only at pauses.

Requirements:
    pip install pydub librosa soundfile
    # On Linux: sudo apt-get install ffmpeg  (pydub uses ffmpeg internally)
"""

from pydub import AudioSegment, silence
import argparse
import os
from pathlib import Path

# ---------- "Smart" parameters ---------- #
TARGET_SR = 22_050          # Hz
MIN_LEN = 4_000             # ms (4 s)
MAX_LEN = 8_000             # ms (8 s)
SILENCE_THRESH = -40        # dBFS, ↓ = more tolerant
MIN_SIL_MS = 300            # ms of silence needed to consider "pause"
# -------------------------------------- #

def slice_audio(in_path: Path, out_dir: Path):
    audio = AudioSegment.from_file(in_path)

    # 1) Resample if necessary
    if audio.frame_rate != TARGET_SR:
        audio = audio.set_frame_rate(TARGET_SR)

    out_dir.mkdir(parents=True, exist_ok=True)
    cursor_ms = 0
    idx = 0

    while cursor_ms < len(audio):
        # Window that never exceeds MAX_LEN
        win_end = min(cursor_ms + MAX_LEN, len(audio))
        window = audio[cursor_ms:win_end]

        # Search for silences within the window
        silences = silence.detect_silence(
            window,
            min_silence_len=MIN_SIL_MS,
            silence_thresh=SILENCE_THRESH,
            seek_step=10        # ms, finer → more precise, slower
        )

        # Choose the FIRST silence after MIN_LEN
        cut_ms = None
        for s_start, _ in silences:
            if s_start >= MIN_LEN:
                cut_ms = cursor_ms + s_start
                break

        # If no appropriate silence, cut hard at MAX_LEN
        if cut_ms is None:
            cut_ms = win_end

        # Export fragment
        chunk = audio[cursor_ms:cut_ms]
        chunk_path = out_dir / f"chunk_{idx:03d}.wav"
        chunk.export(chunk_path, format="wav")
        print(f"· Saved {chunk_path} ({len(chunk)/1000:.2f} s)")

        idx += 1
        cursor_ms = cut_ms   # Advance to next fragment


def main():
    parser = argparse.ArgumentParser(
        description="Splits a WAV into 4-8 second chunks cutting at silences."
    )
    parser.add_argument("input", type=Path, help="Input audio file (.wav/.mp3/...)")
    parser.add_argument(
        "-o", "--out-dir", type=Path, default=Path("chunks"),
        help="Directory to save fragments (default: ./chunks)"
    )
    args = parser.parse_args()

    slice_audio(args.input, args.out_dir)
    print("✔ Process finished.")


if __name__ == "__main__":
    main()

# Example usage:
# python split_segments.py "dataset_coqui/relato_closs_7min_nr.wav" -o "dataset_coqui/chunks_closs"
