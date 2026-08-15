"""
Phase 11F — Extraction Contract Tests (Prompt V2 policy validation).

Tests the extraction policy promised by Prompt V2:
- completeness (all independent fields extracted)
- multilingual preservation (Arabic, Cyrillic)
- fidelity (approximate values not fabricated)
- phone/email formatting robustness
- distinguishing marks extraction
- canonical key normalization
- unknown key rejection
- benchmark non-contamination
"""

import ast
import pathlib

import pytest

# ═══════════════════════════════════════════════════════════════
# Prompt structure and non-contamination
# ═══════════════════════════════════════════════════════════════


class TestPromptV2Structure:
    def test_prompt_v2_loads_and_has_required_sections(self):
        from app.prompts.loader import load_prompt
        t = load_prompt("extraction", "v2")
        assert len(t.content) > 500
        assert "COMPLETENESS" in t.content
        assert "MULTILINGUAL" in t.content
        assert "FIDELITY" in t.content
        assert "DISTINGUISHING" in t.content
        assert "CANONICAL KEYS ONLY" in t.content
        assert "PARTIAL" in t.content

    def test_prompt_v2_no_benchmark_contamination(self):
        from app.prompts.loader import load_prompt
        t = load_prompt("extraction", "v2")
        assert "TRANS-A" not in t.content
        assert "SPELL-A" not in t.content
        assert "GOV-A" not in t.content
        assert "PHONEFMT" not in t.content
        assert "INC-" not in t.content

    def test_prompt_v1_v2_are_distinct(self):
        from app.prompts.loader import load_prompt
        v1 = load_prompt("extraction", "v1")
        v2 = load_prompt("extraction", "v2")
        assert v1.content != v2.content
        assert len(v2.content) > len(v1.content)


class TestPromptV3Precision:
    def test_prompt_v3_tightens_subject_attachment_and_certainty(self):
        from app.prompts.loader import load_prompt

        prompt = load_prompt("extraction", "v3").content
        assert "PERSON ATTACHMENT" in prompt
        assert "LAST KNOWN LOCATION" in prompt
        assert "DISTINGUISHING MARKS" in prompt
        assert "EMAIL AND GOVERNMENT ID" in prompt
        assert "Never use high, medium, low" in prompt

    def test_prompt_v3_has_no_benchmark_identifiers(self):
        from app.prompts.loader import load_prompt

        prompt = load_prompt("extraction", "v3").content
        for forbidden in ("TRANS-A", "SPELL-A", "GOV-A", "PHONEFMT", "INC-"):
            assert forbidden not in prompt


class TestCertaintyNormalization:
    @pytest.mark.parametrize(
        ("provider_value", "expected"),
        [("high", "exact"), ("medium", "estimated"), ("low", "inferred")],
    )
    def test_domain_valid_provider_aliases_normalize(self, provider_value, expected):
        from app.schemas.models import Certainty

        assert Certainty(provider_value).value == expected

    def test_unknown_certainty_still_fails_closed(self):
        from app.schemas.models import Certainty

        with pytest.raises(ValueError):
            Certainty("probably-ish")


# ═══════════════════════════════════════════════════════════════
# Extraction completeness and fidelity (mock extraction)
# ═══════════════════════════════════════════════════════════════


