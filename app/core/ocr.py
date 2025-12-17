import easyocr
import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, Optional
from .mrz_detect import main as mrz_main
from mrz.checker.td3 import TD3CodeChecker
import logging
import tempfile
import os

logger = logging.getLogger(__name__)



def fix_ocr_angle_brackets(text: str, target_length: int = None) -> str:
    """
    Fix common OCR errors with '<' characters in MRZ text.
    
    The main issue is that OCR miscounts consecutive '<' characters at the end.
    This function fixes the count and ensures the text is the correct length.
    
    Args:
        text: Raw OCR text (single line, spaces/newlines will be removed)
        target_length: Target length for the text (88 for TD3 format)
        
    Returns:
        Text with corrected '<' characters and proper length
    """
    import re
    
    # Step 1: Remove all whitespace and invalid characters
    # Keep potential misreadings (>, L, I, 1, |, /) for analysis
    text = re.sub(r'[^A-Z0-9<>LI1\|/\-]', '', text)
    
    # Step 2: Fix dashes and '>' characters
    text = text.replace('-', '<')
    text = text.replace('>', '<')  # OCR sometimes reads '<' as '>'
    
    # Step 3: Fix obvious misreadings (sequences of L/I/1 that should be '<')
    text = re.sub(r'[LI1]{3,}', lambda m: '<' * len(m.group()), text)
    text = re.sub(r'\|{2,}', lambda m: '<' * len(m.group()), text)
    text = re.sub(r'/{2,}', lambda m: '<' * len(m.group()), text)
    
    # Step 4: Fix mixed sequences
    def fix_mixed_sequence(match):
        seq = match.group()
        if len(seq) >= 3:
            return '<' * len(seq)
        return seq
    text = re.sub(r'[<LI1\|]{3,}', fix_mixed_sequence, text)
    
    # Step 5: Final cleanup - remove any remaining invalid characters
    text = re.sub(r'[^A-Z0-9<]', '', text)
    
    # Step 6: Adjust length to target if specified
    # This is crucial - OCR often miscounts trailing '<' characters
    if target_length is not None:
        current_length = len(text)
        if current_length < target_length:
            # Pad with '<' at the end (these are filler characters)
            text = text + '<' * (target_length - current_length)
        elif current_length > target_length:
            # Trim from the end (trailing '<' are usually fillers)
            # Keep the important data at the start
            text = text[:target_length]
    
    return text


def validate_expiry_date(expiry_date_mrz: Optional[str]) -> Dict[str, Any]:
    """
    Validate passport expiry date from MRZ format (YYMMDD).
    
    Args:
        expiry_date_mrz: Expiry date in YYMMDD format from MRZ
        
    Returns:
        Dict with validation results
    """
    from datetime import datetime
    
    if not expiry_date_mrz:
        return {
            "valid": False,
            "error": "No expiry date found in MRZ",
            "expiry_date_formatted": None,
            "is_expired": None
        }
    
    try:
        # Parse YYMMDD format
        # Handle 2-digit year (assume 2000-2099 range)
        year = int(expiry_date_mrz[:2])
        month = int(expiry_date_mrz[2:4])
        day = int(expiry_date_mrz[4:6])
        
        # Convert 2-digit year to 4-digit (assume 00-99 means 2000-2099)
        if year < 100:
            year += 2000
        
        expiry_date = datetime(year, month, day)
        today = datetime.now()
        
        is_expired = expiry_date < today
        
        return {
            "valid": not is_expired,
            "is_expired": is_expired,
            "expiry_date_formatted": expiry_date.strftime("%Y-%m-%d"),
            "expiry_date_mrz": expiry_date_mrz,
            "days_until_expiry": (expiry_date - today).days if not is_expired else None,
            "days_expired": (today - expiry_date).days if is_expired else None
        }
    except (ValueError, IndexError) as e:
        logger.warning(f"Failed to parse expiry date '{expiry_date_mrz}': {str(e)}")
        return {
            "valid": False,
            "error": f"Invalid expiry date format: {expiry_date_mrz}",
            "expiry_date_formatted": None,
            "is_expired": None
        }


