#!/usr/bin/env python3
"""
Convert raw UK sanctions data (ODS format) to normalized CSV format.

This script loads the UK sanctions ODS file and converts it to a normalized
CSV format compatible with the existing EU and OFAC sanctions data.
"""

import re
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Set, Tuple, Any
import unicodedata

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

# Country code mappings
COUNTRY_CODES = {
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
    'GW': 'GUINEA-BISSAU', 'GY': 'GUYANA', 'HT': 'HAITI', 'HN': 'HONDURAS',
    'HU': 'HUNGARY', 'IS': 'ICELAND', 'IN': 'INDIA', 'ID': 'INDONESIA',
    'IR': 'IRAN, ISLAMIC REPUBLIC OF', 'IQ': 'IRAQ', 'IE': 'IRELAND',
    'IL': 'ISRAEL', 'IT': 'ITALY', 'JM': 'JAMAICA', 'JP': 'JAPAN',
    'JO': 'JORDAN', 'KZ': 'KAZAKHSTAN', 'KE': 'KENYA', 'KI': 'KIRIBATI',
    'KP': "KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF", 'KR': 'KOREA, REPUBLIC OF',
    'XK': 'KOSOVO', 'KW': 'KUWAIT', 'KG': 'KYRGYZSTAN',
    'LA': "LAO PEOPLE'S DEMOCRATIC REPUBLIC", 'LV': 'LATVIA',
    'LB': 'LEBANON', 'LS': 'LESOTHO', 'LR': 'LIBERIA', 'LY': 'LIBYA',
    'LI': 'LIECHTENSTEIN', 'LT': 'LITHUANIA', 'LU': 'LUXEMBOURG',
    'MG': 'MADAGASCAR', 'MW': 'MALAWI', 'MY': 'MALAYSIA', 'MV': 'MALDIVES',
    'ML': 'MALI', 'MT': 'MALTA', 'MH': 'MARSHALL ISLANDS', 'MR': 'MAURITANIA',
    'MU': 'MAURITIUS', 'MX': 'MEXICO', 'FM': 'MICRONESIA, FEDERATED STATES OF',
    'MD': 'MOLDOVA, REPUBLIC OF', 'MC': 'MONACO', 'MN': 'MONGOLIA',
    'ME': 'MONTENEGRO', 'MA': 'MOROCCO', 'MZ': 'MOZAMBIQUE', 'MM': 'MYANMAR',
    'NA': 'NAMIBIA', 'NR': 'NAURU', 'NP': 'NEPAL', 'NL': 'NETHERLANDS',
    'NZ': 'NEW ZEALAND', 'NI': 'NICARAGUA', 'NE': 'NIGER', 'NG': 'NIGERIA',
    'MK': 'NORTH MACEDONIA', 'NO': 'NORWAY', 'OM': 'OMAN', 'PK': 'PAKISTAN',
    'PW': 'PALAU', 'PS': 'PALESTINE, STATE OF', 'PA': 'PANAMA',
    'PG': 'PAPUA NEW GUINEA', 'PY': 'PARAGUAY', 'PE': 'PERU',
    'PH': 'PHILIPPINES', 'PL': 'POLAND', 'PT': 'PORTUGAL', 'QA': 'QATAR',
    'RO': 'ROMANIA', 'RU': 'RUSSIAN FEDERATION', 'RW': 'RWANDA',
    'KN': 'SAINT KITTS AND NEVIS', 'LC': 'SAINT LUCIA',
    'VC': 'SAINT VINCENT AND THE GRENADINES', 'WS': 'SAMOA',
    'SM': 'SAN MARINO', 'ST': 'SAO TOME AND PRINCIPE', 'SA': 'SAUDI ARABIA',
    'SN': 'SENEGAL', 'RS': 'SERBIA', 'SC': 'SEYCHELLES', 'SL': 'SIERRA LEONE',
    'SG': 'SINGAPORE', 'SK': 'SLOVAKIA', 'SI': 'SLOVENIA',
    'SB': 'SOLOMON ISLANDS', 'SO': 'SOMALIA', 'ZA': 'SOUTH AFRICA',
    'SS': 'SOUTH SUDAN', 'ES': 'SPAIN', 'LK': 'SRI LANKA', 'SD': 'SUDAN',
    'SR': 'SURINAME', 'SE': 'SWEDEN', 'CH': 'SWITZERLAND',
    'SY': 'SYRIAN ARAB REPUBLIC', 'TW': 'TAIWAN, PROVINCE OF CHINA',
    'TJ': 'TAJIKISTAN', 'TZ': 'TANZANIA, UNITED REPUBLIC OF', 'TH': 'THAILAND',
    'TL': 'TIMOR-LESTE', 'TG': 'TOGO', 'TO': 'TONGA', 'TT': 'TRINIDAD AND TOBAGO',
    'TN': 'TUNISIA', 'TR': 'TURKEY', 'TM': 'TURKMENISTAN', 'TV': 'TUVALU',
    'UG': 'UGANDA', 'UA': 'UKRAINE', 'AE': 'UNITED ARAB EMIRATES',
    'GB': 'UNITED KINGDOM', 'US': 'UNITED STATES',
    'UY': 'URUGUAY', 'UZ': 'UZBEKISTAN', 'VU': 'VANUATU',
    'VA': 'HOLY SEE (VATICAN CITY STATE)', 'VE': 'VENEZUELA, BOLIVARIAN REPUBLIC OF',
    'VN': 'VIET NAM', 'YE': 'YEMEN', 'ZM': 'ZAMBIA', 'ZW': 'ZIMBABWE',
    'XK': 'KOSOVO'
}

