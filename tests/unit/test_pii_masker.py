"""
Unit Tests for PII Masking Module (MD-1876)

Tests the PIIMasker class for:
- Email masking
- Token/API key masking
- Phone number masking
- Credit card masking
- SSN masking
- Nested data structure masking
"""

import pytest
from src.utils.pii_masker import (
    PIIMasker,
    mask_pii,
    mask_for_logging,
    get_pii_masker,
)


class TestEmailMasking:
    """Test email address masking."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_mask_email_basic(self, masker):
        """TC-4.1: Email addresses should be masked."""
        result = masker.mask_email("admin@example.com")
        assert "admin" not in result
        assert "@" in result
        assert ".com" in result
        assert "***" in result

    def test_mask_email_preserves_structure(self, masker):
        """Masked email should preserve basic structure."""
        result = masker.mask_email("user@domain.org")
        assert "@" in result
        assert ".org" in result
        # Should show first char of local and domain
        assert result.startswith("u")

    def test_mask_email_short_local(self, masker):
        """Short local part should still be masked."""
        result = masker.mask_email("a@example.com")
        assert result == "*@e***.com"

    def test_mask_email_invalid(self, masker):
        """Invalid email should be fully redacted."""
        result = masker.mask_email("notanemail")
        assert result == "[REDACTED]"

    def test_mask_email_none(self, masker):
        """None should be redacted."""
        result = masker.mask_email(None)
        assert result == "[REDACTED]"


class TestTokenMasking:
    """Test API token/key masking."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_mask_token_basic(self, masker):
        """TC-4.2: API tokens should be masked."""
        result = masker.mask_token("abc123xyz456def789")
        assert "abc1" in result  # First 4 chars
        assert "789" in result[-4:]  # Last 4 chars
        assert "***" in result

    def test_mask_token_short(self, masker):
        """Short tokens should be fully masked."""
        result = masker.mask_token("abc")
        assert "abc" not in result
        assert "***" in result

    def test_mask_token_none(self, masker):
        """None should be redacted."""
        result = masker.mask_token(None)
        assert result == "[REDACTED]"

    def test_mask_jwt_in_string(self, masker):
        """JWT tokens in strings should be detected and masked."""
        text = "Auth failed: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = masker.mask_string(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[JWT_TOKEN]" in result


class TestPhoneMasking:
    """Test phone number masking."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_mask_phone_dashed(self, masker):
        """Phone with dashes should be masked."""
        result = masker.mask_phone("123-456-7890")
        assert "123" not in result
        assert "456" not in result
        assert "7890" in result
        assert "***" in result

    def test_mask_phone_dotted(self, masker):
        """Phone with dots should be masked."""
        result = masker.mask_phone("123.456.7890")
        assert "7890" in result
        assert "123" not in result

    def test_mask_phone_plain(self, masker):
        """Plain phone number should be masked."""
        result = masker.mask_phone("1234567890")
        assert "7890" in result


class TestCreditCardMasking:
    """Test credit card masking."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_mask_credit_card(self, masker):
        """Credit card numbers should show only last 4 digits."""
        result = masker.mask_credit_card("4111-1111-1111-1111")
        assert "4111" not in result[:10]  # First part hidden
        assert "1111" in result[-4:]  # Last 4 visible
        assert "****" in result

    def test_mask_credit_card_no_dashes(self, masker):
        """Credit card without dashes should be masked."""
        result = masker.mask_credit_card("4111111111111111")
        assert "1111" in result[-4:]

    def test_mask_credit_card_spaces(self, masker):
        """Credit card with spaces should be masked."""
        result = masker.mask_credit_card("4111 1111 1111 1111")
        assert "1111" in result[-4:]


class TestSSNMasking:
    """Test SSN masking."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_mask_ssn(self, masker):
        """SSN should show only last 4 digits."""
        result = masker.mask_ssn("123-45-6789")
        assert "123" not in result
        assert "45" not in result
        assert "6789" in result
        assert "***-**-" in result


class TestDictMasking:
    """Test dictionary masking."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_mask_dict_password_field(self, masker):
        """Password fields should be completely redacted."""
        data = {"username": "admin", "password": "secret123"}
        result = masker.mask_dict(data)
        assert result["password"] == "[REDACTED]"
        assert "secret123" not in str(result)

    def test_mask_dict_email_field(self, masker):
        """Email fields should be masked."""
        data = {"user_email": "admin@example.com"}
        result = masker.mask_dict(data)
        assert "admin" not in result["user_email"]
        assert "@" in result["user_email"]

    def test_mask_dict_api_key_field(self, masker):
        """API key fields should be redacted."""
        data = {"api_key": "sk_live_abc123xyz456"}
        result = masker.mask_dict(data)
        assert result["api_key"] == "[REDACTED]"

    def test_mask_dict_nested(self, masker):
        """Nested dictionaries should be masked."""
        data = {
            "user": {
                "email": "user@test.com",
                "password": "secret",
                "profile": {
                    "phone": "123-456-7890"
                }
            }
        }
        result = masker.mask_dict(data)
        assert "user@test.com" not in str(result)
        assert "secret" not in str(result)
        assert result["user"]["password"] == "[REDACTED]"

    def test_mask_dict_preserves_non_pii(self, masker):
        """Non-PII fields should be preserved."""
        data = {"name": "John", "age": 30, "active": True}
        result = masker.mask_dict(data)
        assert result["name"] == "John"
        assert result["age"] == 30
        assert result["active"] is True


