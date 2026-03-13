from __future__ import annotations

from pathlib import Path
from typing import List

import cv2
import easyocr
import numpy as np


class OCRModule:
    """OCR helper for extracting text from page images using EasyOCR."""

    def __init__(self, languages: List[str] | None = None, confidence_threshold: float = 0.5) -> None:
        self.languages = languages or ["en"]
        self.confidence_threshold = confidence_threshold
        self.reader = easyocr.Reader(self.languages)

    def extract_text_from_image_path(self, image_path: str | Path) -> str:
        """Extract text from an image file path."""
        image = cv2.imread(str(image_path))
        if image is None:
            return ""
        return self.extract_text_from_array(image)

    def extract_text_from_array(self, image: np.ndarray) -> str:
        """Extract text from an in-memory image array."""
        if image is None or image.size == 0:
            return ""

        # Basic preprocessing for better OCR quality
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        denoised = cv2.medianBlur(gray, 3)
        _, thresholded = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        results = self.reader.readtext(thresholded)

        words: List[str] = []
        for _, word, confidence in results:
            if confidence > self.confidence_threshold:
                words.append(word)

        return " ".join(words)
