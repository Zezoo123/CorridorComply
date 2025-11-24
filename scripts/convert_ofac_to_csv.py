#!/usr/bin/env python3
"""
Convert OFAC sanctions CSV files to normalized format
Combines sdn.csv, alt.csv, and add.csv into a single normalized CSV file
with consistent schema matching the EU sanctions format.
"""
import os
import re
import sys
import logging
import unicodedata
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, date
from collections import defaultdict

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

# ISO 3166-1 alpha-2 country codes (uppercase)
COUNTRY_CODES = {
    # Standard country codes
    'AF': 'AFGHANISTAN', 'AL': 'ALBANIA', 'DZ': 'ALGERIA', 'AD': 'ANDORRA',
    'AO': 'ANGOLA', 'AG': 'ANTIGUA AND BARBUDA', 'AR': 'ARGENTINA', 
    'AM': 'ARMENIA', 'AU': 'AUSTRALIA', 'AT': 'AUSTRIA', 'AZ': 'AZERBAIJAN',
    'BS': 'BAHAMAS', 'BH': 'BAHRAIN', 'BD': 'BANGLADESH', 'BB': 'BARBADOS',
    'BY': 'BELARUS', 'BE': 'BELGIUM', 'BZ': 'BELIZE', 'BJ': 'BENIN',
    'BT': 'BHUTAN', 'BO': 'BOLIVIA', 'BA': 'BOSNIA AND HERZEGOVINA',
    'BW': 'BOTSWANA', 'BR': 'BRAZIL', 'BN': 'BRUNEI DARUSSALAM',
    'BG': 'BULGARIA', 'BF': 'BURKINA FASO', 'BI': 'BURUNDI',
    'CV': 'CABO VERDE', 'KH': 'CAMBODIA', 'CM': 'CAMEROON', 'CA': 'CANADA',
    'CF': 'CENTRAL AFRICAN REPUBLIC', 'TD': 'CHAD', 'CL': 'CHILE',
    'CN': 'CHINA', 'CO': 'COLOMBIA', 'KM': 'COMOROS', 'CG': 'CONGO',
    'CD': 'CONGO, THE DEMOCRATIC REPUBLIC OF THE', 'CR': 'COSTA RICA',
    'CI': "COTE D'IVOIRE", 'HR': 'CROATIA', 'CU': 'CUBA', 'CY': 'CYPRUS',
    'CZ': 'CZECH REPUBLIC', 'DK': 'DENMARK', 'DJ': 'DJIBOUTI',
    'DM': 'DOMINICA', 'DO': 'DOMINICAN REPUBLIC', 'EC': 'ECUADOR',
    'EG': 'EGYPT', 'SV': 'EL SALVADOR', 'GQ': 'EQUATORIAL GUINEA',
    'ER': 'ERITREA', 'EE': 'ESTONIA', 'SZ': 'ESWATINI', 'ET': 'ETHIOPIA',
    'FJ': 'FIJI', 'FI': 'FINLAND', 'FR': 'FRANCE', 'GA': 'GABON',
    'GM': 'GAMBIA', 'GE': 'GEORGIA', 'DE': 'GERMANY', 'GH': 'GHANA',
    'GR': 'GREECE', 'GD': 'GRENADA', 'GT': 'GUATEMALA', 'GN': 'GUINEA',
    'GW': 'GUINEA-BISSAU', 'GY': 'GUYANA', 'HT': 'HAITI',
    'HN': 'HONDURAS', 'HU': 'HUNGARY', 'IS': 'ICELAND', 'IN': 'INDIA',
    'ID': 'INDONESIA', 'IR': 'IRAN, ISLAMIC REPUBLIC OF', 'IQ': 'IRAQ',
    'IE': 'IRELAND', 'IL': 'ISRAEL', 'IT': 'ITALY', 'JM': 'JAMAICA',
    'JP': 'JAPAN', 'JO': 'JORDAN', 'KZ': 'KAZAKHSTAN', 'KE': 'KENYA',
    'KI': 'KIRIBATI', 'KP': "KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF",
    'KR': 'KOREA, REPUBLIC OF', 'XK': 'KOSOVO', 'KW': 'KUWAIT',
    'KG': 'KYRGYZSTAN', 'LA': "LAO PEOPLE'S DEMOCRATIC REPUBLIC",
    'LV': 'LATVIA', 'LB': 'LEBANON', 'LS': 'LESOTHO', 'LR': 'LIBERIA',
    'LY': 'LIBYA', 'LI': 'LIECHTENSTEIN', 'LT': 'LITHUANIA',
    'LU': 'LUXEMBOURG', 'MG': 'MADAGASCAR', 'MW': 'MALAWI',
    'MY': 'MALAYSIA', 'MV': 'MALDIVES', 'ML': 'MALI', 'MT': 'MALTA',
    'MH': 'MARSHALL ISLANDS', 'MR': 'MAURITANIA', 'MU': 'MAURITIUS',
    'MX': 'MEXICO', 'FM': 'MICRONESIA, FEDERATED STATES OF',
    'MD': 'MOLDOVA, REPUBLIC OF', 'MC': 'MONACO', 'MN': 'MONGOLIA',
    'ME': 'MONTENEGRO', 'MA': 'MOROCCO', 'MZ': 'MOZAMBIQUE',
    'MM': 'MYANMAR', 'NA': 'NAMIBIA', 'NR': 'NAURU', 'NP': 'NEPAL',
    'NL': 'NETHERLANDS', 'NZ': 'NEW ZEALAND', 'NI': 'NICARAGUA',
    'NE': 'NIGER', 'NG': 'NIGERIA', 'MK': 'NORTH MACEDONIA',
    'NO': 'NORWAY', 'OM': 'OMAN', 'PK': 'PAKISTAN', 'PW': 'PALAU',
    'PA': 'PANAMA', 'PG': 'PAPUA NEW GUINEA', 'PY': 'PARAGUAY',
    'PE': 'PERU', 'PH': 'PHILIPPINES', 'PL': 'POLAND', 'PT': 'PORTUGAL',
    'QA': 'QATAR', 'RO': 'ROMANIA', 'RU': 'RUSSIAN FEDERATION',
    'RW': 'RWANDA', 'KN': 'SAINT KITTS AND NEVIS', 'LC': 'SAINT LUCIA',
    'VC': 'SAINT VINCENT AND THE GRENADINES', 'WS': 'SAMOA',
    'SM': 'SAN MARINO', 'ST': 'SAO TOME AND PRINCIPE',
    'SA': 'SAUDI ARABIA', 'SN': 'SENEGAL', 'RS': 'SERBIA',
    'SC': 'SEYCHELLES', 'SL': 'SIERRA LEONE', 'SG': 'SINGAPORE',
    'SK': 'SLOVAKIA', 'SI': 'SLOVENIA', 'SB': 'SOLOMON ISLANDS',
    'SO': 'SOMALIA', 'ZA': 'SOUTH AFRICA', 'SS': 'SOUTH SUDAN',
    'ES': 'SPAIN', 'LK': 'SRI LANKA', 'SD': 'SUDAN', 'SR': 'SURINAME',
    'SE': 'SWEDEN', 'CH': 'SWITZERLAND', 'SY': 'SYRIAN ARAB REPUBLIC',
    'TW': 'TAIWAN, PROVINCE OF CHINA', 'TJ': 'TAJIKISTAN',
    'TZ': 'TANZANIA, UNITED REPUBLIC OF', 'TH': 'THAILAND',
    'TL': 'TIMOR-LESTE', 'TG': 'TOGO', 'TO': 'TONGA',
    'TT': 'TRINIDAD AND TOBAGO', 'TN': 'TUNISIA', 'TR': 'TURKEY',
    'TM': 'TURKMENISTAN', 'TV': 'TUVALU', 'UG': 'UGANDA',
    'UA': 'UKRAINE', 'AE': 'UNITED ARAB EMIRATES',
    'GB': 'UNITED KINGDOM', 'US': 'UNITED STATES',
    'UY': 'URUGUAY', 'UZ': 'UZBEKISTAN', 'VU': 'VANUATU',
    'VA': 'HOLY SEE (VATICAN CITY STATE)', 'VE': 'VENEZUELA, BOLIVARIAN REPUBLIC OF',
    'VN': 'VIET NAM', 'YE': 'YEMEN', 'ZM': 'ZAMBIA', 'ZW': 'ZIMBABWE',
    
    # Additional common variations
    'UK': 'UNITED KINGDOM', 'USA': 'UNITED STATES', 'UAE': 'UNITED ARAB EMIRATES',
    'U.S.': 'UNITED STATES', 'U.K.': 'UNITED KINGDOM', 'U.S.A.': 'UNITED STATES',
    'U.S.A': 'UNITED STATES', 'U.S': 'UNITED STATES', 'UKRAINIAN': 'UKRAINE',
    'RUSSIAN': 'RUSSIAN FEDERATION', 'IRANIAN': 'IRAN, ISLAMIC REPUBLIC OF',
    'SYRIAN': 'SYRIAN ARAB REPUBLIC', 'CHINESE': 'CHINA', 'CUBAN': 'CUBA',
    'NORTH KOREAN': "KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF",
    'SOUTH KOREAN': 'KOREA, REPUBLIC OF', 'VIETNAMESE': 'VIET NAM',
    'BURMESE': 'MYANMAR', 'LAO': "LAO PEOPLE'S DEMOCRATIC REPUBLIC",
    'IRAQI': 'IRAQ', 'SUDANESE': 'SUDAN', 'YEMENI': 'YEMEN',
    'SOMALI': 'SOMALIA', 'LIBYAN': 'LIBYA', 'LEBANESE': 'LEBANON',
    'PALESTINIAN': 'PALESTINE, STATE OF', 'TAIWANESE': 'TAIWAN, PROVINCE OF CHINA',
    'HONG KONG': 'HONG KONG, CHINA', 'MACAU': 'MACAO, CHINA',
    'MACAO': 'MACAO, CHINA', 'BURMA': 'MYANMAR',
    
    # Special cases
    '00': 'UNKNOWN', 'XX': 'UNKNOWN', 'ZZ': 'UNKNOWN', 'N/A': 'UNKNOWN',
    'NONE': 'UNKNOWN', 'UNKNOWN': 'UNKNOWN', 'VARIOUS': 'MULTIPLE',
    'MULTIPLE': 'MULTIPLE', 'SEVERAL': 'MULTIPLE', 'VARIOUS COUNTRIES': 'MULTIPLE',
    'SEVERAL COUNTRIES': 'MULTIPLE', 'MULTIPLE COUNTRIES': 'MULTIPLE',
    'STATELESS': 'STATELESS', 'NO NATIONALITY': 'STATELESS',
    'NO CITIZENSHIP': 'STATELESS', 'UNDETERMINED': 'UNKNOWN',
    'NOT SPECIFIED': 'UNKNOWN', 'NOT KNOWN': 'UNKNOWN',
    'NOT AVAILABLE': 'UNKNOWN', 'NONE SPECIFIED': 'UNKNOWN',
    'NO NATIONALITY': 'STATELESS', 'NO CITIZENSHIP': 'STATELESS',
    'NO NATIONALITY': 'STATELESS', 'NO CITIZENSHIP': 'STATELESS',
    'NO NATIONALITY': 'STATELESS', 'NO CITIZENSHIP': 'STATELESS',
    'NO NATIONALITY': 'STATELESS', 'NO CITIZENSHIP': 'STATELESS',
    'NO NATIONALITY': 'STATELESS', 'NO CITIZENSHIP': 'STATELESS',
}