def compare_mrz_with_request_data(mrz_data: Dict[str, Any], request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare MRZ extracted data with API request data.
    Only compares fields that are present in the request data.
    
    Args:
        mrz_data: Data extracted from MRZ
        request_data: Data from API request (DocumentData)
        
    Returns:
        Dict with comparison results
    """
    from datetime import datetime
    from app.core.fuzzy_match import fuzzy_name_match
    
    mismatches = []
    matches = []
    warnings = []
    
    # Helper to normalize names (remove spaces, convert to uppercase)
    def normalize_name(name: str) -> str:
        if not name:
            return ""
        return name.upper().replace(" ", "").replace("<", "")
    
    # Helper to parse and format dates
    def parse_mrz_date(mrz_date: str) -> Optional[str]:
        """Convert YYMMDD to YYYY-MM-DD"""
        try:
            year = int(mrz_date[:2])
            month = int(mrz_date[2:4])
            day = int(mrz_date[4:6])
            if year < 100:
                year += 2000
            return f"{year:04d}-{month:02d}-{day:02d}"
        except:
            return None
    
    # Only compare fields that are present in request_data
    
    # 1. Document Number
    if "document_number" in request_data and request_data.get("document_number"):
        mrz_doc_num = mrz_data.get("document_number", "").replace("<", "").strip()
        req_doc_num = request_data.get("document_number", "").strip()
        if mrz_doc_num and req_doc_num:
            if mrz_doc_num.upper() == req_doc_num.upper():
                matches.append("document_number")
            else:
                # Use fuzzy matching for document numbers (OCR might misread some chars)
                similarity_score = fuzzy_name_match(mrz_doc_num.upper(), req_doc_num.upper())
                similarity = similarity_score / 100.0  # Convert 0-100 to 0-1
                if similarity >= 0.9:
                    warnings.append(f"Document number similar but not exact (similarity: {similarity:.2f})")
                    matches.append("document_number")
                else:
                    mismatches.append({
                        "field": "document_number",
                        "mrz_value": mrz_doc_num,
                        "request_value": req_doc_num,
                        "similarity": similarity
                    })
    
    # 2. Names (surname and given names) - only if first_name or last_name in request
    if "first_name" in request_data or "last_name" in request_data:
        mrz_surname = normalize_name(mrz_data.get("surname", ""))
        mrz_given_names = normalize_name(mrz_data.get("given_names", ""))
        req_last_name = normalize_name(request_data.get("last_name", ""))
        req_first_name = normalize_name(request_data.get("first_name", ""))
        
        # Compare surname/last name
        if mrz_surname and req_last_name:
            similarity_score = fuzzy_name_match(mrz_surname, req_last_name)
            similarity = similarity_score / 100.0  # Convert 0-100 to 0-1
            if similarity >= 0.85:  # Names can have slight variations
                matches.append("last_name")
            else:
                mismatches.append({
                    "field": "last_name",
                    "mrz_value": mrz_data.get("surname", ""),
                    "request_value": request_data.get("last_name", ""),
                    "similarity": similarity
                })
        
        # Compare given names/first name
        if mrz_given_names and req_first_name:
            # MRZ might have multiple given names, check if request name is contained
            similarity_score = fuzzy_name_match(mrz_given_names, req_first_name)
            similarity = similarity_score / 100.0  # Convert 0-100 to 0-1
            if similarity >= 0.80 or req_first_name in mrz_given_names or mrz_given_names in req_first_name:
                matches.append("first_name")
            else:
                mismatches.append({
                    "field": "first_name",
                    "mrz_value": mrz_data.get("given_names", ""),
                    "request_value": request_data.get("first_name", ""),
                    "similarity": similarity
                })
    
    # 3. Date of Birth
    if "date_of_birth" in request_data and request_data.get("date_of_birth"):
        mrz_dob = parse_mrz_date(mrz_data.get("birth_date", ""))
        req_dob = request_data.get("date_of_birth", "")
        if mrz_dob and req_dob:
            if mrz_dob == req_dob:
                matches.append("date_of_birth")
            else:
                mismatches.append({
                    "field": "date_of_birth",
                    "mrz_value": mrz_dob,
                    "request_value": req_dob
                })
    
    # 4. Nationality
    if "nationality" in request_data and request_data.get("nationality"):
        mrz_nationality = mrz_data.get("nationality", "").strip()
        req_nationality = request_data.get("nationality", "").strip()
        if mrz_nationality and req_nationality:
            if mrz_nationality.upper() == req_nationality.upper():
                matches.append("nationality")
            else:
                mismatches.append({
                    "field": "nationality",
                    "mrz_value": mrz_nationality,
                    "request_value": req_nationality
                })
    
    # 5. Expiry Date
    if "expiry_date" in request_data and request_data.get("expiry_date"):
        mrz_expiry = parse_mrz_date(mrz_data.get("expiry_date", ""))
        req_expiry = request_data.get("expiry_date", "")
        if mrz_expiry and req_expiry:
            if mrz_expiry == req_expiry:
                matches.append("expiry_date")
            else:
                mismatches.append({
                    "field": "expiry_date",
                    "mrz_value": mrz_expiry,
                    "request_value": req_expiry
                })
    
    # 6. Issuing Country (compare with MRZ country_code)
    if "issuing_country" in request_data and request_data.get("issuing_country"):
        mrz_country = mrz_data.get("country_code", "").strip()
        req_country = request_data.get("issuing_country", "").strip()
        if mrz_country and req_country:
            if mrz_country.upper() == req_country.upper():
                matches.append("issuing_country")
            else:
                mismatches.append({
                    "field": "issuing_country",
                    "mrz_value": mrz_country,
                    "request_value": req_country
                })
    
    return {
        "matches": matches,
        "mismatches": mismatches,
        "warnings": warnings,
        "match_count": len(matches),
        "mismatch_count": len(mismatches),
        "all_match": len(mismatches) == 0
    }


def parse_mrz(mrz_text: str) -> dict:
    try:
        td3_check = TD3CodeChecker(mrz_text)
        if not td3_check.fields:
            return {"error": "Invalid MRZ format"}
        fields = td3_check.fields()
        return {
            "document_type": fields.document_type,
            "country_code": fields.country,
            "surname": fields.surname,
            "given_names": fields.name,
            "document_number": fields.document_number,
            "nationality": fields.nationality,
            "birth_date": fields.birth_date,  # YYMMDD format
            "sex": fields.sex,
            "expiry_date": fields.expiry_date, # YYMMDD format
            "valid_composite": bool(td3_check) # Checksums check
        }
    except Exception as e:
        return {"error": str(e)}


def try_extract_mrz_at_orientation(img_bgr: np.ndarray, orientation: int = 0) -> Optional[np.ndarray]:
    """
    Try to extract MRZ from image at a specific orientation.
    
    Args:
        img_bgr: BGR image as numpy array
        orientation: Rotation in degrees (0, 90, 180, 270)
        
    Returns:
        MRZ image if found, None otherwise
    """
    try:
        # Rotate image if needed
        if orientation == 90:
            img_rotated = cv2.rotate(img_bgr, cv2.ROTATE_90_CLOCKWISE)
        elif orientation == 180:
            img_rotated = cv2.rotate(img_bgr, cv2.ROTATE_180)
        elif orientation == 270:
            img_rotated = cv2.rotate(img_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            img_rotated = img_bgr
        
        # Save to temporary file for mrz_detect
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            cv2.imwrite(tmp_path, img_rotated)
        
        try:
            mrz_image = mrz_main(tmp_path, debug=False)
            return mrz_image
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
    except Exception as e:
        logger.debug(f"MRZ extraction failed at orientation {orientation}: {str(e)}")
        return None


def extract_mrz_from_image(image: Image.Image) -> Optional[np.ndarray]:
    """
    Extract MRZ region from a PIL Image.
    Tries multiple orientations if MRZ is not found in the original orientation.
    
    Args:
        image: PIL Image of the document
        
    Returns:
        numpy array of the MRZ region, or None if not found
    """
    try:
        # Convert PIL Image to numpy array (RGB)
        img_array = np.array(image)
        
        # Convert RGB to BGR for OpenCV
        if len(img_array.shape) == 3:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = img_array
        
        # Try extracting MRZ at different orientations
        # Passports can be scanned/photoed at different angles
        orientations = [0, 90, 180, 270]
        
        for orientation in orientations:
            logger.debug(f"Trying MRZ extraction at {orientation} degrees")
            mrz_image = try_extract_mrz_at_orientation(img_bgr, orientation)
            
            if mrz_image is not None:
                logger.info(f"MRZ found at {orientation} degree orientation")
                return mrz_image
        
        # If we get here, MRZ wasn't found at any orientation
        logger.warning("MRZ extraction returned None - no MRZ found in document at any orientation")
        return None
                
    except Exception as e:
        logger.error(f"Error extracting MRZ from image: {str(e)}")
        return None


def validate_document_ocr(document_image: Image.Image) -> Dict[str, Any]:
    """
    Validate document using OCR to extract and parse MRZ data.
    
    Args:
        document_image: PIL Image of the document
        
    Returns:
        Dict containing:
            - valid: bool - whether document validation passed
            - mrz_data: dict - parsed MRZ data
            - error: Optional[str] - error message if any
            - details: list - validation details
    """
    try:
        # Extract MRZ region
        mrz_image = extract_mrz_from_image(document_image)
        
        if mrz_image is None:
            return {
                "valid": False,
                "mrz_data": None,
                "error": "Could not extract MRZ from document",
                "details": ["MRZ extraction failed"]
            }
        
        # Initialize EasyOCR reader (lazy initialization could be added)
        try:
            reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        except Exception as e:
            logger.error(f"Failed to initialize EasyOCR: {str(e)}")
            return {
                "valid": False,
                "mrz_data": None,
                "error": f"OCR initialization failed: {str(e)}",
                "details": ["OCR reader initialization failed"]
            }
        
        # Read text from MRZ image
        try:
            results = reader.readtext(mrz_image, detail=0)
            
            # Clean and format MRZ text
            # MRZ text should be continuous lines without spaces
            cleaned_lines = []
            for line in results:
                # Remove spaces and convert to uppercase
                cleaned_line = line.upper().replace(" ", "").replace("\n", "").strip()
                if cleaned_line:
                    cleaned_lines.append(cleaned_line)
            
            # Fix alignment: If first line starts with a single letter followed by country code,
            # it's likely a single-letter document type (e.g., "P" for passport)
            # TD3 format requires 2 characters for document type
            if cleaned_lines and len(cleaned_lines[0]) > 0:
                first_line = cleaned_lines[0]
                # Check if it starts with a single letter followed by 3-letter country code
                # Pattern: P + EGY -> should be P< + EGY
                if len(first_line) >= 4 and first_line[0].isalpha() and first_line[1:4].isalpha():
                    # Check if positions 1-3 form a country code (3 uppercase letters)
                    potential_country = first_line[1:4]
                    if potential_country.isalpha() and len(potential_country) == 3:
                        # Insert '<' after the first character to pad document type
                        cleaned_lines[0] = first_line[0] + '<' + first_line[1:]
                        logger.debug(f"Fixed document type alignment: {first_line[:5]} -> {cleaned_lines[0][:5]}")
            
            # Join lines - MRZ typically has 2-3 lines
            mrz_text = "\n".join(cleaned_lines)
            
            # Also create a single-line version for parsing (some parsers expect this)
            mrz_text_single = "".join(cleaned_lines)
            
            if not mrz_text:
                return {
                    "valid": False,
                    "mrz_data": None,
                    "error": "No text extracted from MRZ",
                    "details": ["OCR could not read MRZ text"]
                }
            
            # Post-process to fix common OCR errors with '<' characters
            # TD3 format requires 88 characters total (2 lines of 44)
            mrz_text_single_before_fix = mrz_text_single
            
            # Fix the text and ensure it's the correct length for TD3 (88 chars)
            mrz_text_single = fix_ocr_angle_brackets(mrz_text_single, target_length=88)
            
            # Rebuild multi-line version (2 lines of 44 chars each)
            if len(mrz_text_single) >= 88:
                mrz_text = mrz_text_single[:44] + "\n" + mrz_text_single[44:88]
            else:
                # If still short, pad to 88
                mrz_text_single = mrz_text_single + '<' * (88 - len(mrz_text_single))
                mrz_text = mrz_text_single[:44] + "\n" + mrz_text_single[44:88]
            
            logger.debug(f"Extracted MRZ text ({len(mrz_text_single_before_fix)} -> {len(mrz_text_single)} chars)")
            logger.debug(f"Before fix: {mrz_text_single_before_fix[:60]}...")
            logger.debug(f"After fix:  {mrz_text_single[:60]}...")
            
            # Log if length is not standard (TD3 should be 88 or 89 chars)
            if len(mrz_text_single) not in [88, 89]:
                logger.warning(f"MRZ text length is {len(mrz_text_single)}, expected 88-89 for TD3 format")
        except Exception as e:
            logger.error(f"OCR text extraction failed: {str(e)}")
            return {
                "valid": False,
                "mrz_data": None,
                "error": f"OCR text extraction failed: {str(e)}",
                "details": ["OCR text extraction failed"]
            }
        
        # Parse MRZ - try both multi-line and single-line formats
        mrz_data = parse_mrz(mrz_text)
        
        # If parsing fails, try with single-line format
        if "error" in mrz_data:
            logger.debug("Trying single-line MRZ format")
            mrz_data = parse_mrz(mrz_text_single)
        
        if "error" in mrz_data:
            return {
                "valid": False,
                "mrz_data": mrz_data,
                "error": mrz_data["error"],
                "details": [f"MRZ parsing failed: {mrz_data['error']}"]
            }
        
        # Check if MRZ is valid (checksums pass)
        # Note: We'll still proceed even if checksums fail, as OCR errors can cause this
        checksum_valid = mrz_data.get("valid_composite", False)
        
        # Validate expiry date
        expiry_validation = validate_expiry_date(mrz_data.get("expiry_date"))
        
        # Build details list
        details = [
            "MRZ extraction successful",
            "OCR text extraction successful",
            "MRZ parsing successful"
        ]
        
        if checksum_valid:
            details.append("MRZ checksums validated")
        else:
            details.append("MRZ checksum validation failed (may be due to OCR errors)")
        
        if expiry_validation["valid"]:
            details.append(f"Document expiry date valid: {expiry_validation['expiry_date_formatted']}")
        else:
            details.append(f"Document expired: {expiry_validation['expiry_date_formatted']}")
        
        # Document validation passed if MRZ was parsed (even if checksums fail)
        # Expiry date failure will be handled separately
        return {
            "valid": checksum_valid and expiry_validation["valid"],
            "mrz_data": mrz_data,
            "expiry_validation": expiry_validation,
            "error": None if (checksum_valid and expiry_validation["valid"]) else "Document validation issues found",
            "details": details
        }
        
    except Exception as e:
        logger.error(f"Document OCR validation failed: {str(e)}", exc_info=True)
        return {
            "valid": False,
            "mrz_data": None,
            "error": f"Document validation error: {str(e)}",
            "details": [f"Validation error: {str(e)}"]
        }


if __name__ == "__main__":
    file = "../../tests/data/sample_passports/canada.jpg"
    mrz_image = mrz_main(file)
    reader = easyocr.Reader(['en'], gpu=False)
    results = reader.readtext(mrz_image, detail=0)
    mrz_text = "\n".join(results)
    mrz_text = mrz_text.upper().replace(" ", "").strip()
    print(f"\nMRZ Text:\n{mrz_text}\n")
    print(f"\nParsed Data:\n {parse_mrz(mrz_text)}")