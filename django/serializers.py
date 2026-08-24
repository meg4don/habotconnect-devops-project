"""
serializers.py
Author: Jishnu Ravi | Contact: ravijishnu431@gmail.com
Position: Junior Cloud & DevOps Engineer (GCP / Django / React) — HabotConnect

Every constraint here is an exact, structural limit — never a loose
CharField() or an implicit type coercion — so validation does not depend
on a human reviewer noticing an edge case.
"""

from rest_framework import serializers
from datetime import date


class StudentOnboardingSerializer(serializers.Serializer):
    student_full_name = serializers.RegexField(
        regex=r"^[A-Za-z][A-Za-z\s'\-]{1,99}$",
        max_length=100,
        error_messages={
            "invalid": (
                "Full name must be 2-100 characters, letters/spaces/hyphens/apostrophes only."
            )
        },
    )

    date_of_birth = serializers.DateField(
        input_formats=["%Y-%m-%d"],
        error_messages={"invalid": "Date of birth must be in YYYY-MM-DD format."},
    )

    has_diagnosed_learning_difficulty = serializers.BooleanField()
    requires_one_on_one_support = serializers.BooleanField()

    guardian_full_name = serializers.RegexField(
        regex=r"^[A-Za-z][A-Za-z\s'\-]{1,99}$",
        max_length=100,
    )

    guardian_email = serializers.EmailField(max_length=254)

    guardian_phone_number = serializers.RegexField(
        regex=r"^\+[1-9]\d{7,14}$",
        error_messages={
            "invalid": "Phone number must be in E.164 format, e.g. +447911123456."
        },
    )

    preferred_session_language = serializers.ChoiceField(
        choices=["English", "French", "Spanish", "Arabic"]
    )

    consent_to_data_processing = serializers.BooleanField()
    emergency_contact_provided = serializers.BooleanField()

    session_frequency_per_week = serializers.IntegerField(min_value=1, max_value=5)

    def validate_date_of_birth(self, value: date) -> date:
        """Structural age gate — mirrors the DCYN age check so the API
        layer and the audit layer can never silently disagree."""
        today = date.today()
        age = (
            today.year
            - value.year
            - ((today.month, today.day) < (value.month, value.day))
        )
        if not (3 <= age <= 18):
            raise serializers.ValidationError(
                f"Student age ({age}) is outside the supported range of 3 to 18 years."
            )
        return value

    def validate_consent_to_data_processing(self, value: bool) -> bool:
        """Onboarding cannot proceed without explicit consent — this is
        a hard business rule, not a soft warning."""
        if value is not True:
            raise serializers.ValidationError(
                "consent_to_data_processing must be true to complete onboarding."
            )
        return value
