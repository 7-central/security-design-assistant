"""Component pattern matching utilities for validating security component IDs."""
import re
from typing import Any


class ComponentPatternMatcher:
    """Validates and parses security component ID patterns.

    Standard format: A-XXX-BB-B2 where:
    - A: Building/Area identifier (letter)
    - XXX: Numeric identifier (1-3 digits)
    - BB: Component type code (2 letters)
    - B2: Floor/Zone code (letter + digit)
    """

    # Standard pattern: A-XXX-BB-B2
    STANDARD_PATTERN = re.compile(r'^[A-Z]-\d{1,3}-[A-Z]{2}-[A-Z]\d$')

    # Flexible patterns for variations
    PATTERNS = {
        'standard': re.compile(r'^[A-Z]-\d{1,3}-[A-Z]{2}-[A-Z]\d$'),  # A-101-DR-B2
        'extended': re.compile(r'^[A-Z]{1,3}-\d{1,4}-[A-Z]{2,4}-[A-Z]\d{1,2}$'),  # ABC-1234-DOOR-B10
        'underscore': re.compile(r'^[A-Z]_\d{1,3}_[A-Z]{2}_[A-Z]\d$'),  # A_101_DR_B2
        'no_separator': re.compile(r'^[A-Z]\d{1,3}[A-Z]{2}[A-Z]\d$'),  # A101DRB2
        'dot_separator': re.compile(r'^[A-Z]\.\d{1,3}\.[A-Z]{2}\.[A-Z]\d$'),  # A.101.DR.B2
    }

    # Component type codes
    COMPONENT_TYPES = {
        'DR': 'door',
        'RD': 'reader',
        'EB': 'exit_button',
        'EX': 'exit_button',
        'LK': 'lock',
        'LC': 'lock',
        'CM': 'camera',
        'CAM': 'camera',
        'MTN': 'motion',
        'REX': 'request_exit',
        'KEY': 'keypad',
        'BIO': 'biometric'
    }

    @classmethod
    def is_valid_pattern(cls, component_id: str, pattern_type: str = 'standard') -> bool:
        """Check if component ID matches specified pattern.

        Args:
            component_id: Component ID to validate
            pattern_type: Type of pattern to check ('standard', 'extended', etc.)

        Returns:
            True if ID matches pattern, False otherwise
        """
        if not component_id:
            return False

        # Convert to uppercase for case-insensitive matching
        component_id = component_id.upper().strip()

        if pattern_type == 'any':
            # Check if matches any known pattern
            return any(pattern.match(component_id) for pattern in cls.PATTERNS.values())

        pattern = cls.PATTERNS.get(pattern_type)
        if not pattern:
            return False

        return bool(pattern.match(component_id))

    @classmethod
    def parse_component_id(cls, component_id: str) -> dict[str, Any] | None:
        """Parse component ID into its parts.

        Args:
            component_id: Component ID to parse

        Returns:
            Dictionary with parsed parts or None if invalid
        """
        if not component_id:
            return None

        component_id = component_id.upper().strip()

        # Try standard pattern first
        match = cls.STANDARD_PATTERN.match(component_id)
        if match:
            parts = component_id.split('-')
            return {
                'building': parts[0],
                'number': int(parts[1]),
                'type_code': parts[2],
                'zone': parts[3],
                'component_type': cls.COMPONENT_TYPES.get(parts[2], 'unknown'),
                'pattern_type': 'standard',
                'original': component_id
            }

        # Try extended pattern
        if cls.PATTERNS['extended'].match(component_id):
            parts = component_id.split('-')
            if len(parts) == 4:
                return {
                    'building': parts[0],
                    'number': int(parts[1]),
                    'type_code': parts[2],
                    'zone': parts[3],
                    'component_type': cls.COMPONENT_TYPES.get(parts[2][:2], 'unknown'),
                    'pattern_type': 'extended',
                    'original': component_id
                }

        # Try underscore pattern
        if cls.PATTERNS['underscore'].match(component_id):
            parts = component_id.split('_')
            return {
                'building': parts[0],
                'number': int(parts[1]),
                'type_code': parts[2],
                'zone': parts[3],
                'component_type': cls.COMPONENT_TYPES.get(parts[2], 'unknown'),
                'pattern_type': 'underscore',
                'original': component_id
            }

        # Try dot separator pattern
        if cls.PATTERNS['dot_separator'].match(component_id):
            parts = component_id.split('.')
            return {
                'building': parts[0],
                'number': int(parts[1]),
                'type_code': parts[2],
                'zone': parts[3],
                'component_type': cls.COMPONENT_TYPES.get(parts[2], 'unknown'),
                'pattern_type': 'dot_separator',
                'original': component_id
            }

        # Try no separator pattern
        if cls.PATTERNS['no_separator'].match(component_id):
            # Extract parts using regex groups
            pattern = re.compile(r'^([A-Z])(\d{1,3})([A-Z]{2})([A-Z]\d)$')
            match = pattern.match(component_id)
            if match:
                return {
                    'building': match.group(1),
                    'number': int(match.group(2)),
                    'type_code': match.group(3),
                    'zone': match.group(4),
                    'component_type': cls.COMPONENT_TYPES.get(match.group(3), 'unknown'),
                    'pattern_type': 'no_separator',
                    'original': component_id
                }

        return None

    @classmethod
    def normalize_component_id(cls, component_id: str) -> str | None:
        """Normalize component ID to standard format.

        Args:
            component_id: Component ID to normalize

        Returns:
            Normalized ID in standard format or None if invalid
        """
        parsed = cls.parse_component_id(component_id)
        if not parsed:
            return None

        # Convert to standard format: A-XXX-BB-B2
        return f"{parsed['building']}-{parsed['number']:03d}-{parsed['type_code']}-{parsed['zone']}"

    @classmethod
    def validate_batch(cls, component_ids: list[str]) -> dict[str, bool]:
        """Validate multiple component IDs.

        Args:
            component_ids: List of component IDs to validate

        Returns:
            Dictionary mapping each ID to its validation result
        """
        results = {}
        for component_id in component_ids:
            results[component_id] = cls.is_valid_pattern(component_id, 'any')
        return results

    @classmethod
    def extract_component_type(cls, component_id: str) -> str | None:
        """Extract component type from ID.

        Args:
            component_id: Component ID

        Returns:
            Component type or None if invalid
        """
        parsed = cls.parse_component_id(component_id)
        return parsed['component_type'] if parsed else None
