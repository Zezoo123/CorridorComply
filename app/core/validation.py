"""
KYC field validation utilities
"""
from datetime import datetime, date
from typing import List, Tuple, Optional, Dict, Any
import re
from ..data.countries import is_valid_country_code, get_country_info


# Valid document types
VALID_DOCUMENT_TYPES = {
    "passport",
    "id_card",
    "driving_license",
    "national_id",
    "residence_permit"
}


class ValidationError(Exception):
    """Custom validation error"""
    pass


class FieldValidator:
    """KYC field validation"""
    
    @staticmethod
    def validate_date(date_str: str, field_name: str = "date") -> Tuple[bool, Optional[str], Optional[date]]:
        """
        Validate date string format and value
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            field_name: Name of the field being validated
            
        Returns:
            Tuple of (is_valid, error_message, parsed_date)
        """
        if not date_str or not isinstance(date_str, str):
            return False, f"{field_name} is required", None
        
        date_str = date_str.strip()
        
        # Check format YYYY-MM-DD
        date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        if not date_pattern.match(date_str):
            return False, f"{field_name} must be in YYYY-MM-DD format", None
        
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            
            # Check if date is reasonable (not too far in past/future)
            today = date.today()
            min_date = date(1900, 1, 1)
            max_date = today
            
            if parsed_date < min_date:
                return False, f"{field_name} is too far in the past (before 1900)", None
            
            if parsed_date > max_date:
                return False, f"{field_name} is in the future", None
            
            return True, None, parsed_date
            
        except ValueError as e:
            return False, f"{field_name} is invalid: {str(e)}", None
    
    @staticmethod
    def validate_document_type(doc_type: str) -> Tuple[bool, Optional[str]]:
        """
        Validate document type
        
        Args:
            doc_type: Document type string
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not doc_type or not isinstance(doc_type, str):
            return False, "Document type is required"
        
        doc_type_lower = doc_type.lower().strip()
        
        if doc_type_lower not in VALID_DOCUMENT_TYPES:
            valid_types = ", ".join(sorted(VALID_DOCUMENT_TYPES))
            return False, f"Invalid document type. Must be one of: {valid_types}"
        
        return True, None
    
    @staticmethod
    def validate_nationality(nationality: str) -> Tuple[bool, Optional[str]]:
        """
        Validate nationality (ISO country code)
        
        Args:
            nationality: Nationality/country code
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not nationality or not isinstance(nationality, str):
            return False, "Nationality is required"
        
        nationality_upper = nationality.strip().upper()
        
        # Check format (2 uppercase letters)
        if not re.match(r'^[A-Z]{2}$', nationality_upper):
            return False, "Nationality must be a 2-letter ISO country code (e.g., QA, PH, US)"
        
        # Check if it's a valid country code (alpha-2 or alpha-3)
        if not is_valid_country_code(nationality_upper):
            return False, "Nationality must be a valid 2 or 3-letter ISO country code (e.g., US, GBR, QA, ARE)"
            
        # Get country info (we don't need it here, but this validates the code exists)
        country_info = get_country_info(nationality_upper)
        if not country_info:
            return False, "Invalid country code"
        
        return True, None
    
    @staticmethod
    def validate_document_number(doc_number: str, doc_type: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Validate document number format
        
        Args:
            doc_number: Document number string
            doc_type: Optional document type for type-specific validation
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not doc_number or not isinstance(doc_number, str):
            return False, "Document number is required"
        
        doc_number = doc_number.strip()
        
        # Basic length check
        if len(doc_number) < 3:
            return False, "Document number is too short (minimum 3 characters)"
        
        if len(doc_number) > 50:
            return False, "Document number is too long (maximum 50 characters)"
        
        # Check for valid characters (alphanumeric and common separators)
        if not re.match(r'^[A-Z0-9\s\-_]+$', doc_number.upper()):
            return False, "Document number contains invalid characters"
        
        # Type-specific validation (can be extended)
        if doc_type:
            doc_type_lower = doc_type.lower()
            if doc_type_lower == "passport":
                # Passports often start with a letter
                if not re.match(r'^[A-Z]', doc_number.upper()):
                    # Not required, but common pattern
                    pass
        
        return True, None
    
    @staticmethod
    def validate_full_name(name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate full name
        
        Args:
            name: Full name string
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name or not isinstance(name, str):
            return False, "Full name is required"
        
        name = name.strip()
        
        if len(name) < 2:
            return False, "Full name is too short (minimum 2 characters)"
        
        if len(name) > 100:
            return False, "Full name is too long (maximum 100 characters)"
        
        # Check for valid characters (letters, spaces, hyphens, apostrophes)
        if not re.match(r'^[A-Za-z\s\-\'\.]+$', name):
            return False, "Full name contains invalid characters"
        
        # Check for at least one space (first and last name)
        if ' ' not in name:
            return False, "Full name should include first and last name"
        
        return True, None
    
    @staticmethod
    def validate_kyc_fields(
        full_name: Optional[str] = None,
        dob: Optional[str] = None,
        nationality: Optional[str] = None,
        document_type: Optional[str] = None,
        document_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate all KYC fields and return validation results
        
        Args:
            full_name: Full name
            dob: Date of birth
            nationality: Nationality code
            document_type: Document type
            document_number: Document number
            
        Returns:
            Dictionary with validation results:
            - is_valid: bool
            - missing_fields: List[str]
            - validation_errors: List[str]
            - data_quality_issues: List[str]
        """
        missing_fields = []
        validation_errors = []
        data_quality_issues = []
        
        # Check required fields
        if not full_name:
            missing_fields.append("full_name")
        else:
            is_valid, error = FieldValidator.validate_full_name(full_name)
            if not is_valid:
                validation_errors.append(f"full_name: {error}")
        
        if not dob:
            missing_fields.append("dob")
        else:
            is_valid, error, parsed_date = FieldValidator.validate_date(dob, "Date of birth")
            if not is_valid:
                validation_errors.append(f"dob: {error}")
            elif parsed_date:
                # Check if DOB is reasonable (person should be at least 16 years old)
                today = date.today()
                age = (today - parsed_date).days // 365
                if age < 16:
                    data_quality_issues.append(f"Date of birth indicates age {age} (minimum 16 expected)")
                if age > 120:
                    data_quality_issues.append(f"Date of birth indicates age {age} (unusually old)")
        
        if not nationality:
            missing_fields.append("nationality")
        else:
            is_valid, error = FieldValidator.validate_nationality(nationality)
            if not is_valid:
                validation_errors.append(f"nationality: {error}")
        
        if not document_type:
            missing_fields.append("document_type")
        else:
            is_valid, error = FieldValidator.validate_document_type(document_type)
            if not is_valid:
                validation_errors.append(f"document_type: {error}")
        
        if not document_number:
            missing_fields.append("document_number")
        else:
            is_valid, error = FieldValidator.validate_document_number(document_number, document_type)
            if not is_valid:
                validation_errors.append(f"document_number: {error}")
        
        is_valid = len(missing_fields) == 0 and len(validation_errors) == 0
        
        return {
            "is_valid": is_valid,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "data_quality_issues": data_quality_issues
        }

