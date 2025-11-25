#!/usr/bin/env python3
"""
Convert UN sanctions XML to CSV format

This script parses the UN sanctions XML file (consolidatedLegacyByPRN.xml) and converts it to a normalized
CSV format compatible with the existing EU and UK sanctions data.
"""
import xml.etree.ElementTree as ET
import csv
import logging
import re
import unicodedata
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Optional, Set, Any, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sanctions_processing.log')
    ]
)
logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Clean and normalize text by removing extra whitespace and normalizing unicode."""
    if not text or pd.isna(text):
        return ''
    
    # Convert to string and normalize unicode
    text = str(text)
    text = unicodedata.normalize('NFKC', text)
    
    # Remove extra whitespace and newlines
    text = ' '.join(text.split())
    
    return text.strip()

def extract_text(element, tag: str, default: str = "") -> str:
    """
    Extract text from XML element, return default if not found.
    
    Args:
        element: XML element to search within
        tag: Tag name to find
        default: Default value if tag not found or empty
        
    Returns:
        Cleaned text content of the tag or default value
    """
    try:
        found = element.find(tag)
        if found is not None and found.text:
            return clean_text(found.text)
    except Exception as e:
        logger.warning(f"Error extracting text for tag '{tag}': {e}")
    return default


def extract_value_list(element, tag: str) -> List[str]:
    """
    Extract all VALUE elements from a tag.
    
    Args:
        element: XML element to search within
        tag: Tag name to find
        
    Returns:
        List of cleaned text values
    """
    values = []
    try:
        parent = element.find(tag)
        if parent is not None:
            for value_elem in parent.findall("VALUE"):
                if value_elem.text:
                    values.append(clean_text(value_elem.text))
    except Exception as e:
        logger.warning(f"Error extracting value list for tag '{tag}': {e}")
    
    return values


def extract_all_children_text(element, tag: str) -> List[str]:
    """
    Extract text from all child elements with given tag.
    
    Args:
        element: XML element to search within
        tag: Tag name to find
        
    Returns:
        List of cleaned text values from matching child elements
    """
    values = []
    try:
        for child in element.findall(tag):
            if child.text:
                values.append(clean_text(child.text))
    except Exception as e:
        logger.warning(f"Error extracting children text for tag '{tag}': {e}")
    
    return values


def join_list(items: List[str], separator: str = "; ") -> str:
    """
    Join list items with separator, filter empty strings.
    
    Args:
        items: List of strings to join
        separator: Separator to use between items
        
    Returns:
        Joined string or empty string if no valid items
    """
    if not items:
        return ""
    return separator.join(filter(None, [str(item).strip() for item in items]))


def parse_individual(individual_elem, source: str, source_file: str) -> Dict[str, str]:
    """
    Parse an INDIVIDUAL element and return comprehensive record.
    
    Args:
        individual_elem: XML element containing individual data
        source: Source identifier (e.g., "UN")
        source_file: Source file name
        
    Returns:
        Dictionary with all extracted fields
    """
    try:
        # Basic identifiers
        dataid = extract_text(individual_elem, "DATAID").strip()
        reference_number = extract_text(individual_elem, "REFERENCE_NUMBER").strip()
        
        # Name components
        first_name = extract_text(individual_elem, "FIRST_NAME")
        second_name = extract_text(individual_elem, "SECOND_NAME")
        third_name = extract_text(individual_elem, "THIRD_NAME", "")  # May not exist
        fourth_name = extract_text(individual_elem, "FOURTH_NAME", "")  # May not exist
        
        # Build full name from components
        name_parts = [first_name, second_name, third_name, fourth_name]
        name = " ".join(filter(None, name_parts)).strip()
        
        # If name is empty, try to get it from the title
        if not name:
            name = extract_text(individual_elem, "TITLE")
        
        # Normalize name to uppercase
        name = name.upper() if name else ""
        
        # Aliases - collect all "Good" quality aliases
        aliases = []
        alias_elems = individual_elem.findall("INDIVIDUAL_ALIAS")
        for alias_elem in alias_elems:
            try:
                alias_name = extract_text(alias_elem, "ALIAS_NAME")
                quality = extract_text(alias_elem, "QUALITY", "").lower()
                # Include "Good" quality or aliases without quality specified
                if alias_name and (quality == "good" or quality == ""):
                    aliases.append(alias_name.upper())
            except Exception as e:
                logger.warning(f"Error processing alias for {dataid}: {e}")
    
        # Gender
        gender = extract_text(individual_elem, "GENDER")
        
        # Nationalities (can have multiple)
        nationality_values = extract_value_list(individual_elem, "NATIONALITY")
        nationalities = join_list(nationality_values)
    
        # Date of birth - can have multiple entries
        dob_dates = []
        dob_years = []
        dob_elems = individual_elem.findall("INDIVIDUAL_DATE_OF_BIRTH")
        for dob_elem in dob_elems:
            try:
                # Check for full DATE field first
                date_str = extract_text(dob_elem, "DATE")
                if date_str:
                    # Try to standardize date format
                    try:
                        # Try to parse and reformat the date
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        date_str = date_obj.strftime('%Y-%m-%d')
                    except ValueError:
                        pass  # Keep original format if parsing fails
                    dob_dates.append(date_str)
                else:
                    # Otherwise try YEAR
                    year = extract_text(dob_elem, "YEAR")
                    if year and year.isdigit() and len(year) == 4:
                        dob_years.append(year)
            except Exception as e:
                logger.warning(f"Error processing DOB for {dataid}: {e}")
        
        dob_dates_str = join_list(dob_dates)
        dob_years_str = join_list(dob_years)
    
        # Place of birth - can have multiple entries
        pob_cities = []
        pob_countries = []
        pob_elems = individual_elem.findall("INDIVIDUAL_PLACE_OF_BIRTH")
        for pob_elem in pob_elems:
            try:
                city = extract_text(pob_elem, "CITY")
                country = extract_text(pob_elem, "COUNTRY")
                if city:
                    pob_cities.append(city.upper())
                if country:
                    pob_countries.append(country.upper())
            except Exception as e:
                logger.warning(f"Error processing place of birth for {dataid}: {e}")
        
        pob_cities_str = join_list(pob_cities)
        pob_countries_str = join_list(pob_countries)
    
        # Addresses - can have multiple entries
        addresses = []
        address_elems = individual_elem.findall("INDIVIDUAL_ADDRESS")
        for addr_elem in address_elems:
            try:
                street = extract_text(addr_elem, "STREET")
                city = extract_text(addr_elem, "CITY")
                state = extract_text(addr_elem, "STATE_PROVINCE")
                postal_code = extract_text(addr_elem, "ZIP_CODE")
                country = extract_text(addr_elem, "COUNTRY")
                note = extract_text(addr_elem, "NOTE")
                
                # Build address string
                addr_parts = []
                if street:
                    addr_parts.append(street.upper())
                if city:
                    addr_parts.append(city.upper())
                if state:
                    addr_parts.append(state.upper())
                if postal_code:
                    addr_parts.append(postal_code)
                if country:
                    addr_parts.append(country.upper())
                if note:
                    addr_parts.append(f"({note.upper()})")
                
                if addr_parts:
                    addresses.append(", ".join(addr_parts))
            except Exception as e:
                logger.warning(f"Error processing address for {dataid}: {e}")
        
        addresses_str = join_list(addresses)
    
        # Documents - can have multiple entries
        id_numbers = []
        doc_elems = individual_elem.findall("INDIVIDUAL_DOCUMENT")
        for doc_elem in doc_elems:
            try:
                doc_type = extract_text(doc_elem, "TYPE_OF_DOCUMENT")
                doc_number = extract_text(doc_elem, "NUMBER")
                issuing_country = extract_text(doc_elem, "ISSUING_COUNTRY")
                
                if doc_number:
                    doc_info = doc_number.upper()
                    if doc_type:
                        doc_info = f"{doc_type.upper()}: {doc_info}"
                    if issuing_country:
                        doc_info = f"{doc_info} ({issuing_country.upper()})"
                    id_numbers.append(doc_info)
            except Exception as e:
                logger.warning(f"Error processing document for {dataid}: {e}")
        
        id_numbers_str = join_list(id_numbers)
    
        # UN List Type and Program
        un_list_type = extract_text(individual_elem, "UN_LIST_TYPE")
        
        # List Type
        list_type_values = extract_value_list(individual_elem, "LIST_TYPE")
        list_type = join_list(list_type_values)
        
        # Program (use UN_LIST_TYPE if no separate program field)
        program = un_list_type  # Can be enhanced if PROGRAM field exists
        
        # Comments/Narrative - combine all available comment fields
        comments_parts = []
        for i in range(1, 6):  # Check COMMENTS1 through COMMENTS5
            comment = extract_text(individual_elem, f"COMMENTS{i}", "").strip()
            if comment:
                comments_parts.append(comment)
        
        comments = " ".join(comments_parts).strip()
        
        # Listed on date - try to standardize format
        listed_on = ""
        listed_on_raw = extract_text(individual_elem, "LISTED_ON")
        if listed_on_raw:
            try:
                # Try to parse and reformat the date
                date_obj = datetime.strptime(listed_on_raw, '%Y-%m-%d')
                listed_on = date_obj.strftime('%Y-%m-%d')
            except ValueError:
                listed_on = listed_on_raw  # Keep original if parsing fails
        
        # Last updated - get the most recent date
        last_updated = ""
        last_updated_values = extract_value_list(individual_elem, "LAST_DAY_UPDATED")
        if last_updated_values:
            try:
                # Get the most recent date
                dates = []
                for date_str in last_updated_values:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                        dates.append((date_obj, date_str))
                    except ValueError:
                        continue
                
                if dates:
                    # Sort by date (newest first) and take the first one
                    dates.sort(reverse=True, key=lambda x: x[0])
                    last_updated = dates[0][1]
            except Exception as e:
                logger.warning(f"Error processing last_updated for {dataid}: {e}")
                last_updated = last_updated_values[0]  # Fallback to first value
    
        # Build record with all fields
        record = {
            "source": source,
            "source_file": source_file,
            "record_type": "individual",
            "dataid": dataid,
            "reference_number": reference_number,
            "name": name,
            "first_name": first_name.upper() if first_name else "",
            "middle_name": third_name.upper() if third_name else "",  # Using third_name as middle_name
            "last_name": second_name.upper() if second_name else "",
            "aliases": join_list(aliases),
            "gender": gender.upper() if gender else "",
            "nationalities": nationalities.upper() if nationalities else "",
            "pob_cities": pob_cities_str,
            "pob_countries": pob_countries_str,
            "dob_dates": dob_dates_str,
            "dob_years": dob_years_str,
            "un_list_type": un_list_type,
            "list_type": list_type,
            "program": program,
            "comments": comments,
            "listed_on": listed_on,
            "last_updated": last_updated,
            "addresses": addresses_str,
            "id_numbers": id_numbers_str,
            "processing_date": date.today().isoformat()
        }
        
        return record
        
    except Exception as e:
        logger.error(f"Error parsing individual record: {e}", exc_info=True)
        return None


def save_output(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save the DataFrame to a CSV file with proper formatting.
    
    Args:
        df: DataFrame to save
        output_path: Path to save the file to
    """
    try:
        # Ensure the output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build save arguments
        save_args = {
            'path_or_buf': output_path,
            'index': False,
            'encoding': 'utf-8',
            'quoting': 1,  # Quote all fields
            'quotechar': '"',
            'escapechar': '\\',
            'date_format': '%Y-%m-%d'
        }
        
        # Check pandas version to handle line_terminator parameter
        import pandas as pd
        if pd.__version__ < '2.0.0':
            save_args['line_terminator'] = '\n'
        # Save the DataFrame
        df.to_csv(**save_args)
        logger.info(f"Successfully saved output to {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving output file {output_path}: {e}")
        raise