# Alternative country names
ALTERNATIVE_NAMES = {
    'UK': 'UNITED KINGDOM', 'USA': 'UNITED STATES', 'UAE': 'UNITED ARAB EMIRATES',
    'U.S.': 'UNITED STATES', 'U.S.A.': 'UNITED STATES', 'U.K.': 'UNITED KINGDOM',
    'SOUTH KOREA': 'KOREA, REPUBLIC OF', 'NORTH KOREA': "KOREA, DEMOCRATIC PEOPLE'S REPUBLIC OF",
    'RUSSIA': 'RUSSIAN FEDERATION', 'PALESTINIAN': 'PALESTINE, STATE OF',
    'TAIWANESE': 'TAIWAN, PROVINCE OF CHINA', 'HONG KONG': 'HONG KONG, CHINA',
    'MACAU': 'MACAO, CHINA', 'MACAO': 'MACAO, CHINA', 'BURMA': 'MYANMAR',
    'VIETNAM': 'VIET NAM', 'BOSNIA': 'BOSNIA AND HERZEGOVINA',
    'IVORY COAST': "COTE D'IVOIRE", 'EAST TIMOR': 'TIMOR-LESTE',
    'SWAZILAND': 'ESWATINI', 'CZECHIA': 'CZECH REPUBLIC',
    'SLOVAK REPUBLIC': 'SLOVAKIA', 'MACEDONIA': 'NORTH MACEDONIA',
    'REPUBLIC OF MOLDOVA': 'MOLDOVA, REPUBLIC OF',
    'DEMOCRATIC REPUBLIC OF THE CONGO': 'CONGO, THE DEMOCRATIC REPUBLIC OF THE',
    'REPUBLIC OF THE CONGO': 'CONGO', 'VATICAN': 'HOLY SEE (VATICAN CITY STATE)'
}

# Reverse mapping from country name to ISO code
COUNTRY_NAMES = {v.upper(): k for k, v in COUNTRY_CODES.items()}

# Add alternative names to the main mapping
for alt_name, std_name in ALTERNATIVE_NAMES.items():
    if std_name.upper() in COUNTRY_NAMES:
        COUNTRY_NAMES[alt_name.upper()] = COUNTRY_NAMES[std_name.upper()]

def load_uk_data():
    """Load UK sanctions data from ODS file."""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    raw_dir = project_root / 'app' / 'data' / 'sanctions' / 'raw' / 'uk'
    
    uk_file = raw_dir / 'FCDO_SL_Wed_Nov 19 2025.ods'
    
    if not uk_file.exists():
        logger.error(f"UK file not found: {uk_file}")
        return pd.DataFrame()
    
    try:
        logger.info(f"Loading UK data from {uk_file}")
        df = pd.read_excel(uk_file, engine='odf')
        
        # Clean column names (strip whitespace)
        df.columns = df.columns.str.strip()
        
        logger.info(f"Loaded {len(df)} rows from UK file")
        logger.info(f"Columns: {list(df.columns)}")
        
        return df
    except Exception as e:
        logger.error(f"Error loading UK file: {e}")
        return pd.DataFrame()

def clean_text(text: str) -> str:
    """Clean and normalize text by removing extra whitespace and normalizing unicode."""
    if pd.isna(text) or not text:
        return ''
    
    # Convert to string and normalize unicode
    text = str(text)
    text = unicodedata.normalize('NFKC', text)
    
    # Remove extra whitespace and newlines
    text = ' '.join(text.split())
    
    return text.strip()

