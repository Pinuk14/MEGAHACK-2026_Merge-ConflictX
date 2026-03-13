from pathlib import Path
import re
import json

# ---------------------------------
# TEXT CLEANING FUNCTIONS
# ---------------------------------

def normalize_text(text: str) -> str:
    text = text.lower()
    text = text.replace("\u00a0", " ")
    return text


def remove_headers_footers(text: str) -> str:
    lines = text.split("\n")
    cleaned = []

    for line in lines:
        line = line.strip()
        if (
            re.match(r"^page\s*\d+", line) or
            re.match(r"^chapter\s*\d+", line) or
            len(line) < 3
        ):
            continue
        cleaned.append(line)

    return "\n".join(cleaned)


def fix_broken_lines(text: str) -> str:
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"\n(?=[a-z])", " ", text)
    return text


def cleanup_whitespace(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_text(text: str) -> str:
    """
    MASTER CLEANING FUNCTION
    """
    text = normalize_text(text)
    text = remove_headers_footers(text)
    text = fix_broken_lines(text)
    text = cleanup_whitespace(text)
    return text


# ---------------------------------
# PIPELINE: TXT → CLEAN JSON
# ---------------------------------

def clean_txt_directory(input_dir: str, output_json: str):
    records = []
    record_id = 1

    input_path = Path(input_dir)

    for txt_file in input_path.glob("*.txt"):
        raw_text = txt_file.read_text(encoding="utf-8", errors="ignore")
        cleaned_text = clean_text(raw_text)

        # Quality filter
        if len(cleaned_text) < 100:
            continue

        record = {
            "id": record_id,
            "source": "txt",
            "title": txt_file.stem,
            "content": cleaned_text,
            "metadata": {
                "char_count": len(cleaned_text),
                "file_path": str(txt_file.resolve())
            }
        }

        records.append(record)
        record_id += 1

    # Save JSON
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"✅ Cleaned {len(records)} text files")
    print(f"📄 Output saved to {output_path}")


# ---------------------------------
# RUN (Notebook / Script Friendly)
# ---------------------------------

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    clean_txt_directory(
        input_dir=project_root / "data" / "raw" / "txts",
        output_json=project_root / "data" / "processed" / "clean_text.json",
    )
