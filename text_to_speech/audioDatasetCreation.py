"""
audioDatasetCreation.py
─────────────────
Build a TTS-style corpus from a folder of .mp3 / .wav football
commentary.  Guarantees every upload ≤ 25 MiB, fixes truncated
transcripts, and preserves the commentators' excitement.
"""

import logging
logging.basicConfig(
    filename="corrupted_audio.log",
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
)

import csv, pathlib, tempfile, textwrap
from datetime import datetime
from typing import List
from tqdm import tqdm
from pydub import AudioSegment
from openai import AzureOpenAI, BadRequestError
from fetch_api_keys import parse_settings

API_KEYS_TXT = "audioDatasetCreation_LLM_API_keys.txt"
cfg = parse_settings(API_KEYS_TXT)
AZURE_OPENAI_ENDPOINT   = cfg["AZURE_OPENAI_ENDPOINT"]  
AZURE_API_KEY           = cfg["AZURE_API_KEY"]
AZURE_DEPLOYMENT_NAME   = cfg["AZURE_DEPLOYMENT_NAME"]

AUDIO_ROOT              = pathlib.Path("dataset_coqui/chunks_closs")

MAX_UPLOAD_MIB = 25
TARGET_SR      = 22_050 
CHUNK_SEC      = 30

OUTPUT_DIR   = pathlib.Path("dataset_coqui")
OUTPUT_WAVS  = OUTPUT_DIR / "wavs"
OUTPUT_TXTS  = OUTPUT_DIR / "transcriptions"
METADATA_CSV = OUTPUT_DIR / "metadata.csv"

TMP_DIR      = tempfile.TemporaryDirectory()

client = AzureOpenAI(
    api_key       = AZURE_API_KEY,
    api_version   = "2025-03-01-preview",
    azure_endpoint= AZURE_OPENAI_ENDPOINT,
)

PROMPT = textwrap.dedent("""
    Transcribe ONLY the Spanish-language football commentators.
    Preserve interjections, elongated shouts and expressive punctuation
    exactly as spoken (e.g. "¡Gooooooool!", "¡Qué paradón!", "Uhhhh…", "¡Vamos!").
    Ignore crowd noise, music or stadium P.A.
    Output plain text — one sentence per line.
""").strip()

def ensure_dirs():
    OUTPUT_WAVS.mkdir(parents=True, exist_ok=True)
    OUTPUT_TXTS.mkdir(parents=True, exist_ok=True)

def bytes_to_mib(n_bytes: int) -> float:
    return n_bytes / (1024 * 1024)

def save_audiosegment(seg: AudioSegment, path: pathlib.Path):
    seg.export(path, format="wav")

def whisper(path: pathlib.Path) -> str:
    try:
        with path.open("rb") as fp:
            resp = client.audio.transcriptions.create(
                model=AZURE_DEPLOYMENT_NAME,
                file=fp,
                response_format="text",
                prompt=PROMPT,
                language="es",
            )
        return resp.text if hasattr(resp, "text") else str(resp)
    except BadRequestError as e:
        logging.info("BAD_FILE %s  - %s", path, e)
        raise

def convert_to_wav(src: pathlib.Path) -> pathlib.Path:
    if src.suffix.lower() == ".wav":
        audio = AudioSegment.from_wav(src)
    else:
        audio = AudioSegment.from_file(src)

    need_sr   = audio.frame_rate != TARGET_SR
    need_mono = audio.channels   != 1

    if not need_sr and not need_mono and src.suffix.lower() == ".wav":
        return src

    if need_mono:
        audio = audio.set_channels(1)
    if need_sr:
        audio = audio.set_frame_rate(TARGET_SR)

    dst = pathlib.Path(TMP_DIR.name) / f"{src.stem}_{TARGET_SR//1000}k.wav"
    save_audiosegment(audio, dst)
    return dst

def split_if_needed(wav: pathlib.Path) -> List[pathlib.Path]:
    if bytes_to_mib(wav.stat().st_size) <= MAX_UPLOAD_MIB:
        return [wav]

    audio = AudioSegment.from_wav(wav)
    pieces = []
    for i in range(0, len(audio), CHUNK_SEC * 1000):
        chunk = audio[i : i + CHUNK_SEC * 1000]
        tmp = pathlib.Path(TMP_DIR.name) / f"{wav.stem}_{i//1000:05d}.wav"
        save_audiosegment(chunk, tmp)
        pieces.append(tmp)

    return pieces

def create_metadata(input_csv: pathlib.Path, output_csv: pathlib.Path) -> None:
    rows = []
    with input_csv.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="|", quoting=csv.QUOTE_NONE, escapechar="\\")
        for row in reader:
            if len(row) != 2:
                continue
            audio_file, text = row
            rows.append((audio_file, text, text))

    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="|", quoting=csv.QUOTE_NONE, escapechar="\\")
        writer.writerows(rows)

def main():
    ensure_dirs()
    rows = []
    audio_files = sorted(
        p for p in AUDIO_ROOT.rglob("*") if p.suffix.lower() in {".mp3", ".wav"}
    )

    for idx, src in enumerate(tqdm(audio_files, desc="Files")):
        try:
            file_id = f"{idx:05d}"
            wav_dst = OUTPUT_WAVS / f"{file_id}.wav"
            txt_dst = OUTPUT_TXTS / f"{file_id}.txt"

            wav_tmp = convert_to_wav(src)
            chunks = split_if_needed(wav_tmp)

            full_text: List[str] = []
            for part in chunks:
                try:
                    for attempt in (1, 2):
                        text = whisper(part).strip()
                        if len(text) >= 10 or attempt == 2:
                            break
                    full_text.append(text)
                except BadRequestError:
                    tqdm.write(f"Skipping corrupt chunk: {part}")
                    break

            transcript = "\n".join(full_text)

            if not wav_dst.exists():
                if wav_tmp != wav_dst:
                    wav_tmp.replace(wav_dst)
                else:
                    wav_tmp.rename(wav_dst)

            txt_dst.write_text(transcript, encoding="utf-8")
            rows.append([wav_dst.name, transcript])

        except BadRequestError:
            tqdm.write(f"Skipped corrupt file: {src}")
            continue

    with METADATA_CSV.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f, delimiter="|").writerows(rows)

    
    metadata = OUTPUT_DIR / "metadata.csv"
    create_metadata(METADATA_CSV, metadata)

    print(f"Finished {len(rows)} recordings.")
    print(f"WAVs: {OUTPUT_WAVS.resolve()}")
    print(f"TXT: {OUTPUT_TXTS.resolve()}")
    print(f"CSV: {METADATA_CSV.resolve()}")
    print(f"CSV: {metadata.resolve()}")

if __name__ == "__main__":
    t0 = datetime.now()
    main()
    print("Total:", datetime.now() - t0)
