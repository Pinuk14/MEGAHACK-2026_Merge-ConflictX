from pathlib import Path
import json
import re
import soundfile as sf
import whisper


# ---------------------------------
# TEXT CLEANING HELPERS
# ---------------------------------

def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("\u00a0", " ")
    return text


def cleanup_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    text = normalize_text(text)
    text = cleanup_whitespace(text)
    return text


# ---------------------------------
# AUDIO METADATA
# ---------------------------------

def get_audio_metadata(wav_path: Path):
    audio, samplerate = sf.read(wav_path)
    duration = len(audio) / samplerate
    return duration, samplerate


# ---------------------------------
# PIPELINE: WAV → TEXT → CLEAN JSON
# ---------------------------------

def clean_wav_directory(input_dir: str, output_json: str, model_size="base"):
    records = []
    input_path = Path(input_dir)

    print(" Loading Whisper model...")
    model = whisper.load_model(model_size)

    for wav_file in input_path.rglob("*.wav"):
        try:
            print(f" Transcribing {wav_file.name}")

            wav_path = wav_file.resolve()
            result = model.transcribe(str(wav_path))
            raw_text = result.get("text", "")

            cleaned_text = clean_text(raw_text)

            if len(cleaned_text) < 30:
                continue

            duration, sample_rate = get_audio_metadata(wav_file)

            metadata = {
                "duration_sec": round(duration, 2),
                "sample_rate": sample_rate,
                "language": result.get("language"),
                "file_path": str(wav_file.resolve()),
            }

            record = {
                "source": "audio",
                "title": wav_file.stem,
                "content": cleaned_text,
                "metadata": metadata,
            }

            records.append(record)

        except Exception as e:
            print(f"⚠️ Failed to process {wav_file.name}: {e}")

    # Save output
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"✅ Cleaned {len(records)} WAV files")
    print(f"📄 Output saved to {output_path}")


# ---------------------------------
# RUN
# ---------------------------------

# if __name__ == "__main__":
#     clean_wav_directory(
#         input_dir="data/raw",
#         output_json="data/processed/clean_audio.json",
#         model_size="base"   # tiny | base | small | medium | large
#     )



if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    clean_wav_directory(
        input_dir=project_root / "data" / "raw" / "wavs",
        output_json=project_root / "data" / "processed" / "clean_audio.json",
        model_size="base"   # tiny | base | small | medium | large
    )