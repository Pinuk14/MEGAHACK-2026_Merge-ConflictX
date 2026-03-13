from pathlib import Path
import re
import json
import xml.etree.ElementTree as ET

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
# XML EXTRACTION
# ---------------------------------

def extract_text_from_xml(xml_file: Path) -> tuple[str, str, str | None]:
    """
    Extract all text nodes from XML and return:
    - combined text
    - root tag
    - published date (if available)
    """
    tree = ET.parse(xml_file)
    root = tree.getroot()

    texts = []
    published_date = None

    for elem in root.iter():
        if elem.text and elem.text.strip():
            texts.append(elem.text.strip())

        if published_date is None:
            local_tag = elem.tag.split("}")[-1].lower()
            if local_tag.endswith("date") and elem.text:
                published_date = elem.text.strip()

    combined_text = " ".join(texts)
    return combined_text, root.tag, published_date


# ---------------------------------
# PIPELINE: XML → CLEAN JSON
# ---------------------------------

def clean_xml_directory(input_dir: str, output_json: str):
    records = []
    input_path = Path(input_dir)

    for xml_file in input_path.glob("*.xml"):
        try:
            raw_text, root_tag, published_date = extract_text_from_xml(xml_file)
            cleaned_text = clean_text(raw_text)

            if len(cleaned_text) < 100:
                continue

            metadata = {
                "char_count": len(cleaned_text),
                "root_tag": root_tag,
                "file_path": str(xml_file.resolve()),
            }
            if published_date:
                metadata["published_date"] = published_date

            record = {
                "source": "xml",
                "title": xml_file.stem,
                "content": cleaned_text,
                "metadata": metadata,
            }
            records.append(record)

        except ET.ParseError:
            print(f"⚠️ Skipping invalid XML file: {xml_file.name}")

    # Save JSON output
    output_path = Path(output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"✅ Cleaned {len(records)} XML files")
    print(f"📄 Output saved to {output_path}")


# ---------------------------------
# RUN (Notebook / Script Friendly)
# ---------------------------------




if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[2]
    clean_xml_directory(
        input_dir=project_root / "data" / "raw" / "xmls",
        output_json=project_root / "data" / "processed" / "clean_xml.json",
    )