def parse_name(full_name: str) -> Dict[str, str]:
    """Parse a full name into components (first, middle, last, etc.)."""
    if not full_name or pd.isna(full_name):
        return {
            'name': '',
            'first_name': '',
            'middle_name': '',
            'last_name': ''
        }
    
    # Clean and normalize the name
    name = clean_text(full_name).upper()
    
    # Common suffixes and titles to remove
    suffixes = ['JR', 'SR', 'II', 'III', 'IV', 'V']
    titles = ['MR', 'MRS', 'MS', 'MISS', 'DR', 'PROF', 'SIR', 'LADY', 'LORD', 'CAPT', 'COL', 'MAJ', 'GEN', 'REV', 'FR']
    
    # Split into parts and remove empty strings
    parts = [p for p in re.split(r'[\s,.-]+', name) if p]
    
    # Remove suffixes and titles
    parts = [p for p in parts if p not in suffixes and p not in titles]
    
    # Reconstruct the name without titles/suffixes
    clean_name = ' '.join(parts)
    
    # Simple approach: first part is first name, last part is last name, rest is middle
    first_name = parts[0] if len(parts) > 0 else ''
    last_name = parts[-1] if len(parts) > 1 else first_name
    middle_name = ' '.join(parts[1:-1]) if len(parts) > 2 else ''
    
    return {
        'name': clean_name,
        'first_name': first_name,
        'middle_name': middle_name,
        'last_name': last_name
    }

def extract_nationalities(text: str) -> List[str]:
    """Extract country names from text and return as a list of country names."""
    if not text or pd.isna(text):
        return []
    
    text = clean_text(text).upper()
    found_countries = set()
    
    # Check for country names in the text
    for country in COUNTRY_NAMES.keys():
        # Use word boundaries to avoid partial matches
        if re.search(r'\b' + re.escape(country) + r'\b', text):
            found_countries.add(country)
    
    # Check for alternative names
    for alt_name, std_name in ALTERNATIVE_NAMES.items():
        if re.search(r'\b' + re.escape(alt_name.upper()) + r'\b', text):
            found_countries.add(std_name.upper())
    
    # Convert to list and sort for consistency
    return sorted(list(found_countries)) if found_countries else []

def clean_address(address: str) -> str:
    """Clean and normalize an address string."""
    if not address or pd.isna(address):
        return ''
    
    # Basic cleaning
    address = clean_text(address)
    
    # Remove multiple spaces and normalize commas
    address = re.sub(r'\s+', ' ', address)
    address = re.sub(r'\s*,\s*', ', ', address)
    
    # Standardize common address components
    replacements = {
        r'\bSTREET\b': 'ST',
        r'\bAVENUE\b': 'AVE',
        r'\bBOULEVARD\b': 'BLVD',
        r'\bROAD\b': 'RD',
        r'\bDRIVE\b': 'DR',
        r'\bLANE\b': 'LN',
        r'\bCOURT\b': 'CT',
        r'\bPLACE\b': 'PL',
        r'\bSQUARE\b': 'SQ',
        r'\bAPARTMENT\b': 'APT',
        r'\bAPPT\b': 'APT',
        r'\bBUILDING\b': 'BLDG',
        r'\bFLOOR\b': 'FL',
        r'\bSUITE\b': 'STE',
        r'\bNUMBER\b': 'NO',
        r'\bNORTH\b': 'N',
        r'\bSOUTH\b': 'S',
        r'\bEAST\b': 'E',
        r'\bWEST\b': 'W'
    }
    
    for pattern, replacement in replacements.items():
        address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)
    
    return address.strip()

