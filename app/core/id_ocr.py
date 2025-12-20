"""
ID Card OCR processing for different countries.

This module handles OCR extraction for ID cards, national IDs, and other
non-passport documents that don't have MRZ (Machine Readable Zone).
"""
import easyocr
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, Optional, List
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Initialize EasyOCR reader (lazy initialization)
_ocr_reader = None

def get_ocr_reader():
    """Get or initialize EasyOCR reader."""
    global _ocr_reader
    if _ocr_reader is None:
        try:
            _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {str(e)}")
            raise
    return _ocr_reader

def extract_text_from_image(image: Image.Image, region: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """
    Extract text from an image using OCR.
    
    Args:
        image: PIL Image
        region: Optional (x, y, width, height) tuple to extract specific region
        
    Returns:
        List of dicts with 'text', 'confidence', and 'bbox' keys
    """
    try:
        reader = get_ocr_reader()
        
        # Convert PIL to numpy array
        img_array = np.array(image)
        
        # Extract region if specified
        if region:
            x, y, w, h = region
            img_array = img_array[y:y+h, x:x+w]
        
        # Run OCR
        results = reader.readtext(img_array, detail=1)
        
        # Format results
        formatted_results = []
        for (bbox, text, confidence) in results:
            formatted_results.append({
                'text': text.strip(),
                'confidence': float(confidence),
                'bbox': bbox
            })
        
        return formatted_results
    except Exception as e:
        logger.error(f"OCR extraction failed: {str(e)}")
        return []

def extract_id_fields(ocr_results: List[Dict[str, Any]], country_code: str, document_type: str) -> Dict[str, Any]:
    """
    Extract structured fields from OCR results based on country and document type.
    
    Args:
        ocr_results: List of OCR results with text and confidence
        country_code: ISO 2-letter country code (e.g., 'US', 'QA', 'PH')
        document_type: Document type (e.g., 'id_card', 'national_id')
        
    Returns:
        Dict with extracted fields (name, document_number, dob, etc.)
    """
    extracted = {
        'name': None,
        'document_number': None,
        'date_of_birth': None,
        'expiry_date': None,
        'nationality': None,
        'address': None,
        'raw_text': ' '.join([r['text'] for r in ocr_results]),
        'confidence_scores': {}
    }
    
    # Combine all text for pattern matching
    all_text = ' '.join([r['text'] for r in ocr_results]).upper()
    
    # Try to load country-specific rules
    rules = load_country_rules(country_code, document_type)
    
    if rules:
        # Use country-specific extraction patterns
        extracted = extract_with_rules(ocr_results, rules, country_code)
    else:
        # Use generic extraction patterns
        extracted = extract_generic_fields(ocr_results, all_text)
    
    return extracted

def load_country_rules(country_code: str, document_type: str) -> Optional[Dict[str, Any]]:
    """
    Load country-specific OCR rules if available.
    
    Args:
        country_code: ISO 2-letter country code
        document_type: Document type
        
    Returns:
        Dict with extraction rules or None
    """
    try:
        rules_dir = Path(__file__).parent.parent.parent / "premium" / "corridor_rules"
        rules_file = rules_dir / f"{country_code.lower()}_{document_type.lower()}_rules.json"
        
        if not rules_file.exists():
            # Try alternative naming
            rules_file = rules_dir / f"{country_code.lower()}_rules.json"
        
        if rules_file.exists():
            import json
            with open(rules_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.debug(f"Could not load rules for {country_code}/{document_type}: {str(e)}")
    
    return None

def extract_with_rules(ocr_results: List[Dict[str, Any]], rules: Dict[str, Any], country_code: str) -> Dict[str, Any]:
    """
    Extract fields using country-specific rules.
    
    Args:
        ocr_results: OCR results
        rules: Country-specific rules dict
        country_code: Country code
        
    Returns:
        Dict with extracted fields
    """
    extracted = {
        'name': None,
        'document_number': None,
        'date_of_birth': None,
        'expiry_date': None,
        'nationality': country_code,
        'address': None,
        'raw_text': ' '.join([r['text'] for r in ocr_results]),
        'confidence_scores': {}
    }
    
    # Extract patterns from rules
    patterns = rules.get('extraction_patterns', {})
    all_text = extracted['raw_text']
    
    # Extract document number
    if 'document_number' in patterns:
        doc_num_pattern = patterns['document_number']
        match = re.search(doc_num_pattern, all_text)
        if match:
            extracted['document_number'] = match.group(1).strip()
    
    # Extract name
    if 'name' in patterns:
        name_pattern = patterns['name']
        match = re.search(name_pattern, all_text)
        if match:
            extracted['name'] = match.group(1).strip()
    
    # Extract date of birth
    if 'date_of_birth' in patterns:
        dob_pattern = patterns['date_of_birth']
        match = re.search(dob_pattern, all_text)
        if match:
            extracted['date_of_birth'] = match.group(1).strip()
    
    # Extract expiry date
    if 'expiry_date' in patterns:
        expiry_pattern = patterns['expiry_date']
        match = re.search(expiry_pattern, all_text)
        if match:
            extracted['expiry_date'] = match.group(1).strip()
    
    return extracted

def extract_generic_fields(ocr_results: List[Dict[str, Any]], all_text: str) -> Dict[str, Any]:
    """
    Extract fields using generic patterns (fallback when no country-specific rules).
    
    Args:
        ocr_results: OCR results
        all_text: Combined text from all OCR results
        
    Returns:
        Dict with extracted fields
    """
    extracted = {
        'name': None,
        'document_number': None,
        'date_of_birth': None,
        'expiry_date': None,
        'nationality': None,
        'address': None,
        'raw_text': all_text,
        'confidence_scores': {}
    }
    
    # Generic patterns for common fields
    
    # Document number patterns (alphanumeric, 6-20 chars)
    doc_num_patterns = [
        r'\b([A-Z0-9]{6,20})\b',  # Alphanumeric ID
        r'ID[:\s]+([A-Z0-9]{6,20})',  # "ID: ABC123456"
        r'DOC[:\s]+([A-Z0-9]{6,20})',  # "DOC: ABC123456"
    ]
    for pattern in doc_num_patterns:
        match = re.search(pattern, all_text)
        if match:
            extracted['document_number'] = match.group(1).strip()
            break
    
    # Date patterns (various formats)
    date_patterns = [
        r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b',  # DD/MM/YYYY or DD-MM-YYYY
        r'\b(\d{4}[/-]\d{1,2}[/-]\d{1,2})\b',  # YYYY/MM/DD or YYYY-MM-DD
        r'DOB[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # "DOB: 01/01/1990"
        r'BIRTH[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # "BIRTH: 01/01/1990"
    ]
    for pattern in date_patterns:
        match = re.search(pattern, all_text)
        if match:
            extracted['date_of_birth'] = match.group(1).strip()
            break
    
    # Name extraction (look for common name patterns)
    # This is more complex and may need country-specific rules
    name_patterns = [
        r'NAME[:\s]+([A-Z\s]{3,50})',  # "NAME: JOHN DOE"
        r'FULL[:\s]+NAME[:\s]+([A-Z\s]{3,50})',  # "FULL NAME: JOHN DOE"
    ]
    for pattern in name_patterns:
        match = re.search(pattern, all_text)
        if match:
            extracted['name'] = match.group(1).strip()
            break
    
    return extracted

def validate_id_ocr(document_image: Image.Image, country_code: str, document_type: str) -> Dict[str, Any]:
    """
    Validate ID card using OCR to extract document data.
    
    This is the main entry point for ID card validation (non-MRZ documents).
    
    Args:
        document_image: PIL Image of the document
        country_code: ISO 2-letter country code
        document_type: Document type (e.g., 'id_card', 'national_id')
        
    Returns:
        Dict containing:
            - valid: bool - whether document validation passed
            - extracted_data: dict - extracted document data
            - error: Optional[str] - error message if any
            - details: list - validation details
    """
    try:
        logger.info(f"Starting ID OCR validation for {country_code} {document_type}")
        
        # Extract text from entire image
        ocr_results = extract_text_from_image(document_image)
        
        if not ocr_results:
            return {
                "valid": False,
                "extracted_data": None,
                "error": "Could not extract text from document",
                "details": ["OCR extraction returned no results"]
            }
        
        # Extract structured fields
        extracted_fields = extract_id_fields(ocr_results, country_code, document_type)
        
        # Validate extracted data
        validation_details = []
        is_valid = True
        
        if not extracted_fields.get('document_number'):
            validation_details.append("Document number not found")
            is_valid = False
        
        if not extracted_fields.get('name'):
            validation_details.append("Name not found")
            # Not critical, just a warning
        
        if not extracted_fields.get('date_of_birth'):
            validation_details.append("Date of birth not found")
            # Not critical, just a warning
        
        if is_valid:
            validation_details.append("ID OCR extraction successful")
            validation_details.append(f"Extracted document number: {extracted_fields.get('document_number')}")
        
        return {
            "valid": is_valid,
            "extracted_data": extracted_fields,
            "error": None if is_valid else "Some required fields could not be extracted",
            "details": validation_details,
            "ocr_confidence": sum([r['confidence'] for r in ocr_results]) / len(ocr_results) if ocr_results else 0.0
        }
        
    except Exception as e:
        logger.error(f"ID OCR validation failed: {str(e)}", exc_info=True)
        return {
            "valid": False,
            "extracted_data": None,
            "error": f"ID OCR validation failed: {str(e)}",
            "details": [f"Error during OCR processing: {str(e)}"]
        }
