"""
Validation module for strict data validation and reporting.
"""

from .strict_validator import validate_record
from .error_report_pdf import generate_report

__all__ = [
    "validate_record", "generate_report"
]