"""
PII Masking Module for MD-1876: API Validation Layer Phase 2 - Hardening

This module provides PII (Personally Identifiable Information) masking
for audit logs and sensitive data handling.

Features:
- Email address masking (user@domain.com -> u***@d***.com)
- API token/key masking (abc123xyz -> abc***xyz)
- Password field masking (completely redacted)
- Phone number masking
- Credit card masking
- SSN/Tax ID masking

Usage:
    from src.utils.pii_masker import PIIMasker, mask_pii

    masker = PIIMasker()
    safe_data = masker.mask_dict({"email": "user@example.com"})
"""

import re
import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class PIIMasker:
    """
    PII Masker for audit logging and sensitive data handling.

    Provides configurable masking of personally identifiable information
    while preserving enough context for debugging.
    """

    # Fields that should be completely redacted
    REDACT_FIELDS = {
        "password", "passwd", "pwd", "secret", "api_key", "apikey",
        "access_token", "refresh_token", "auth_token", "bearer",
        "private_key", "ssh_key", "client_secret", "credentials",
        "authorization", "x-api-key", "x-auth-token",
    }

    # Fields that should be partially masked
    MASK_FIELDS = {
        "email", "phone", "mobile", "telephone", "ssn", "tax_id",
        "credit_card", "card_number", "account_number", "routing_number",
        "user", "username", "user_id", "userid", "user_name",
    }

    # Patterns for content-based detection
    PATTERNS = {
        "email": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        "phone": re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'),
        "ssn": re.compile(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'),
        "credit_card": re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
        "api_token": re.compile(r'\b[A-Za-z0-9]{32,}\b'),  # Long alphanumeric strings
        "jwt": re.compile(r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'),  # JWT tokens
        "bearer": re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.IGNORECASE),
        "ip_address": re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),
    }

    def __init__(
        self,
        redact_fields: Optional[set] = None,
        mask_fields: Optional[set] = None,
        mask_content: bool = True,
        preserve_length: bool = False,
    ):
        """
        Initialize PII masker.

        Args:
            redact_fields: Additional field names to completely redact
            mask_fields: Additional field names to partially mask
            mask_content: Whether to scan and mask content (not just field names)
            preserve_length: Whether to preserve original length in masking
        """
        self.redact_fields = self.REDACT_FIELDS.copy()
        if redact_fields:
            self.redact_fields.update(redact_fields)

        self.mask_fields = self.MASK_FIELDS.copy()
        if mask_fields:
            self.mask_fields.update(mask_fields)

        self.mask_content = mask_content
        self.preserve_length = preserve_length

    def mask_email(self, email: str) -> str:
        """
        Mask an email address while preserving domain hint.

        Example: user@example.com -> u***@e***.com
        """
        if not email or '@' not in email:
            return '[REDACTED]'

        parts = email.split('@')
        if len(parts) != 2:
            return '[REDACTED]'

        local, domain = parts

        # Mask local part
        if len(local) <= 1:
            masked_local = '*'
        else:
            masked_local = local[0] + '***'

        # Mask domain
        domain_parts = domain.rsplit('.', 1)
        if len(domain_parts) == 2:
            domain_name, tld = domain_parts
            if len(domain_name) <= 1:
                masked_domain = '*'
            else:
                masked_domain = domain_name[0] + '***'
            return f"{masked_local}@{masked_domain}.{tld}"
        else:
            return f"{masked_local}@***.***"

    def mask_token(self, token: str, show_chars: int = 4) -> str:
        """
        Mask a token/key showing only first and last few characters.

        Example: abc123xyz456 -> abc1***6456
        """
        if not token:
            return '[REDACTED]'

        token = str(token)
        if len(token) <= show_chars * 2:
            return '*' * len(token) if self.preserve_length else '***'

        return f"{token[:show_chars]}***{token[-show_chars:]}"

    def mask_phone(self, phone: str) -> str:
        """
        Mask a phone number showing only last 4 digits.

        Example: 123-456-7890 -> ***-***-7890
        """
        if not phone:
            return '[REDACTED]'

        # Extract digits
        digits = re.sub(r'\D', '', str(phone))
        if len(digits) < 4:
            return '***'

        return f"***-***-{digits[-4:]}"

    def mask_ssn(self, ssn: str) -> str:
        """
        Mask SSN showing only last 4 digits.

        Example: 123-45-6789 -> ***-**-6789
        """
        if not ssn:
            return '[REDACTED]'

        digits = re.sub(r'\D', '', str(ssn))
        if len(digits) < 4:
            return '***-**-****'

        return f"***-**-{digits[-4:]}"

    def mask_credit_card(self, card: str) -> str:
        """
        Mask credit card showing only last 4 digits.

        Example: 4111-1111-1111-1111 -> ****-****-****-1111
        """
        if not card:
            return '[REDACTED]'

        digits = re.sub(r'\D', '', str(card))
        if len(digits) < 4:
            return '****-****-****-****'

        return f"****-****-****-{digits[-4:]}"

    def mask_ip(self, ip: str) -> str:
        """
        Mask IP address showing only first octet.

        Example: 192.168.1.100 -> 192.***.***.**
        """
        if not ip:
            return '[REDACTED]'

        parts = str(ip).split('.')
        if len(parts) == 4:
            return f"{parts[0]}.***.***.**"
        return '***.***.***.**'

    def mask_value(self, key: str, value: Any) -> Any:
        """
        Mask a single value based on its key name.

        Args:
            key: Field name/key
            value: Value to mask

        Returns:
            Masked value
        """
        if value is None:
            return None

        key_lower = key.lower().replace('-', '_')

        # Check if field should be completely redacted
        for redact_field in self.redact_fields:
            if redact_field in key_lower:
                return '[REDACTED]'

        # Check if field should be partially masked
        str_value = str(value)

        if 'email' in key_lower:
            return self.mask_email(str_value)
        elif 'phone' in key_lower or 'mobile' in key_lower or 'telephone' in key_lower:
            return self.mask_phone(str_value)
        elif 'ssn' in key_lower or 'tax_id' in key_lower:
            return self.mask_ssn(str_value)
        elif 'card' in key_lower or 'credit' in key_lower:
            return self.mask_credit_card(str_value)
        elif 'token' in key_lower or 'key' in key_lower:
            return self.mask_token(str_value)
        elif 'ip' in key_lower and key_lower not in ('tip', 'skip', 'strip'):
            return self.mask_ip(str_value)

        # Check mask_fields for partial masking
        for mask_field in self.mask_fields:
            if mask_field in key_lower:
                return self.mask_token(str_value)

        return value

    def mask_string(self, text: str) -> str:
        """
        Scan and mask PII patterns in a string.

        Args:
            text: Text to scan and mask

        Returns:
            Text with PII masked
        """
        if not text or not self.mask_content:
            return text

        result = text

        # Mask JWT tokens first (they're long and specific)
        result = self.PATTERNS['jwt'].sub('[JWT_TOKEN]', result)

        # Mask Bearer tokens
        result = self.PATTERNS['bearer'].sub('Bearer [TOKEN]', result)

        # Mask emails
        for match in self.PATTERNS['email'].finditer(result):
            masked = self.mask_email(match.group())
            result = result.replace(match.group(), masked)

        # Mask credit cards
        for match in self.PATTERNS['credit_card'].finditer(result):
            masked = self.mask_credit_card(match.group())
            result = result.replace(match.group(), masked)

        # Mask SSNs
        for match in self.PATTERNS['ssn'].finditer(result):
            # Only mask if it looks like an SSN (not just any number)
            ssn = match.group()
            if len(re.sub(r'\D', '', ssn)) == 9:
                masked = self.mask_ssn(ssn)
                result = result.replace(ssn, masked)

        # Mask phone numbers
        for match in self.PATTERNS['phone'].finditer(result):
            masked = self.mask_phone(match.group())
            result = result.replace(match.group(), masked)

        return result

    def mask_dict(self, data: Dict[str, Any], depth: int = 0, max_depth: int = 10) -> Dict[str, Any]:
        """
        Recursively mask PII in a dictionary.

        Args:
            data: Dictionary to mask
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            Dictionary with PII masked
        """
        if depth >= max_depth:
            return data

        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self.mask_dict(value, depth + 1, max_depth)
            elif isinstance(value, list):
                result[key] = self.mask_list(value, depth + 1, max_depth)
            elif isinstance(value, str):
                # First mask by field name, then scan content
                masked = self.mask_value(key, value)
                if isinstance(masked, str) and masked != '[REDACTED]':
                    masked = self.mask_string(masked)
                result[key] = masked
            else:
                result[key] = self.mask_value(key, value)

        return result

    def mask_list(self, data: List[Any], depth: int = 0, max_depth: int = 10) -> List[Any]:
        """
        Recursively mask PII in a list.

        Args:
            data: List to mask
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            List with PII masked
        """
        if depth >= max_depth:
            return data

        result = []
        for item in data:
            if isinstance(item, dict):
                result.append(self.mask_dict(item, depth + 1, max_depth))
            elif isinstance(item, list):
                result.append(self.mask_list(item, depth + 1, max_depth))
            elif isinstance(item, str):
                result.append(self.mask_string(item))
            else:
                result.append(item)

        return result


# Default masker instance
_default_masker: Optional[PIIMasker] = None


def get_pii_masker() -> PIIMasker:
    """Get the default PII masker instance."""
    global _default_masker
    if _default_masker is None:
        _default_masker = PIIMasker()
    return _default_masker


def mask_pii(data: Union[Dict, List, str]) -> Union[Dict, List, str]:
    """
    Convenience function to mask PII in data.

    Args:
        data: Data to mask (dict, list, or string)

    Returns:
        Data with PII masked
    """
    masker = get_pii_masker()

    if isinstance(data, dict):
        return masker.mask_dict(data)
    elif isinstance(data, list):
        return masker.mask_list(data)
    elif isinstance(data, str):
        return masker.mask_string(data)
    else:
        return data


def mask_for_logging(data: Any) -> str:
    """
    Mask PII and convert to string for logging.

    Args:
        data: Data to mask and stringify

    Returns:
        Safe string representation for logging
    """
    if data is None:
        return 'None'

    if isinstance(data, str):
        return mask_pii(data)

    if isinstance(data, (dict, list)):
        import json
        try:
            masked = mask_pii(data)
            return json.dumps(masked, default=str)
        except Exception:
            return str(mask_pii(data))

    return str(data)
