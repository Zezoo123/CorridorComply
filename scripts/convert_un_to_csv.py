#!/usr/bin/env python3
"""
Convert UN sanctions XML to CSV format
Parses consolidatedLegacyByPRN.xml and creates un_sanctions.csv with comprehensive fields
"""
import xml.etree.ElementTree as ET
import csv
from pathlib import Path
from typing import List, Dict, Optional, Set
import re


def extract_text(element, tag: str, default: str = "") -> str:
    """Extract text from XML element, return default if not found"""
    found = element.find(tag)
    if found is not None and found.text:
        return found.text.strip()
    return default


def extract_value_list(element, tag: str) -> List[str]:
    """Extract all VALUE elements from a tag"""
    values = []
    parent = element.find(tag)
    if parent is not None:
        for value_elem in parent.findall("VALUE"):
            if value_elem.text:
                values.append(value_elem.text.strip())
    return values


def extract_all_children_text(element, tag: str) -> List[str]:
    """Extract text from all child elements with given tag"""
    values = []
    for child in element.findall(tag):
        if child.text:
            values.append(child.text.strip())
    return values


def join_list(items: List[str], separator: str = "; ") -> str:
    """Join list items with separator, filter empty strings"""
    return separator.join(filter(None, items))


def parse_individual(individual_elem, source: str, source_file: str) -> Dict[str, str]:
    """
    Parse an INDIVIDUAL element and return comprehensive record
    
    Returns:
        Dictionary with all extracted fields
    """
    # Basic identifiers
    dataid = extract_text(individual_elem, "DATAID")
    reference_number = extract_text(individual_elem, "REFERENCE_NUMBER")
    
    # Name components
    first_name = extract_text(individual_elem, "FIRST_NAME")
    second_name = extract_text(individual_elem, "SECOND_NAME")
    third_name = extract_text(individual_elem, "THIRD_NAME", "")  # May not exist
    fourth_name = extract_text(individual_elem, "FOURTH_NAME", "")  # May not exist
    
    # Build full name from components
    name_parts = [first_name, second_name, third_name, fourth_name]
    name = " ".join(filter(None, name_parts)).strip()
    
    # Aliases - collect all "Good" quality aliases
    aliases = []
    alias_elems = individual_elem.findall("INDIVIDUAL_ALIAS")
    for alias_elem in alias_elems:
        alias_name = extract_text(alias_elem, "ALIAS_NAME")
        quality = extract_text(alias_elem, "QUALITY", "").lower()
        # Include "Good" quality or aliases without quality specified
        if alias_name and (quality == "good" or quality == ""):
            aliases.append(alias_name)
    
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
        # Check for full DATE field first
        date_str = extract_text(dob_elem, "DATE")
        if date_str:
            dob_dates.append(date_str)
        else:
            # Otherwise try YEAR
            year = extract_text(dob_elem, "YEAR")
            if year:
                dob_years.append(year)
    
    dob_dates_str = join_list(dob_dates)
    dob_years_str = join_list(dob_years)
    
    # Place of birth - can have multiple entries
    pob_cities = []
    pob_countries = []
    pob_elems = individual_elem.findall("INDIVIDUAL_PLACE_OF_BIRTH")
    for pob_elem in pob_elems:
        city = extract_text(pob_elem, "CITY")
        country = extract_text(pob_elem, "COUNTRY")
        if city:
            pob_cities.append(city)
        if country:
            pob_countries.append(country)
    
    pob_cities_str = join_list(pob_cities)
    pob_countries_str = join_list(pob_countries)
    
    # Addresses - can have multiple entries
    addresses = []
    address_elems = individual_elem.findall("INDIVIDUAL_ADDRESS")
    for addr_elem in address_elems:
        city = extract_text(addr_elem, "CITY")
        state = extract_text(addr_elem, "STATE_PROVINCE")
        country = extract_text(addr_elem, "COUNTRY")
        note = extract_text(addr_elem, "NOTE")
        
        # Build address string
        addr_parts = []
        if city:
            addr_parts.append(city)
        if state:
            addr_parts.append(state)
        if country:
            addr_parts.append(country)
        if note:
            addr_parts.append(f"({note})")
        
        if addr_parts:
            addresses.append(", ".join(addr_parts))
    
    addresses_str = join_list(addresses)
    
    # Documents - can have multiple entries
    id_numbers = []
    doc_elems = individual_elem.findall("INDIVIDUAL_DOCUMENT")
    for doc_elem in doc_elems:
        doc_type = extract_text(doc_elem, "TYPE_OF_DOCUMENT")
        doc_number = extract_text(doc_elem, "NUMBER")
        issuing_country = extract_text(doc_elem, "ISSUING_COUNTRY")
        
        if doc_number:
            doc_info = doc_number
            if doc_type:
                doc_info = f"{doc_type}: {doc_info}"
            if issuing_country:
                doc_info = f"{doc_info} ({issuing_country})"
            id_numbers.append(doc_info)
    
    id_numbers_str = join_list(id_numbers)
    
    # UN List Type
    un_list_type = extract_text(individual_elem, "UN_LIST_TYPE")
    
    # List Type
    list_type_values = extract_value_list(individual_elem, "LIST_TYPE")
    list_type = join_list(list_type_values)
    
    # Program (use UN_LIST_TYPE if no separate program field)
    program = un_list_type  # Can be enhanced if PROGRAM field exists
    
    # Comments/Narrative
    comments = extract_text(individual_elem, "COMMENTS1", "")
    # Also check for other comment fields
    comments2 = extract_text(individual_elem, "COMMENTS2", "")
    if comments2:
        comments = f"{comments} {comments2}".strip()
    
    # Listed on date
    listed_on = extract_text(individual_elem, "LISTED_ON")
    
    # Last updated
    last_updated_values = extract_value_list(individual_elem, "LAST_DAY_UPDATED")
    last_updated = join_list(last_updated_values)
    
    # Build record
    record = {
        "source": source,
        "source_file": source_file,
        "record_type": "individual",
        "dataid": dataid,
        "reference_number": reference_number,
        "name": name.upper() if name else "",  # Normalize to uppercase
        "first_name": first_name,
        "second_name": second_name,
        "third_name": third_name,
        "fourth_name": fourth_name,
        "aliases": join_list(aliases),
        "gender": gender,
        "nationalities": nationalities,
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
    }
    
    return record