def create_normalized_uk_data(uk_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create normalized UK sanctions data from the raw UK DataFrame.
    
    Args:
        uk_df: Raw DataFrame containing UK sanctions data
        
    Returns:
        pd.DataFrame: Normalized sanctions data in standard format
    """
    if uk_df.empty:
        logger.error("No UK data to process")
        return pd.DataFrame()
    
    logger.info(f"Creating normalized UK data with {len(uk_df)} records")
    
    # Clean up column names and data
    uk_df.columns = [col.strip() for col in uk_df.columns]
    uk_df = uk_df.fillna('')
    
    # Initialize the result list
    normalized_records = []
    
    # Process each record
    for _, row in uk_df.iterrows():
        try:
            # Basic record info
            record = {
                'source': 'UK',
                'source_file': 'FCDO_SL_Wed_Nov_19_2025.ods',
                'list_type': 'UK Sanctions List',
                'dataid': str(row.get('Unique ID', '')).strip(),
                'reference_number': str(row.get('OFSI Group ID', '')).strip() or str(row.get('Unique ID', '')).strip(),
                'program': clean_text(row.get('Regime Name', '')),
                'comments': clean_text(row.get('Sanctions Imposed', '')),
                'last_updated': date.today().isoformat(),
                'processing_date': date.today().isoformat()
            }
            
            # Determine record type
            record_type = str(row.get('Type', '')).strip().upper()
            if 'INDIVIDUAL' in record_type:
                record['record_type'] = 'individual'
            elif 'ENTITY' in record_type or 'ORGANIZATION' in record_type:
                record['record_type'] = 'entity'
            elif 'VESSEL' in record_type or 'SHIP' in record_type or 'BOAT' in record_type:
                record['record_type'] = 'vessel'
            else:
                record['record_type'] = 'other'
            
            # Process name
            full_name = clean_text(row.get('Name', ''))
            name_parts = parse_name(full_name)
            
            record.update({
                'name': name_parts['name'],
                'first_name': name_parts['first_name'],
                'middle_name': name_parts['middle_name'],
                'last_name': name_parts['last_name']
            })
            
            # Extract nationalities from name and regime name
            text_fields = [
                full_name,
                row.get('Regime Name', ''),
                row.get('Designation Source', '')
            ]
            
            nationalities = set()
            for field in text_fields:
                nationalities.update(extract_nationalities(field))
            
            record['nationalities'] = '; '.join(sorted(nationalities)) if nationalities else ''
            
            # Initialize other fields
            record.update({
                'aliases': '',  # UK data doesn't have separate aliases
                'gender': '',   # UK doesn't provide gender
                'pob_cities': '',
                'pob_countries': '',
                'dob_dates': '',
                'dob_years': '',
                'addresses': '',
                'id_numbers': ''
            })
            
            # Add to results
            normalized_records.append(record)
            
        except Exception as e:
            logger.error(f"Error processing record {row.get('Unique ID', 'unknown')}: {str(e)}")
            continue
    
    # Create DataFrame from normalized records
    if not normalized_records:
        logger.error("No valid records were processed")
        return pd.DataFrame()
    
    normalized_df = pd.DataFrame(normalized_records)
    
    # Reorder columns to match other sanctions lists
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
    
    logger.info(f"Created normalized dataset with {len(normalized_df)} records")
    
    # Log record type distribution
    if 'record_type' in normalized_df.columns:
        type_counts = normalized_df['record_type'].value_counts().to_dict()
        logger.info(f"Record type distribution: {type_counts}")
    
    return normalized_df

def save_output(df: pd.DataFrame, output_path: Path) -> None:
    """
    Save the normalized data to a CSV file with proper formatting.
    
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

def main():
    """Main conversion function."""
    start_time = datetime.now()
    logger.info("\n" + "="*60)
    logger.info("Starting UK sanctions conversion")
    logger.info("="*60)
    
    try:
        # Load UK data
        uk_df = load_uk_data()
        
        if uk_df.empty:
            logger.error("No UK data loaded. Cannot proceed.")
            return 1
        
        # Create normalized data
        logger.info("Creating normalized data...")
        normalized_df = create_normalized_uk_data(uk_df)
        
        if normalized_df.empty:
            logger.error("Failed to create normalized data")
            return 1
        
        # Set up output paths
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        output_dir = project_root / 'app' / 'data' / 'sanctions' / 'normalized' / 'uk'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create date-based filename
        today = date.today().strftime('%Y%m%d')
        output_filename = f"uk_sanctions_{today}.csv"
        output_path = output_dir / output_filename
        latest_path = output_dir / "uk_sanctions_latest.csv"
        
        # Save the data
        save_output(normalized_df, output_path)
        
        # Create/update the latest symlink
        try:
            if latest_path.exists():
                latest_path.unlink()
            latest_path.symlink_to(output_path.name)
            logger.info(f"Created symlink: {latest_path} -> {output_path.name}")
        except OSError as e:
            logger.warning(f"Could not create symlink: {e}")
        
        # Log completion
        duration = (datetime.now() - start_time).total_seconds()
        logger.info("\n" + "="*60)
        logger.info("Conversion complete!")
        logger.info("="*60)
        logger.info(f"Input file: FCDO_SL_Wed_Nov_19_2025.ods")
        logger.info(f"Output: {len(normalized_df)} normalized records")
        logger.info(f"Output file: {output_path}")
        logger.info(f"Processing time: {duration:.2f} seconds")
        
        # Show record type distribution
        if 'record_type' in normalized_df.columns:
            type_counts = normalized_df['record_type'].value_counts().to_dict()
            logger.info("\nRecord type distribution:")
            for rec_type, count in type_counts.items():
                logger.info(f"  {rec_type}: {count} records")
        
        # Show sample records
        logger.info("\nSample records:")
        for _, row in normalized_df.head(3).iterrows():
            logger.info(f"\n  Name: {row.get('name', 'N/A')}")
            logger.info(f"  Type: {row.get('record_type', 'N/A')}")
            logger.info(f"  Nationalities: {row.get('nationalities', 'N/A')}")
            logger.info(f"  Program: {row.get('program', 'N/A')}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    main()
