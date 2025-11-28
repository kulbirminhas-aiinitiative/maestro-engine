"""
Unit Tests for Input Sanitization Module (MD-1876)

Tests the InputSanitizer class for:
- String sanitization
- Path traversal prevention
- XSS/HTML tag removal
- SQL injection pattern detection
- Max length enforcement
"""

import pytest
from src.utils.input_sanitizer import (
    InputSanitizer,
    sanitize_string,
    sanitize_path,
    sanitize_identifier,
    get_sanitizer,
)


class TestInputSanitizer:
    """Test cases for InputSanitizer class."""

    @pytest.fixture
    def sanitizer(self):
        """Create a sanitizer instance for testing."""
        return InputSanitizer(log_security_events=False)

    # ==================== TC-1.1: XSS/Script Tag Tests ====================

    def test_script_tags_stripped(self, sanitizer):
        """TC-1.1: Input with <script> tags should have tags stripped."""
        input_text = "Hello <script>alert('xss')</script> World"
        result = sanitizer.sanitize_string(input_text)
        assert "<script>" not in result
        assert "</script>" not in result
        assert "alert" not in result.lower() or "xss" not in result.lower()

    def test_script_self_closing_tag_stripped(self, sanitizer):
        """Script self-closing tags should be stripped."""
        input_text = "Test <script src='evil.js'/> content"
        result = sanitizer.sanitize_string(input_text)
        assert "<script" not in result

    def test_javascript_protocol_stripped(self, sanitizer):
        """JavaScript protocol URLs should be stripped."""
        input_text = "Click <a href='javascript:alert(1)'>here</a>"
        result = sanitizer.sanitize_string(input_text)
        assert "javascript:" not in result

    def test_event_handlers_stripped(self, sanitizer):
        """Event handlers (onclick, onerror) should be stripped."""
        input_text = "<img onerror='alert(1)' src='x'>"
        result = sanitizer.sanitize_string(input_text)
        assert "onerror" not in result

    def test_iframe_tags_stripped(self, sanitizer):
        """Iframe tags should be stripped."""
        input_text = "<iframe src='evil.com'></iframe>"
        result = sanitizer.sanitize_string(input_text)
        assert "<iframe" not in result

    def test_vbscript_protocol_stripped(self, sanitizer):
        """VBScript protocol should be stripped."""
        input_text = "vbscript:msgbox('test')"
        result = sanitizer.sanitize_string(input_text)
        assert "vbscript:" not in result

    # ==================== TC-1.2: Path Traversal Tests ====================

    def test_path_traversal_unix_rejected(self, sanitizer):
        """TC-1.2: Path with ../ traversal should be rejected."""
        path = "../../../etc/passwd"
        result = sanitizer.sanitize_path(path)
        assert result is None

    def test_path_traversal_windows_rejected(self, sanitizer):
        """Path with ..\\ traversal should be rejected."""
        path = "..\\..\\windows\\system32"
        result = sanitizer.sanitize_path(path)
        assert result is None

    def test_path_traversal_url_encoded_rejected(self, sanitizer):
        """URL-encoded path traversal should be rejected."""
        path = "%2e%2e%2f%2e%2e%2fetc/passwd"
        result = sanitizer.sanitize_path(path)
        assert result is None

    def test_valid_path_accepted(self, sanitizer):
        """Valid paths should be accepted."""
        path = "templates/workflow/default.yaml"
        result = sanitizer.sanitize_path(path)
        assert result == "templates/workflow/default.yaml"

    def test_path_with_allowed_prefix(self, sanitizer):
        """Paths matching allowed prefixes should be accepted."""
        path = "/opt/templates/test.yaml"
        result = sanitizer.sanitize_path(path, allowed_prefixes=["/opt/templates"])
        assert result == "/opt/templates/test.yaml"

    def test_path_outside_allowed_prefix_rejected(self, sanitizer):
        """Paths outside allowed prefixes should be rejected."""
        path = "/etc/passwd"
        result = sanitizer.sanitize_path(path, allowed_prefixes=["/opt/templates"])
        assert result is None

    def test_path_invalid_characters_rejected(self, sanitizer):
        """Paths with invalid characters should be rejected."""
        path = "templates/test;rm -rf /"
        result = sanitizer.sanitize_path(path)
        assert result is None

    # ==================== TC-1.3: Max Length Tests ====================

    def test_string_exceeding_max_length_truncated(self, sanitizer):
        """TC-1.3: String exceeding max length should be truncated."""
        long_string = "a" * 1000
        result = sanitizer.sanitize_string(long_string, max_length=100)
        assert len(result) == 100

    def test_string_within_max_length_preserved(self, sanitizer):
        """Strings within max length should be preserved."""
        short_string = "Hello World"
        result = sanitizer.sanitize_string(short_string, max_length=100)
        assert result == "Hello World"

    def test_default_max_length_by_field_type(self, sanitizer):
        """Field-specific max lengths should be applied."""
        long_name = "a" * 500
        result = sanitizer.sanitize_string(long_name, field_type="name")
        assert len(result) == 200  # Default for "name" is 200

    def test_requirement_field_max_length(self, sanitizer):
        """Requirement field should allow up to 10000 chars."""
        long_requirement = "a" * 15000
        result = sanitizer.sanitize_string(long_requirement, field_type="requirement")
        assert len(result) == 10000

    # ==================== TC-1.4: SQL Injection Tests ====================

    def test_sql_injection_drop_table_detected(self, sanitizer):
        """TC-1.4: SQL injection pattern should be detected."""
        input_text = "'; DROP TABLE users; --"
        threats = sanitizer.check_for_threats(input_text)
        assert any(t[0] == "SQL_INJECTION" for t in threats)

    def test_sql_injection_union_select_detected(self, sanitizer):
        """UNION SELECT injection should be detected."""
        input_text = "1 UNION SELECT * FROM passwords"
        threats = sanitizer.check_for_threats(input_text)
        assert any(t[0] == "SQL_INJECTION" for t in threats)

    def test_sql_injection_or_1_equals_1_detected(self, sanitizer):
        """OR 1=1 pattern should be detected."""
        input_text = "admin' OR 1=1 --"
        threats = sanitizer.check_for_threats(input_text)
        assert any(t[0] == "SQL_INJECTION" for t in threats)

    def test_safe_sql_keywords_allowed(self, sanitizer):
        """Normal text containing SQL keywords should be allowed."""
        input_text = "Please select the items from the dropdown"
        result = sanitizer.sanitize_string(input_text)
        assert "select" in result.lower()

    # ==================== Identifier Validation Tests ====================

    def test_valid_identifier_accepted(self, sanitizer):
        """Valid identifiers should be accepted."""
        identifier = "template-v2_test"
        result = sanitizer.sanitize_identifier(identifier)
        assert result == "template-v2_test"

    def test_identifier_with_special_chars_rejected(self, sanitizer):
        """Identifiers with special characters should be rejected."""
        identifier = "template;drop table"
        result = sanitizer.sanitize_identifier(identifier)
        assert result is None

    def test_identifier_exceeding_max_length_rejected(self, sanitizer):
        """Identifiers exceeding max length should be rejected."""
        identifier = "a" * 150
        result = sanitizer.sanitize_identifier(identifier, max_length=100)
        assert result is None

    def test_uuid_pattern_validation(self, sanitizer):
        """UUID-style identifiers should validate with custom pattern."""
        uuid_id = "550e8400-e29b-41d4-a716-446655440000"
        pattern = r'^[a-f0-9-]+$'
        result = sanitizer.sanitize_identifier(uuid_id, pattern=pattern)
        assert result == uuid_id

    # ==================== General Sanitization Tests ====================

    def test_whitespace_trimmed(self, sanitizer):
        """Leading/trailing whitespace should be trimmed."""
        input_text = "   Hello World   "
        result = sanitizer.sanitize_string(input_text)
        assert result == "Hello World"

    def test_control_characters_removed(self, sanitizer):
        """Control characters should be removed."""
        input_text = "Hello\x00World\x1f"
        result = sanitizer.sanitize_string(input_text)
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_newlines_preserved_by_default(self, sanitizer):
        """Newlines should be preserved by default."""
        input_text = "Line 1\nLine 2"
        result = sanitizer.sanitize_string(input_text)
        assert "\n" in result

    def test_newlines_removed_when_disabled(self, sanitizer):
        """Newlines should be removed when allow_newlines=False."""
        input_text = "Line 1\nLine 2"
        result = sanitizer.sanitize_string(input_text, allow_newlines=False)
        assert "\n" not in result

    def test_windows_newlines_normalized(self, sanitizer):
        """Windows-style newlines should be normalized to Unix style."""
        input_text = "Line 1\r\nLine 2"
        result = sanitizer.sanitize_string(input_text)
        assert "\r\n" not in result
        assert "\n" in result

    def test_none_input_returns_none(self, sanitizer):
        """None input should return None."""
        assert sanitizer.sanitize_string(None) is None
        assert sanitizer.sanitize_path(None) is None
        assert sanitizer.sanitize_identifier(None) is None

    def test_non_string_input_converted(self, sanitizer):
        """Non-string input should be converted to string."""
        result = sanitizer.sanitize_string(12345)
        assert result == "12345"