# Reverse mapping from country name to ISO code
COUNTRY_NAMES = {v.upper(): k for k, v in COUNTRY_CODES.items()}

# Add common alternative spellings and names
ALTERNATIVE_NAMES = {
    'RUSSIA': 'RUSSIAN FEDERATION',
    'IRAN': 'IRAN, ISLAMIC REPUBLIC OF',
    'SOUTH KOREA': 'KOREA, REPUBLIC OF',
    'NORTH KOREA': "KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF",
    'LAOS': "LAO PEOPLE'S DEMOCRATIC REPUBLIC",
    'BOSNIA': 'BOSNIA AND HERZEGOVINA',
    'BURMA': 'MYANMAR',
    'CZECHIA': 'CZECH REPUBLIC',
    'MACEDONIA': 'NORTH MACEDONIA',
    'PALESTINE': 'PALESTINE, STATE OF',
    'REPUBLIC OF THE CONGO': 'CONGO',
    'DEMOCRATIC REPUBLIC OF THE CONGO': 'CONGO, THE DEMOCRATIC REPUBLIC OF THE',
    'EAST TIMOR': 'TIMOR-LESTE',
    'SWAZILAND': 'ESWATINI',
    'IVORY COAST': "COTE D'IVOIRE",
    'CAPE VERDE': 'CABO VERDE',
    'VIETNAM': 'VIET NAM',
    'TAIWAN': 'TAIWAN, PROVINCE OF CHINA',
    'VATICAN': 'HOLY SEE (VATICAN CITY STATE)',
    'VATICAN CITY': 'HOLY SEE (VATICAN CITY STATE)',
    'HOLY SEE': 'HOLY SEE (VATICAN CITY STATE)',
    'UNITED STATES OF AMERICA': 'UNITED STATES',
    'USA': 'UNITED STATES',
    'US': 'UNITED STATES',
    'UK': 'UNITED KINGDOM',
    'UAE': 'UNITED ARAB EMIRATES',
    'DPRK': "KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF",
    'ROK': 'KOREA, REPUBLIC OF',
    'PRK': "KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF",
    'VENEZUELA': 'VENEZUELA, BOLIVARIAN REPUBLIC OF',
    'BOLIVIA': 'BOLIVIA, PLURINATIONAL STATE OF',
    'MOLDOVA': 'MOLDOVA, REPUBLIC OF',
    'TANZANIA': 'TANZANIA, UNITED REPUBLIC OF',
    'MICRONESIA': 'MICRONESIA, FEDERATED STATES OF',
    'FEDERATED STATES OF MICRONESIA': 'MICRONESIA, FEDERATED STATES OF',
    'ST. VINCENT AND THE GRENADINES': 'SAINT VINCENT AND THE GRENADINES',
    'ST. KITTS AND NEVIS': 'SAINT KITTS AND NEVIS',
    'ST. LUCIA': 'SAINT LUCIA',
    'ST. VINCENT & THE GRENADINES': 'SAINT VINCENT AND THE GRENADINES',
    'ST. KITTS & NEVIS': 'SAINT KITTS AND NEVIS',
    'SAO TOME': 'SAO TOME AND PRINCIPE',
    'SAO TOME & PRINCIPE': 'SAO TOME AND PRINCIPE',
    'SAINT VINCENT': 'SAINT VINCENT AND THE GRENADINES',
    'SAINT KITTS': 'SAINT KITTS AND NEVIS',
    'SAINT LUCIA': 'SAINT LUCIA',
    'SAINT VINCENT & GRENADINES': 'SAINT VINCENT AND THE GRENADINES',
    'SAINT KITTS & NEVIS': 'SAINT KITTS AND NEVIS',
    'SAINT LUCIA': 'SAINT LUCIA',
    'SVALBARD AND JAN MAYEN': 'NORWAY',
    'BRITISH VIRGIN ISLANDS': 'VIRGIN ISLANDS, BRITISH',
    'US VIRGIN ISLANDS': 'VIRGIN ISLANDS, U.S.',
    'U.S. VIRGIN ISLANDS': 'VIRGIN ISLANDS, U.S.',
    'UNITED STATES VIRGIN ISLANDS': 'VIRGIN ISLANDS, U.S.',
    'BRITISH VIRGIN ISLANDS': 'VIRGIN ISLANDS, BRITISH',
    'U.S. MINOR OUTLYING ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. OUTLYING ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES MINOR OUTLYING ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES OUTLYING ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. MINOR ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES MINOR ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. PACIFIC ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES PACIFIC ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. PACIFIC TERRITORIES': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES PACIFIC TERRITORIES': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. TERRITORIES': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES TERRITORIES': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. TERRITORY': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES TERRITORY': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES ISLANDS': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. ISLAND TERRITORIES': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES ISLAND TERRITORIES': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. ISLAND TERRITORY': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES ISLAND TERRITORY': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. PACIFIC ISLAND TERRITORIES': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES PACIFIC ISLAND TERRITORIES': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'U.S. PACIFIC ISLAND TERRITORY': 'UNITED STATES MINOR OUTLYING ISLANDS',
    'UNITED STATES PACIFIC ISLAND TERRITORY': 'UNITED STATES MINOR OUTLYING ISLANDS'
}


