"""
dcyn_library.py
Author: Jishnu Ravi | Contact: ravijishnu431@gmail.com
Position: Junior Cloud & DevOps Engineer (GCP / Django / React) — HabotConnect

DCYN = "Deconstructed / Categorical Yes-No" validation library.

Purpose: Every field on the student onboarding form is reduced to an
explicit, auditable boolean outcome BEFORE it reaches the database or
downstream analytics. This removes human judgment calls entirely —
a reviewer never has to interpret ambiguous input; the system already
resolved it to Yes or No, with a stated reason on every result.

Each function returns a DCYNResult: a plain, structured record —
never a bare bool — so failed validations carry a reason (audit trail)
instead of relying on someone remembering why a field failed.
"""

from dataclasses import dataclass
from datetime import date, datetime
import re


@dataclass(frozen=True)
class DCYNResult:
    field_name: str
    answer: bool  # True = Yes (valid/compliant), False = No
    reason: str  # Always populated — no silent Yes/No


def check_full_name(value: str, field_name: str = "full_name") -> DCYNResult:
    """Yes only if 2-100 chars, letters/spaces/hyphens/apostrophes only."""
    pattern = r"^[A-Za-z][A-Za-z\s'\-]{1,99}$"
    is_valid = bool(value) and bool(re.match(pattern, value.strip()))
    reason = (
        "Valid full name format"
        if is_valid
        else "Name missing, too short, or contains invalid characters"
    )
    return DCYNResult(field_name, is_valid, reason)


def check_date_of_birth(value: str, min_age: int = 3, max_age: int = 18) -> DCYNResult:
    """Yes only if the DOB parses AND the resulting age falls in the
    program's supported range for Learning Support Assistant services."""
    try:
        dob = datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return DCYNResult(
            "date_of_birth", False, "Date is not valid ISO 8601 (YYYY-MM-DD)"
        )

    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    is_valid = min_age <= age <= max_age
    reason = (
        f"Age {age} is within supported range ({min_age}-{max_age})"
        if is_valid
        else f"Age {age} falls outside supported range ({min_age}-{max_age})"
    )
    return DCYNResult("date_of_birth", is_valid, reason)


def check_boolean_field(field_name: str, value) -> DCYNResult:
    """Generic Yes/No resolver for fields that must be strictly boolean —
    never a string like 'yes', 'true', or a null. No implicit coercion."""
    is_valid = isinstance(value, bool)
    reason = (
        "Strict boolean received"
        if is_valid
        else f"Expected strict boolean, received {type(value).__name__}"
    )
    return DCYNResult(field_name, is_valid, reason)


def check_email(value: str) -> DCYNResult:
    pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
    is_valid = bool(value) and bool(re.match(pattern, value.strip()))
    reason = "Valid email format" if is_valid else "Email missing or malformed"
    return DCYNResult("guardian_email", is_valid, reason)


def check_phone_number(value: str) -> DCYNResult:
    """Yes only for E.164 format — required so downstream SMS/contact
    systems never have to guess a dialing format."""
    pattern = r"^\+[1-9]\d{7,14}$"
    is_valid = bool(value) and bool(re.match(pattern, value.strip()))
    reason = (
        "Valid E.164 phone format"
        if is_valid
        else "Phone number missing or not in E.164 format"
    )
    return DCYNResult("guardian_phone_number", is_valid, reason)


def check_session_frequency(value, min_val: int = 1, max_val: int = 5) -> DCYNResult:
    is_valid = isinstance(value, int) and min_val <= value <= max_val
    reason = (
        f"Value within allowed range ({min_val}-{max_val})"
        if is_valid
        else f"Value missing, non-integer, or outside allowed range ({min_val}-{max_val})"
    )
    return DCYNResult("session_frequency_per_week", is_valid, reason)


def check_language(
    value: str, allowed: tuple = ("English", "French", "Spanish", "Arabic")
) -> DCYNResult:
    is_valid = value in allowed
    reason = (
        "Language is in the supported list"
        if is_valid
        else f"'{value}' is not in the supported language list {allowed}"
    )
    return DCYNResult("preferred_session_language", is_valid, reason)


def run_dcyn_validation(payload: dict) -> list:
    """Runs the full onboarding payload through every DCYN check and
    returns one auditable result per field — the single source of truth
    the serializer (below) and any human reviewer both rely on."""
    return [
        check_full_name(payload.get("student_full_name", ""), "student_full_name"),
        check_date_of_birth(payload.get("date_of_birth", "")),
        check_boolean_field(
            "has_diagnosed_learning_difficulty",
            payload.get("has_diagnosed_learning_difficulty"),
        ),
        check_boolean_field(
            "requires_one_on_one_support", payload.get("requires_one_on_one_support")
        ),
        check_full_name(payload.get("guardian_full_name", ""), "guardian_full_name"),
        check_email(payload.get("guardian_email", "")),
        check_phone_number(payload.get("guardian_phone_number", "")),
        check_language(payload.get("preferred_session_language", "")),
        check_boolean_field(
            "consent_to_data_processing", payload.get("consent_to_data_processing")
        ),
        check_boolean_field(
            "emergency_contact_provided", payload.get("emergency_contact_provided")
        ),
        check_session_frequency(payload.get("session_frequency_per_week")),
    ]