class TestMockExtractionCompleteness:
    def test_preserves_arabic_name(self):
        from app.services.identity_benchmark import mock_extract_fields
        text = "\u0627\u0644\u0627\u0633\u0645: \u064a\u0648\u0633\u0641 \u0627\u0644\u062d\u0633\u0646. "
        text += "\u0627\u0644\u0639\u0645\u0631: 14"
        fields = mock_extract_fields(text, "TEST-ARABIC", "Arabic")
        keys = {f.key for f in fields}
        assert "name" in keys, f"Arabic name not extracted; got keys={keys}"

    def test_preserves_all_independent_fields(self):
        from app.services.identity_benchmark import mock_extract_fields
        text = (
            "Name: Karim Mansour. Age: 34. Phone: 5551234567, "
            "Location: North Gate. Scar on right hand. "
            "Government ID: GOV-12345. DOB: 1990-07-22. "
            "Email: karim@example.com. Sister: Lina Mansour."
        )
        fields = mock_extract_fields(text, "TEST-MULTI", "English")
        keys = {f.key for f in fields}
        for expected in ("name", "age", "phone", "last_known_location",
                         "distinguishing_marks", "government_id",
                         "date_of_birth", "email"):
            assert expected in keys, f"Missing expected field: {expected}; got {keys}"

    def test_approximate_age_not_exact_dob(self):
        from app.services.identity_benchmark import mock_extract_fields
        text = "Name: Samir Nader. Approximately 34 years old."
        fields = mock_extract_fields(text, "TEST-APPROX", "English")
        keys = {f.key for f in fields}
        assert "age" in keys
        age_field = next((f for f in fields if f.key == "age"), None)
        if age_field:
            age_val = str(age_field.value).lower()
            assert "approximately" in age_val or "34" in age_val, \
                f"Approximate age should preserve qualifier; got: {age_field.value}"

    def test_partial_dob_preserved(self):
        from app.services.identity_benchmark import mock_extract_fields
        text = "Name: Nadia Saleh. DOB: 2012."
        fields = mock_extract_fields(text, "TEST-PARTIAL-DOB", "English")
        keys = {f.key for f in fields}
        assert "date_of_birth" in keys, f"Partial DOB not extracted; got keys={keys}"
        dob = next((f for f in fields if f.key == "date_of_birth"), None)
        if dob:
            assert "2012" in str(dob.value)

    def test_distinguishing_marks_extracted(self):
        from app.services.identity_benchmark import mock_extract_fields
        text = "Name: Amal Rafiq. Scar above left eyebrow. Birthmark on right forearm."
        fields = mock_extract_fields(text, "TEST-MARKS", "English")
        keys = {f.key for f in fields}
        assert "distinguishing_marks" in keys, \
            f"Distinguishing marks not extracted; got keys={keys}"

    @pytest.mark.parametrize("fmt_text", [
        "Phone: 5551234567",
        "Phone: +1-555-123-4567",
        "Phone: 555.123.4567",
        "Phone: 5551234567",
    ])
    def test_phone_formatting_preserved(self, fmt_text):
        from app.services.identity_benchmark import mock_extract_fields
        fields = mock_extract_fields(fmt_text, "TEST-PHONE", "English")
        keys = {f.key for f in fields}
        assert "phone" in keys, f"Phone not extracted from: {fmt_text}"

    def test_email_exact_preserved(self):
        from app.services.identity_benchmark import mock_extract_fields
        text = "Email: yhassan@example.com. Age: 14."
        fields = mock_extract_fields(text, "TEST-EMAIL", "English")
        email_field = next((f for f in fields if f.key == "email"), None)
        assert email_field is not None, "Email not extracted"
        assert "yhassan@example.com" in str(email_field.value).lower()

    def test_no_hallucinated_gov_id(self):
        from app.services.identity_benchmark import mock_extract_fields
        text = "Name: Lina Haddad. Age: 28. Location: Central Hospital."
        fields = mock_extract_fields(text, "TEST-NO-HALLUC", "English")
        keys = {f.key for f in fields}
        assert "government_id" not in keys, \
            "Hallucinated government_id from text without ID"

    def test_unicode_name_preservation(self):
        from app.services.identity_benchmark import mock_extract_fields
        text = "Name: Jos\u00e9 Garc\u00eda. Location: M\u00e9rida."
        fields = mock_extract_fields(text, "TEST-UNICODE", "English")
        name_field = next((f for f in fields if f.key == "name"), None)
        assert name_field is not None, "Name with Unicode not extracted"
        assert "Jos\u00e9" in str(name_field.value) or "Garc\u00eda" in str(name_field.value)


# ═══════════════════════════════════════════════════════════════
# Canonical field key normalization
# ═══════════════════════════════════════════════════════════════


class TestFieldKeyNormalization:
    def test_rejects_invented_keys(self):
        from app.services.field_key_normalizer import normalize_field_key
        for non_canonical in ["birth_year", "languages_spoken",
                              "arrival_time", "full_name_english"]:
            result = normalize_field_key(non_canonical)
            assert result.canonical_key is None or \
                "UNKNOWN" in str(getattr(result, 'normalization_rule', '')), \
                f"Non-canonical key '{non_canonical}' should not map; got {result.canonical_key}"

    def test_dob_alias_normalizes(self):
        from app.services.field_key_normalizer import normalize_field_key
        result = normalize_field_key("DOB")
        assert result.canonical_key is not None
        assert str(result.canonical_key.value) == "date_of_birth"

    def test_id_alias_normalizes(self):
        from app.services.field_key_normalizer import normalize_field_key
        result = normalize_field_key("id")
        assert result.canonical_key is not None
        assert str(result.canonical_key.value) == "government_id"

    def test_telephone_alias_normalizes(self):
        from app.services.field_key_normalizer import normalize_field_key
        result = normalize_field_key("telephone")
        assert result.canonical_key is not None
        assert str(result.canonical_key.value) == "phone"

    def test_mixed_case_aliases_normalize(self):
        from app.services.field_key_normalizer import normalize_field_key
        for alias in ["Dob", "DOB", "dob", "Id", "ID", "Telephone", "EMAIL"]:
            result = normalize_field_key(alias)
            assert result.canonical_key is not None, \
                f"Mixed-case alias '{alias}' should normalize"


# ═══════════════════════════════════════════════════════════════
# Live runner infrastructure
# ═══════════════════════════════════════════════════════════════


class TestLiveRunnerInfrastructure:
    def test_live_runner_includes_canonical_keys_block(self):
        runner_path = pathlib.Path("scripts/live_phase10t_runner.py")
        if not runner_path.exists():
            pytest.skip("live_phase10t_runner.py not found")
        source = runner_path.read_text()
        tree = ast.parse(source)
        found = any(
            isinstance(node, ast.Call) and
            hasattr(node.func, 'id') and
            node.func.id == 'format_canonical_keys_for_prompt'
            for node in ast.walk(tree)
        )
        assert found, "live_phase10t_runner.py must call format_canonical_keys_for_prompt()"

    def test_production_extraction_uses_promoted_prompt(self):
        from app.workflow.nodes.extraction import PRODUCTION_EXTRACTION_PROMPT_VERSION

        assert PRODUCTION_EXTRACTION_PROMPT_VERSION == "v2"