def split_name_parts(name: str) -> Dict[str, str]:
    """
    Split a name into first, second, third, fourth parts
    Returns dictionary with name components
    """
    if pd.isna(name) or not isinstance(name, str):
        return {"first_name": "", "second_name": "", "third_name": "", "fourth_name": ""}
    
    # Split by comma first (to handle "Lastname, Firstname" format)
    if "," in name:
        parts = name.split(",", 1)
        if len(parts) == 2:
            last_name = parts[0].strip()
            first_rest = parts[1].strip()
            first_parts = first_rest.split()
            
            # Assign parts: first part is first_name, rest goes to second_name
            first_name = first_parts[0] if first_parts else ""
            second_name = last_name
            third_name = " ".join(first_parts[1:2]) if len(first_parts) > 1 else ""
            fourth_name = " ".join(first_parts[2:]) if len(first_parts) > 2 else ""
        else:
            first_name = parts[0].strip()
            second_name = ""
            third_name = ""
            fourth_name = ""
    else:
        # No comma, split by spaces
        parts = name.split()
        first_name = parts[0] if parts else ""
        second_name = parts[1] if len(parts) > 1 else ""
        third_name = parts[2] if len(parts) > 2 else ""
        fourth_name = " ".join(parts[3:]) if len(parts) > 3 else ""
    
    return {
        "first_name": first_name,
        "second_name": second_name,
        "third_name": third_name,
        "fourth_name": fourth_name
    }