def convert_xml_to_csv(xml_path: Path, output_dir: Path, source: str = "UN") -> Tuple[Path, int]:
    """
    Convert UN sanctions XML file to CSV with standardized format.
    
    Args:
        xml_path: Path to input XML file
        output_dir: Directory to save output CSV files
        source: Source identifier (e.g., "UN")
        
    Returns:
        Tuple of (output_path, record_count)
    """
    start_time = datetime.now()
    logger.info(f"Parsing XML file: {xml_path}")
    source_file = xml_path.name
    
    try:
        # Parse XML
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Find all INDIVIDUAL elements
        individuals = root.findall(".//INDIVIDUAL")
        logger.info(f"Found {len(individuals)} individuals in XML")
        
        # Parse all individuals
        all_records = []
        for idx, individual in enumerate(individuals):
            if (idx + 1) % 1000 == 0:
                logger.info(f"  Processed {idx + 1}/{len(individuals)} individuals...")
            
            record = parse_individual(individual, source, source_file)
            if record:  # Only add if parsing was successful
                all_records.append(record)
        
        if not all_records:
            logger.error("No valid records were generated")
            return None, 0
        
        # Create DataFrame
        df = pd.DataFrame(all_records)
        
        # Reorder columns to match other sanctions lists
        column_order = [
            'source', 'source_file', 'dataid', 'reference_number', 'list_type',
            'record_type', 'name', 'first_name', 'middle_name', 'last_name',
            'aliases', 'nationalities', 'gender', 'pob_cities', 'pob_countries',
            'dob_dates', 'dob_years', 'addresses', 'id_numbers', 'program',
            'comments', 'listed_on', 'last_updated', 'processing_date', 'un_list_type'
        ]
        
        # Only include columns that exist in the DataFrame
        existing_columns = [col for col in column_order if col in df.columns]
        df = df[existing_columns]
        
        # Create date-based filename
        today = date.today().strftime('%Y%m%d')
        output_filename = f"un_sanctions_{today}.csv"
        output_path = output_dir / output_filename
        latest_path = output_dir / "un_sanctions_latest.csv"
        
        # Save the data
        save_output(df, output_path)
        
        # Create/update the latest symlink
        try:
            if latest_path.exists():
                latest_path.unlink()
            latest_path.symlink_to(output_path.name)
            logger.info(f"Created symlink: {latest_path} -> {output_path.name}")
        except OSError as e:
            logger.warning(f"Could not create symlink: {e}")
        
        # Log statistics
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Processed {len(df)} records in {duration:.2f} seconds")
        
        # Additional statistics
        if 'record_type' in df.columns:
            type_counts = df['record_type'].value_counts().to_dict()
            logger.info("Record type distribution:")
            for rec_type, count in type_counts.items():
                logger.info(f"  {rec_type}: {count} records")
        
        # Show sample records
        logger.info("\nSample records:")
        for _, row in df.head(3).iterrows():
            logger.info(f"\n  Name: {row.get('name', 'N/A')}")
            logger.info(f"  Type: {row.get('record_type', 'N/A')}")
            logger.info(f"  Nationalities: {row.get('nationalities', 'N/A')}")
            logger.info(f"  Program: {row.get('program', 'N/A')}")
        
        return output_path, len(df)
        
    except Exception as e:
        logger.error(f"Error processing XML file: {e}", exc_info=True)
        return None, 0


