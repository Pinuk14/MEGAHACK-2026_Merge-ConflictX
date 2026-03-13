from datetime import datetime

ALLOWED_SOURCES = {"pdf", "xml", "txt", "audio", "csv"}
ALLOWED_TYPES = {
    "Legal Documents",
    "Numeric Values",
    "Case Studies",
    "News Articles"
}


def validate_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except Exception:
        return False


def validate_record(record: dict):
    """
    Returns:
    - is_valid (bool)
    - corrected_record (dict)
    - warnings (list)
    - errors (list)
    """
    warnings = []
    errors = []

    # ---------- source ----------
    if record.get("source") not in ALLOWED_SOURCES:
        errors.append("Invalid or missing source")

    # ---------- title ----------
    title = record.get("title") or record.get("Title")
    if not isinstance(title, str) or not title.strip():
        errors.append("Title must be a non-empty string")

    # ---------- content ----------
    content = record.get("content") or record.get("Content")
    if not isinstance(content, str) or not content.strip():
        errors.append("Content must be a non-empty string")

    # ---------- published_date (AUTO-FIX) ----------
    pub_date = record.get("Published_date") or record.get("published_date")
    if not pub_date:
        today = datetime.today().strftime("%Y-%m-%d")
        # Set in both possible locations
        record["Published_date"] = today
        record["published_date"] = today
        warnings.append(
            f"Published_date missing → auto-filled with {today}"
        )
    elif not validate_date(pub_date):
        errors.append("Published_date must be in YYYY-MM-DD format")

    # ---------- original_content ----------
    orig_content = record.get("Original_content") or record.get("original_content")
    if not isinstance(orig_content, str) or not orig_content.strip():
        errors.append("Original_content must be a non-empty string")

    # ---------- metadata (handle both uppercase and lowercase) ----------
    metadata = record.get("metadata") or record.get("Metadata")
    if not isinstance(metadata, dict):
        errors.append("Metadata must be an object")
        return False, record, warnings, errors

    # ---------- page_count (AUTO-FIX) ----------
    page_count = metadata.get("Page_count") or metadata.get("page_count")
    if page_count is None:
        metadata["Page_count"] = 0
        warnings.append("page_count was null → auto-set to 0")
    elif not isinstance(page_count, (int, float)) or page_count < 0:
        errors.append("Page_count must be a number ≥ 0")

    # ---------- numeric checks ----------
    def check_number(key, min_v, max_v=None):
        # Try multiple possible field names
        val = metadata.get(key) or metadata.get(f"{key}_score") or metadata.get(key.lower())
        if val is None:
            warnings.append(f"{key} is missing")
            return
        if not isinstance(val, (int, float)):
            errors.append(f"{key} must be a number")
        else:
            if val < min_v or (max_v is not None and val > max_v):
                errors.append(f"{key} out of allowed range: {val}")

    # Check with proper field names from pipeline
    check_number("Accuracy", 0, 1.0)  # Pipeline uses 0-1 range, not 0-100
    check_number("Usability", 1, 10)
    check_number("Char_count", 0)
    check_number("Outliers", 0, 5)

    # ---------- metadata.type (handle as list or string) ----------
    doc_type = metadata.get("Type") or metadata.get("type")
    if doc_type:
        # Type can be a list or a single string
        if isinstance(doc_type, list):
            # Check if any type in the list is valid
            valid_types = [t for t in doc_type if t in ALLOWED_TYPES]
            if not valid_types:
                errors.append(f"Invalid metadata.Type value: {doc_type}")
        elif isinstance(doc_type, str):
            if doc_type not in ALLOWED_TYPES:
                errors.append(f"Invalid metadata.Type value: {doc_type}")
        else:
            errors.append("metadata.Type must be a string or list")
    else:
        warnings.append("metadata.Type is missing")

    is_valid = len(errors) == 0
    return is_valid, record, warnings, errors