def load_sdn_data(sdn_path: Path) -> pd.DataFrame:
    """Load and process SDN (Specially Designated Nationals) data"""
    logger.info(f"Loading SDN data from {sdn_path}")
    
    if not sdn_path.exists():
        logger.warning(f"SDN file not found: {sdn_path}")
        return pd.DataFrame()
    
    try:
        # Read the file and fix line breaks first
        with open(sdn_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix line breaks - join lines that don't start with a number
        lines = content.split('\n')
        fixed_lines = []
        current_line = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # If line starts with a digit followed by comma, it's a new record
            # Pattern: number,"text"... or number,text...
            if line and line[0].isdigit() and ',' in line and line.find(',') < 10:
                if current_line:
                    fixed_lines.append(current_line)
                current_line = line
            else:
                # Continue the current record
                if current_line:
                    current_line += " " + line
                else:
                    current_line = line
        
        if current_line:
            fixed_lines.append(current_line)
        
        # Parse as CSV with proper headers
        from io import StringIO
        csv_content = '\n'.join(fixed_lines)
        
        # OFAC SDN format has 12 columns
        # Use csv module to handle quoted fields properly
        import csv
        reader = csv.reader(StringIO(csv_content))
        rows = list(reader)
        
        # Create DataFrame with proper column names (12 columns)
        df = pd.DataFrame(rows, columns=['ent_num', 'sdn_name', 'sdn_type', 'program', 'title', 'call_sign', 'vess_type', 'vess_flag', 'vess_owner', 'remarks', 'col11', 'col12'])
        
        logger.info(f"Loaded {len(df)} rows from SDN file")
        
        if df.empty:
            logger.warning("SDN file is empty")
            return pd.DataFrame()
        
        # Clean up data - replace -0- with empty string
        df = df.replace('-0-', '')
        df = df.replace('-0- ', '')
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading SDN file: {e}")
        return pd.DataFrame()


def load_alt_data(alt_path: Path) -> pd.DataFrame:
    """Load and process alternative names (aliases) data"""
    logger.info(f"Loading ALT data from {alt_path}")
    
    if not alt_path.exists():
        logger.warning(f"ALT file not found: {alt_path}")
        return pd.DataFrame()
    
    try:
        # Read the file and fix line breaks first
        with open(alt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix line breaks - join lines that don't start with a number
        lines = content.split('\n')
        fixed_lines = []
        current_line = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # If line starts with a digit followed by comma, it's a new record
            # Pattern: number,"text"... or number,text...
            if line and line[0].isdigit() and ',' in line and line.find(',') < 10:
                if current_line:
                    fixed_lines.append(current_line)
                current_line = line
            else:
                # Continue the current record
                if current_line:
                    current_line += " " + line
                else:
                    current_line = line
        
        if current_line:
            fixed_lines.append(current_line)
        
        # Parse as CSV with proper headers
        from io import StringIO
        csv_content = '\n'.join(fixed_lines)
        
        # OFAC ALT format has 5 columns
        # Use csv module to handle quoted fields properly
        import csv
        reader = csv.reader(StringIO(csv_content))
        rows = list(reader)
        
        # Create DataFrame with proper column names (5 columns)
        df = pd.DataFrame(rows, columns=['ent_num', 'alt_type', 'alt_name', 'alt_reg_date', 'col5'])
        
        logger.info(f"Loaded {len(df)} rows from ALT file")
        
        if df.empty:
            logger.warning("ALT file is empty")
            return pd.DataFrame()
        
        # Clean up data
        df = df.replace('-0-', '')
        df = df.replace('-0- ', '')
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading ALT file: {e}")
        return pd.DataFrame()


def load_add_data(add_path: Path) -> pd.DataFrame:
    """Load and process address data"""
    logger.info(f"Loading ADD data from {add_path}")
    
    if not add_path.exists():
        logger.warning(f"ADD file not found: {add_path}")
        return pd.DataFrame()
    
    try:
        # Read the file and fix line breaks first
        with open(add_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Fix line breaks - join lines that don't start with a number
        lines = content.split('\n')
        fixed_lines = []
        current_line = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # If line starts with a digit followed by comma, it's a new record
            # Pattern: number,"text"... or number,text...
            if line and line[0].isdigit() and ',' in line and line.find(',') < 10:
                if current_line:
                    fixed_lines.append(current_line)
                current_line = line
            else:
                # Continue the current record
                if current_line:
                    current_line += " " + line
                else:
                    current_line = line
        
        if current_line:
            fixed_lines.append(current_line)
        
        # Parse as CSV with proper headers
        from io import StringIO
        csv_content = '\n'.join(fixed_lines)
        
        # OFAC ADD format: ent_num, address_type, address, city_state_zip, country, add_reg_date
        # Use csv module to handle quoted fields properly
        import csv
        reader = csv.reader(StringIO(csv_content))
        rows = list(reader)
        
        # Create DataFrame with proper column names
        df = pd.DataFrame(rows, columns=['ent_num', 'address_type', 'address', 'city_state_zip', 'country', 'add_reg_date'])
        
        logger.info(f"Loaded {len(df)} rows from ADD file")
        
        if df.empty:
            logger.warning("ADD file is empty")
            return pd.DataFrame()
        
        # Clean up data
        df = df.replace('-0-', '')
        df = df.replace('-0- ', '')
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading ADD file: {e}")
        return pd.DataFrame()


def extract_nationalities(text: str) -> List[str]:
    """Extract country names and codes from text and return normalized country names."""
    if not text or not isinstance(text, str):
        return []
    
    nationalities = set()
    text_upper = text.upper()
    
    # First check for country codes
    for code, name in COUNTRY_CODES.items():
        if len(code) == 2 and f' {code} ' in f' {text_upper} ':
            nationalities.add(name)
    
    # Then check for country names and alternative names
    for name in COUNTRY_NAMES:
        if name in text_upper and len(name) > 3:  # Avoid matching short names like 'and', 'the'
            nationalities.add(name)
    
    # Check alternative names
    for alt_name, std_name in ALTERNATIVE_NAMES.items():
        if alt_name in text_upper:
            nationalities.add(std_name)
    
    # Clean up results
    cleaned = set()
    for nat in nationalities:
        # Skip common false positives
        if len(nat) <= 3 and nat not in ['USA', 'UAE', 'UK']:
            continue
        cleaned.add(nat)
    
    return sorted(cleaned)

def clean_address(address: str) -> str:
    """Clean and standardize address string."""
    if not address or not isinstance(address, str):
        return ""
    
    # Remove extra whitespace and normalize unicode
    address = ' '.join(address.split())
    address = unicodedata.normalize('NFKC', address)
    
    # Standardize common address components
    replacements = {
        r'\bSTREET\b': 'ST',
        r'\bAVENUE\b': 'AVE',
        r'\bBOULEVARD\b': 'BLVD',
        r'\bROAD\b': 'RD',
        r'\bDRIVE\b': 'DR',
        r'\bLANE\b': 'LN',
        r'\bSUITE\b': 'STE',
        r'\bAPARTMENT\b': 'APT',
        r'\bFLOOR\b': 'FL',
        r'\bUNITED STATES(?: OF AMERICA)?\b': 'USA',
        r'\bUNITED KINGDOM\b': 'UK',
        r'\bUNITED ARAB EMIRATES\b': 'UAE'
    }
    
    for pattern, repl in replacements.items():
        address = re.sub(pattern, repl, address, flags=re.IGNORECASE)
    
    return address.strip()

def create_normalized_ofac_data(sdn_df: pd.DataFrame, alt_df: pd.DataFrame, add_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create normalized OFAC sanctions data with enhanced field extraction.
    """
    logger.info("Creating normalized OFAC data")
    
    if sdn_df.empty:
        logger.error("No SDN data available")
        return pd.DataFrame()
    
    # Make a copy of the input dataframes to avoid modifying originals
    result_df = sdn_df.copy()
    
    # Clean and standardize names
    result_df['sdn_name'] = result_df['sdn_name'].str.upper().str.strip()
    name_components = result_df['sdn_name'].apply(split_name_parts)
    name_df = pd.DataFrame(name_components.tolist())
    result_df = pd.concat([result_df.reset_index(drop=True), name_df], axis=1)
    
    # Process aliases and extract additional nationalities
    nationalities = {}
    if not alt_df.empty and 'ent_num' in alt_df.columns:
        # Clean alias names
        alt_df['alt_name'] = alt_df['alt_name'].str.upper().str.strip()
        alt_df['alt_reg_date'] = alt_df['alt_reg_date'].str.upper().str.strip()
        
        # Group aliases by entity
        alias_groups = alt_df.groupby('ent_num').apply(
            lambda x: '; '.join(filter(None, set(x['alt_reg_date'].dropna())))
        )
        result_df['aliases'] = result_df['ent_num'].map(alias_groups).fillna('')
        
        # Extract nationalities from aliases
        for ent_num, group in alt_df.groupby('ent_num'):
            alias_text = ' '.join(str(x) for x in group['alt_reg_date'].dropna().values)
            nationalities[ent_num] = extract_nationalities(alias_text)
    else:
        result_df['aliases'] = ''
    
    # Process addresses and extract countries
    addresses = {}
    if not add_df.empty:
        # Clean address components
        for col in ['address', 'city_state_zip', 'country']:
            if col in add_df.columns:
                add_df[col] = add_df[col].fillna('').astype(str).str.strip()
        
        # Combine address parts
        add_df['full_address'] = (
            add_df.get('address', '') + ', ' + 
            add_df.get('city_state_zip', '') + ', ' + 
            add_df.get('country', '')
        ).str.strip(' ,')
        
        # Clean and standardize addresses
        add_df['full_address'] = add_df['full_address'].apply(clean_address)
        
        # Group addresses by entity and extract countries
        for ent_num, group in add_df.groupby('ent_num'):
            addresses[ent_num] = group['full_address'].tolist()
            
            # Extract countries from addresses
            country_text = ' '.join(str(x) for x in group['full_address'].values)
            if ent_num in nationalities:
                nationalities[ent_num].extend(extract_nationalities(country_text))
            else:
                nationalities[ent_num] = extract_nationalities(country_text)
    
    # Add addresses to result
    result_df['addresses'] = result_df['ent_num'].map(
        lambda x: '; '.join(addresses.get(x, []))
    )
    
    # Add nationalities to result
    result_df['nationalities'] = result_df['ent_num'].map(
        lambda x: '; '.join(sorted(set(nationalities.get(x, []))))
    )
    
    # Map to standard schema
    data = {
        'source': 'OFAC',
        'source_file': 'sdn.csv',
        'record_type': result_df.get('sdn_type', '').apply(
            lambda x: 'individual' if str(x).upper() == 'INDIVIDUAL' else 'entity'
        ),
        'dataid': result_df['ent_num'].astype(str),
        'reference_number': result_df['ent_num'].astype(str),
        'name': result_df['sdn_name'],
        'first_name': result_df['first_name'],
        'middle_name': result_df['second_name'],
        'last_name': result_df['third_name'],
        'aliases': result_df['aliases'],
        'nationalities': result_df['nationalities'],
        'addresses': result_df['addresses'],
        'program': result_df.get('program', '').fillna(''),
        'comments': result_df.get('remarks', '').fillna(''),
        'list_type': 'OFAC SDN List',
        'last_updated': datetime.now().strftime('%Y-%m-%d'),
        'id_numbers': '',  # Will be populated from other sources if available
        'gender': '',      # Not typically provided by OFAC
        'pob_cities': '',  # Not typically provided by OFAC
        'pob_countries': '',  # Not typically provided by OFAC
        'dob_dates': '',   # Not typically provided by OFAC
        'dob_years': ''    # Not typically provided by OFAC
    }
    
    normalized_df = pd.DataFrame(data)
    
    # Verify source column is set
    logger.info(f"Source column verification: {normalized_df['source'].value_counts().to_dict()}")
    
    # Remove duplicates
    initial_count = len(normalized_df)
    normalized_df = normalized_df.drop_duplicates()
    final_count = len(normalized_df)
    
    if initial_count != final_count:
        logger.info(f"Removed {initial_count - final_count} duplicate rows")
    
    logger.info(f"Created normalized dataset with {len(normalized_df)} records")
    
    # Verify source column is set correctly
    source_counts = normalized_df['source'].value_counts()
    logger.info(f"Source column verification: {dict(source_counts)}")
    
    return normalized_df


def ensure_directory_exists(directory: Path) -> None:
    """Ensure the specified directory exists, creating it if necessary."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Directory exists or was created: {directory}")
    except Exception as e:
        logger.error(f"Error creating directory {directory}: {e}")
        raise

def save_output(df: pd.DataFrame, output_path: Path) -> None:
    """Save the output DataFrame to a CSV file with proper formatting."""
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

def main():
    """Main function to process OFAC sanctions data."""
    logger.info("Starting OFAC sanctions conversion")
    
    # Define paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    raw_dir = project_root / "app" / "data" / "sanctions" / "raw" / "ofac"
    output_dir = project_root / "app" / "data" / "sanctions" / "normalized" / "ofac"
    
    # Ensure output directory exists
    try:
        ensure_directory_exists(output_dir)
    except Exception as e:
        logger.error(f"Failed to create output directory: {e}")
        return 1
    
    # Load data files with error handling
    sdn_path = raw_dir / "sdn.csv"
    alt_path = raw_dir / "alt.csv"
    add_path = raw_dir / "add.csv"
    
    # Check if input files exist
    for path in [sdn_path, alt_path, add_path]:
        if not path.exists():
            logger.error(f"Input file not found: {path}")
            return 1
    
    try:
        logger.info(f"Loading SDN data from {sdn_path}")
        sdn_df = load_sdn_data(sdn_path)
        if sdn_df.empty:
            logger.error("No data loaded from SDN file")
            return 1
            
        logger.info(f"Loading ALT data from {alt_path}")
        alt_df = load_alt_data(alt_path)
        
        logger.info(f"Loading ADD data from {add_path}")
        add_df = load_add_data(add_path)
    except Exception as e:
        logger.error(f"Error loading input files: {e}")
        return 1
    
    if sdn_df.empty:
        logger.error("No SDN data loaded. Cannot proceed.")
        return 1
    
    try:
        # Create normalized data
        logger.info("Creating normalized data")
        normalized_df = create_normalized_ofac_data(sdn_df, alt_df, add_df)
        
        if normalized_df.empty:
            logger.error("No data was normalized")
            return 1
        
        # Get current date for filenames and timestamps
        current_date = date.today()
        
        # Add processing timestamp
        normalized_df['processing_date'] = current_date.isoformat()
        normalized_df['last_updated'] = current_date.isoformat()
        
        # Reorder columns for better readability
        column_order = [
            'source', 'source_file', 'dataid', 'reference_number', 'list_type',
            'record_type', 'name', 'first_name', 'middle_name', 'last_name',
            'aliases', 'nationalities', 'gender', 'pob_cities', 'pob_countries',
            'dob_dates', 'dob_years', 'addresses', 'id_numbers', 'program',
            'comments', 'last_updated', 'processing_date'
        ]
        
        # Only include columns that exist in the DataFrame
        existing_columns = [col for col in column_order if col in normalized_df.columns]
        normalized_df = normalized_df[existing_columns]
        
        # Save output with date-based filename
        today = current_date.strftime('%Y%m%d')
        output_filename = f"ofac_sanctions_{today}.csv"
        output_path = output_dir / output_filename
        latest_path = output_dir / "ofac_sanctions_latest.csv"
        
        # Save the data
        save_output(normalized_df, output_path)
        
        # Create/update the latest symlink
        try:
            if latest_path.exists():
                latest_path.unlink()
            latest_path.symlink_to(output_path.name)
            logger.info(f"Created symlink: {latest_path} -> {output_path.name}")
        except OSError as e:
            logger.warning(f"Could not create symlink (this is normal on Windows): {e}")
            # On Windows or if symlink fails, just copy the file
            shutil.copy2(output_path, latest_path)
            logger.info(f"Copied to latest file: {latest_path}")
        
        # Log summary statistics
        logger.info(f"Processed {len(normalized_df)} records")
        logger.info(f"Records by type: {normalized_df['record_type'].value_counts().to_dict()}")
        
        logger.info("OFAC sanctions conversion completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        return 1
    # Summary statistics
    logger.info("="*60)
    logger.info("Conversion complete!")
    logger.info("="*60)
    logger.info(f"Input files:")
    logger.info(f"  SDN: {len(sdn_df)} records")
    logger.info(f"  ALT: {len(alt_df)} records")
    logger.info(f"  ADD: {len(add_df)} records")
    logger.info(f"Output: {len(normalized_df)} normalized records")
    logger.info(f"Output file: {output_file}")
    
    # Show sample of data
    logger.info("\nSample records:")
    for idx, row in normalized_df.head(3).iterrows():
        logger.info(f"  {row['name']} ({row['record_type']}) - Program: {row['program']}")
    
    logger.info("\nNext steps:")
    logger.info("1. Review the CSV file to ensure data looks correct")
    logger.info("2. Test with: python -c \"from app.services.sanctions_loader import SanctionsLoader; df = SanctionsLoader.load_sanctions(); ofac_records = df[df['source'] == 'OFAC']; print(f'OFAC records: {len(ofac_records)}'); print(ofac_records.head())\"")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)