class TestListMasking:
    """Test list masking."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_mask_list_of_dicts(self, masker):
        """List of dicts should have PII masked."""
        data = [
            {"email": "user1@test.com"},
            {"email": "user2@test.com"},
        ]
        result = masker.mask_list(data)
        assert "user1@test.com" not in str(result)
        assert "user2@test.com" not in str(result)

    def test_mask_list_of_strings(self, masker):
        """List of strings should be scanned for PII."""
        data = [
            "Contact: admin@example.com",
            "Regular text",
        ]
        result = masker.mask_list(data)
        assert "admin@example.com" not in str(result)
        assert "Regular text" in str(result)


class TestStringMasking:
    """Test string content masking."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_mask_string_with_email(self, masker):
        """Strings containing emails should be masked."""
        text = "Please contact admin@example.com for support"
        result = masker.mask_string(text)
        assert "admin@example.com" not in result
        assert "Please contact" in result
        assert "for support" in result

    def test_mask_string_with_bearer_token(self, masker):
        """Bearer tokens should be masked."""
        text = "Authorization: Bearer abc123xyz456"
        result = masker.mask_string(text)
        assert "abc123xyz456" not in result
        assert "[TOKEN]" in result

    def test_mask_string_preserves_normal_text(self, masker):
        """Normal text should be preserved."""
        text = "This is a normal log message"
        result = masker.mask_string(text)
        assert result == text


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    def test_mask_pii_dict(self):
        """mask_pii should work with dicts."""
        data = {"password": "secret", "name": "John"}
        result = mask_pii(data)
        assert result["password"] == "[REDACTED]"
        assert result["name"] == "John"

    def test_mask_pii_list(self):
        """mask_pii should work with lists."""
        data = [{"email": "test@example.com"}]
        result = mask_pii(data)
        assert "test@example.com" not in str(result)

    def test_mask_pii_string(self):
        """mask_pii should work with strings."""
        text = "Email: user@test.com"
        result = mask_pii(text)
        assert "user@test.com" not in result

    def test_mask_for_logging(self):
        """mask_for_logging should return string."""
        data = {"password": "secret", "id": 123}
        result = mask_for_logging(data)
        assert isinstance(result, str)
        assert "secret" not in result

    def test_get_pii_masker_singleton(self):
        """get_pii_masker should return singleton."""
        m1 = get_pii_masker()
        m2 = get_pii_masker()
        assert m1 is m2


class TestEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def masker(self):
        return PIIMasker()

    def test_empty_dict(self, masker):
        """Empty dict should return empty dict."""
        result = masker.mask_dict({})
        assert result == {}

    def test_empty_list(self, masker):
        """Empty list should return empty list."""
        result = masker.mask_list([])
        assert result == []

    def test_empty_string(self, masker):
        """Empty string should return empty string."""
        result = masker.mask_string("")
        assert result == ""

    def test_none_values(self, masker):
        """None values should be preserved."""
        data = {"email": None, "name": "John"}
        result = masker.mask_dict(data)
        assert result["email"] is None
        assert result["name"] == "John"

    def test_deep_nesting(self, masker):
        """Deep nesting should be handled up to max depth."""
        data = {"l1": {"l2": {"l3": {"l4": {"l5": {"password": "secret"}}}}}}
        result = masker.mask_dict(data)
        # Should mask at reasonable depth
        assert "secret" not in str(result)

    def test_mixed_types(self, masker):
        """Mixed types should be handled."""
        data = {
            "int_val": 123,
            "float_val": 45.67,
            "bool_val": True,
            "none_val": None,
            "str_val": "test",
            "list_val": [1, 2, 3],
        }
        result = masker.mask_dict(data)
        assert result["int_val"] == 123
        assert result["float_val"] == 45.67
        assert result["bool_val"] is True
        assert result["none_val"] is None


class TestCustomConfiguration:
    """Test custom masker configuration."""

    def test_custom_redact_fields(self):
        """Custom redact fields should be added."""
        masker = PIIMasker(redact_fields={"custom_secret"})
        data = {"custom_secret": "value123"}
        result = masker.mask_dict(data)
        assert result["custom_secret"] == "[REDACTED]"

    def test_custom_mask_fields(self):
        """Custom mask fields should be added."""
        masker = PIIMasker(mask_fields={"user_code"})
        data = {"user_code": "abc123xyz456"}
        result = masker.mask_dict(data)
        assert "abc123xyz456" not in str(result)
        # Should be partially masked, not fully redacted
        assert result["user_code"] != "[REDACTED]"

    def test_disable_content_masking(self):
        """Content masking can be disabled."""
        masker = PIIMasker(mask_content=False)
        text = "Email: admin@example.com"
        result = masker.mask_string(text)
        # Should not scan content
        assert result == text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