def main() -> int:
    """
    Main function to process UN sanctions data.
    
    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    start_time = datetime.now()
    logger.info("\n" + "="*60)
    logger.info("Starting UN sanctions conversion")
    logger.info("="*60)
    
    try:
        # Set up paths
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        xml_file = project_root / "app" / "data" / "sanctions" / "raw" / "un" / "consolidatedLegacyByPRN.xml"
        output_dir = project_root / "app" / "data" / "sanctions" / "normalized" / "un"
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if input file exists
        if not xml_file.exists():
            logger.error(f"XML file not found: {xml_file}")
            return 1
        
        # Convert the file
        output_path, record_count = convert_xml_to_csv(xml_file, output_dir, source="UN")
        
        if not output_path or record_count == 0:
            logger.error("Failed to convert UN sanctions data")
            return 1
        
        # Log completion
        duration = (datetime.now() - start_time).total_seconds()
        logger.info("\n" + "="*60)
        logger.info("Conversion complete!")
        logger.info("="*60)
        logger.info(f"Input file: {xml_file.name}")
        logger.info(f"Output: {record_count} normalized records")
        logger.info(f"Output file: {output_path}")
        logger.info(f"Processing time: {duration:.2f} seconds")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        return 1
    
    finally:
        # Ensure all logs are flushed
        for handler in logger.handlers:
            handler.flush()


if __name__ == "__main__":
    import sys
    sys.exit(main())