class TestConvenienceFunctions:
    """Test the module-level convenience functions."""

    def test_sanitize_string_function(self):
        """Module-level sanitize_string should work."""
        result = sanitize_string("  test  ")
        assert result == "test"

    def test_sanitize_path_function(self):
        """Module-level sanitize_path should work."""
        result = sanitize_path("valid/path")
        assert result == "valid/path"

    def test_sanitize_identifier_function(self):
        """Module-level sanitize_identifier should work."""
        result = sanitize_identifier("valid-id")
        assert result == "valid-id"

    def test_get_sanitizer_returns_singleton(self):
        """get_sanitizer should return a singleton instance."""
        s1 = get_sanitizer()
        s2 = get_sanitizer()
        assert s1 is s2


class TestThreatDetection:
    """Test threat detection capabilities."""

    @pytest.fixture
    def sanitizer(self):
        return InputSanitizer(log_security_events=False)

    def test_multiple_threats_detected(self, sanitizer):
        """Multiple threat types should all be detected."""
        input_text = "<script>alert(1)</script> OR 1=1 ../etc/passwd"
        threats = sanitizer.check_for_threats(input_text)
        threat_types = [t[0] for t in threats]
        assert "XSS_HTML" in threat_types
        assert "SQL_INJECTION" in threat_types
        assert "PATH_TRAVERSAL" in threat_types

    def test_no_threats_in_clean_input(self, sanitizer):
        """Clean input should not trigger any threat detection."""
        input_text = "This is a normal requirement for the workflow system."
        threats = sanitizer.check_for_threats(input_text)
        assert len(threats) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def sanitizer(self):
        return InputSanitizer(log_security_events=False)

    def test_empty_string(self, sanitizer):
        """Empty string should return empty string."""
        result = sanitizer.sanitize_string("")
        assert result == ""

    def test_single_character(self, sanitizer):
        """Single character should be handled correctly."""
        result = sanitizer.sanitize_string("a")
        assert result == "a"

    def test_only_whitespace(self, sanitizer):
        """String with only whitespace should return empty string."""
        result = sanitizer.sanitize_string("   \t\n  ")
        assert result == ""

    def test_unicode_preserved(self, sanitizer):
        """Unicode characters should be preserved."""
        input_text = "Hello 世界 مرحبا 🌍"
        result = sanitizer.sanitize_string(input_text)
        assert "世界" in result
        assert "مرحبا" in result
        assert "🌍" in result

    def test_html_entities_escaped(self, sanitizer):
        """HTML special characters should be escaped."""
        input_text = "2 < 3 && 3 > 2"
        result = sanitizer.sanitize_string(input_text)
        assert "&lt;" in result or "<" not in result

    def test_deeply_nested_scripts(self, sanitizer):
        """Nested script patterns should be handled."""
        input_text = "<scr<script>ipt>alert(1)</scr</script>ipt>"
        result = sanitizer.sanitize_string(input_text)
        assert "<script>" not in result
        assert "alert" not in result.lower() or "(" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