def convert_xml_to_csv(xml_path: Path, csv_path: Path, source: str = "UN"):
    """
    Convert UN sanctions XML file to CSV
    
    Args:
        xml_path: Path to input XML file
        csv_path: Path to output CSV file
        source: Source identifier (e.g., "UN")
    """
    print(f"Parsing XML file: {xml_path}")
    source_file = xml_path.name
    
    # Parse XML
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # Find all INDIVIDUAL elements
    individuals = root.findall(".//INDIVIDUAL")
    print(f"Found {len(individuals)} individuals in XML")
    
    # Parse all individuals
    all_records = []
    for idx, individual in enumerate(individuals):
        if (idx + 1) % 1000 == 0:
            print(f"  Processed {idx + 1}/{len(individuals)} individuals...")
        
        record = parse_individual(individual, source, source_file)
        all_records.append(record)
    
    print(f"Generated {len(all_records)} records")
    
    # Write to CSV
    if not all_records:
        print("Warning: No records to write!")
        return
    
    # Define CSV columns in the order requested
    fieldnames = [
        "source",
        "source_file",
        "record_type",
        "dataid",
        "reference_number",
        "name",
        "first_name",
        "second_name",
        "third_name",
        "fourth_name",
        "aliases",
        "gender",
        "nationalities",
        "pob_cities",
        "pob_countries",
        "dob_dates",
        "dob_years",
        "un_list_type",
        "list_type",
        "program",
        "comments",
        "listed_on",
        "last_updated",
        "addresses",
        "id_numbers",
    ]
    
    print(f"Writing CSV file: {csv_path}")
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)
    
    print(f"✓ Successfully created {csv_path}")
    print(f"  Total records: {len(all_records)}")
    
    # Show sample statistics
    records_with_aliases = sum(1 for r in all_records if r["aliases"])
    records_with_dob = sum(1 for r in all_records if r["dob_dates"] or r["dob_years"])
    records_with_docs = sum(1 for r in all_records if r["id_numbers"])
    
    print(f"\nStatistics:")
    print(f"  Records with aliases: {records_with_aliases}")
    print(f"  Records with DOB: {records_with_dob}")
    print(f"  Records with documents: {records_with_docs}")


def main():
    """Main function"""
    # Paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    xml_file = project_root / "app" / "data" / "sanctions" / "raw" / "un" / "consolidatedLegacyByPRN.xml"
    csv_file = project_root / "app" / "data" / "sanctions" / "normalized" / "un" / "un_sanctions.csv"
    
    if not xml_file.exists():
        print(f"Error: XML file not found: {xml_file}")
        return
    
    # Convert
    convert_xml_to_csv(xml_file, csv_file, source="UN")
    
    print("\n" + "="*60)
    print("Conversion complete!")
    print("="*60)
    print(f"\nCSV file ready: {csv_file}")
    print("\nNext steps:")
    print("1. Review the CSV file to ensure data looks correct")
    print("2. Test with: python -c \"from app.services.sanctions_loader import SanctionsLoader; df = SanctionsLoader.load_sanctions(); print(df.head()); print(f'Total: {len(df)} records')\"")


if __name__ == "__main__":
    main()
