#!/usr/bin/env python3
"""
Convert raw EU sanctions data (CSV format) to normalized CSV format.

This script loads the EU sanctions CSV file and converts it to a normalized
CSV format compatible with the existing sanctions data.
"""

import pandas as pd
from pathlib import Path
import logging
from datetime import datetime
import re
from typing import Dict, List, Set, Optional, Any, Union
import unicodedata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Country code to name mapping
COUNTRY_CODES = {
    'AF': 'Afghanistan', 'AL': 'Albania', 'DZ': 'Algeria', 'AD': 'Andorra',
    'AO': 'Angola', 'AG': 'Antigua and Barbuda', 'AR': 'Argentina',
    'AM': 'Armenia', 'AU': 'Australia', 'AT': 'Austria', 'AZ': 'Azerbaijan',
    'BS': 'Bahamas', 'BH': 'Bahrain', 'BD': 'Bangladesh', 'BB': 'Barbados',
    'BY': 'Belarus', 'BE': 'Belgium', 'BZ': 'Belize', 'BJ': 'Benin',
    'BT': 'Bhutan', 'BO': 'Bolivia', 'BA': 'Bosnia and Herzegovina',
    'BW': 'Botswana', 'BR': 'Brazil', 'BN': 'Brunei Darussalam',
    'BG': 'Bulgaria', 'BF': 'Burkina Faso', 'BI': 'Burundi',
    'CV': 'Cabo Verde', 'KH': 'Cambodia', 'CM': 'Cameroon',
    'CA': 'Canada', 'CF': 'Central African Republic', 'TD': 'Chad',
    'CL': 'Chile', 'CN': 'China', 'CO': 'Colombia', 'KM': 'Comoros',
    'CG': 'Congo', 'CD': 'Democratic Republic of the Congo',
    'CR': 'Costa Rica', 'CI': "Côte d'Ivoire", 'HR': 'Croatia',
    'CU': 'Cuba', 'CY': 'Cyprus', 'CZ': 'Czech Republic', 'DK': 'Denmark',
    'DJ': 'Djibouti', 'DM': 'Dominica', 'DO': 'Dominican Republic',
    'EC': 'Ecuador', 'EG': 'Egypt', 'SV': 'El Salvador',
    'GQ': 'Equatorial Guinea', 'ER': 'Eritrea', 'EE': 'Estonia',
    'SZ': 'Eswatini', 'ET': 'Ethiopia', 'FJ': 'Fiji', 'FI': 'Finland',
    'FR': 'France', 'GA': 'Gabon', 'GM': 'Gambia', 'GE': 'Georgia',
    'DE': 'Germany', 'GH': 'Ghana', 'GR': 'Greece', 'GD': 'Grenada',
    'GT': 'Guatemala', 'GN': 'Guinea', 'GW': 'Guinea-Bissau',
    'GY': 'Guyana', 'HT': 'Haiti', 'HN': 'Honduras', 'HU': 'Hungary',
    'IS': 'Iceland', 'IN': 'India', 'ID': 'Indonesia', 'IR': 'Iran',
    'IQ': 'Iraq', 'IE': 'Ireland', 'IL': 'Israel', 'IT': 'Italy',
    'JM': 'Jamaica', 'JP': 'Japan', 'JO': 'Jordan', 'KZ': 'Kazakhstan',
    'KE': 'Kenya', 'KI': 'Kiribati', 'KP': "Korea (Democratic People's Republic of)",
    'KR': 'Korea, Republic of', 'KW': 'Kuwait', 'KG': 'Kyrgyzstan',
    'LA': "Lao People's Democratic Republic", 'LV': 'Latvia',
    'LB': 'Lebanon', 'LS': 'Lesotho', 'LR': 'Liberia', 'LY': 'Libya',
    'LI': 'Liechtenstein', 'LT': 'Lithuania', 'LU': 'Luxembourg',
    'MG': 'Madagascar', 'MW': 'Malawi', 'MY': 'Malaysia',
    'MV': 'Maldives', 'ML': 'Mali', 'MT': 'Malta',
    'MH': 'Marshall Islands', 'MR': 'Mauritania', 'MU': 'Mauritius',
    'MX': 'Mexico', 'FM': 'Micronesia (Federated States of)',
    'MC': 'Monaco', 'MN': 'Mongolia', 'ME': 'Montenegro',
    'MA': 'Morocco', 'MZ': 'Mozambique', 'MM': 'Myanmar',
    'NA': 'Namibia', 'NR': 'Nauru', 'NP': 'Nepal', 'NL': 'Netherlands',
    'NZ': 'New Zealand', 'NI': 'Nicaragua', 'NE': 'Niger',
    'NG': 'Nigeria', 'MK': 'North Macedonia', 'NO': 'Norway',
    'OM': 'Oman', 'PK': 'Pakistan', 'PW': 'Palau', 'PA': 'Panama',
    'PG': 'Papua New Guinea', 'PY': 'Paraguay', 'PE': 'Peru',
    'PH': 'Philippines', 'PL': 'Poland', 'PT': 'Portugal',
    'QA': 'Qatar', 'RO': 'Romania', 'RU': 'Russian Federation',
    'RW': 'Rwanda', 'KN': 'Saint Kitts and Nevis', 'LC': 'Saint Lucia',
    'VC': 'Saint Vincent and the Grenadines', 'WS': 'Samoa',
    'SM': 'San Marino', 'ST': 'Sao Tome and Principe',
    'SA': 'Saudi Arabia', 'SN': 'Senegal', 'RS': 'Serbia',
    'SC': 'Seychelles', 'SL': 'Sierra Leone', 'SG': 'Singapore',
    'SK': 'Slovakia', 'SI': 'Slovenia', 'SB': 'Solomon Islands',
    'SO': 'Somalia', 'ZA': 'South Africa', 'SS': 'South Sudan',
    'ES': 'Spain', 'LK': 'Sri Lanka', 'SD': 'Sudan', 'SR': 'Suriname',
    'SE': 'Sweden', 'CH': 'Switzerland', 'SY': 'Syrian Arab Republic',
    'TJ': 'Tajikistan', 'TZ': 'Tanzania, United Republic of',
    'TH': 'Thailand', 'TL': 'Timor-Leste', 'TG': 'Togo', 'TO': 'Tonga',
    'TT': 'Trinidad and Tobago', 'TN': 'Tunisia', 'TR': 'Türkiye',
    'TM': 'Turkmenistan', 'TV': 'Tuvalu', 'UG': 'Uganda',
    'UA': 'Ukraine', 'AE': 'United Arab Emirates',
    'GB': 'United Kingdom of Great Britain and Northern Ireland',
    'US': 'United States of America', 'UY': 'Uruguay',
    'UZ': 'Uzbekistan', 'VU': 'Vanuatu', 'VA': 'Holy See',
    'VE': 'Venezuela (Bolivarian Republic of)', 'VN': 'Viet Nam',
    'YE': 'Yemen', 'ZM': 'Zambia', 'ZW': 'Zimbabwe',
    'TW': 'Taiwan, Province of China', 'HK': 'Hong Kong',
    'MO': 'Macao', 'PS': 'Palestine, State of', 'XK': 'Kosovo'
}

def load_eu_data() -> pd.DataFrame:
    """
    Load EU sanctions data from CSV file.
    
    Returns:
        DataFrame containing the raw EU sanctions data
    """
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    raw_dir = project_root / 'app' / 'data' / 'sanctions' / 'raw' / 'eu'
    
    # Find the latest EU sanctions file (in case the name changes)
    eu_files = list(raw_dir.glob('*FULL*.csv'))
    if not eu_files:
        logger.error(f"No EU sanctions files found in {raw_dir}")
        return pd.DataFrame()
    
    # Sort by modification time to get the most recent file
    eu_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    eu_file = eu_files[0]
    
    logger.info(f"Loading EU data from {eu_file}")
    
    try:
        # Read the file with proper encoding and handle potential issues
        df = pd.read_csv(
            eu_file, 
            sep=';', 
            encoding='utf-8-sig',  # Handle BOM if present
            dtype=str,
            on_bad_lines='warn',  # Log bad lines but continue
            low_memory=False  # Avoid mixed type warnings
        )
        
        # Clean column names (remove BOM if present and strip whitespace)
        df.columns = [col.strip('\ufeff').strip() for col in df.columns]
        
        # Log basic info about the loaded data
        logger.info(f"Loaded {len(df)} rows with {len(df.columns)} columns")
        logger.info(f"Columns: {', '.join(df.columns[:10])}...")
        
        # Convert date columns to datetime with proper format
        date_columns = [
            'fileGenerationDate', 
            'Entity_DesignationDate',
            'NameAlias_Regulation_PublicationDate', 
            'BirthDate_BirthDate',
            'Entity_Regulation_PublicationDate',
            'Entity_Regulation_EntryIntoForceDate'
        ]
        
        for col in date_columns:
            if col in df.columns:
                try:
                    # First ensure it's a string, then convert to datetime
                    df[col] = pd.to_datetime(
                        df[col].astype(str), 
                        dayfirst=True, 
                        errors='coerce',
                        format='mixed'  # Try multiple formats
                    )
                    logger.debug(f"Converted {col} to datetime")
                except Exception as e:
                    logger.warning(f"Error converting {col} to datetime: {str(e)}")
        
        # Log sample data for verification
        logger.info("Sample data (first row):")
        for col in df.columns:
            if col in date_columns and col in df.columns:
                logger.info(f"  {col}: {df[col].iloc[0]} (type: {type(df[col].iloc[0])})")
        
        return df
    
    except Exception as e:
        logger.error(f"Error loading EU file {eu_file}: {str(e)}", exc_info=True)
        return pd.DataFrame()

def clean_name(name: str) -> str:
    """
    Clean and normalize name strings.
    
    Args:
        name: The name string to clean
        
    Returns:
        Cleaned and normalized name string
    """
    if pd.isna(name) or not str(name).strip():
        return ''
    
    # Convert to string and normalize unicode
    name = str(name).strip()
    name = unicodedata.normalize('NFKC', name)
    
    # Replace multiple spaces with single space
    name = re.sub(r'\s+', ' ', name)
    
    # Remove control characters
    name = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', name)
    
    # Standardize quotes and apostrophes
    name = name.replace('‘', "'").replace('’', "'")
    name = name.replace('“', '"').replace('”', '"')
    
    # Remove any remaining non-printable characters
    name = ''.join(char for char in name if char.isprintable() or char.isspace())
    
    return name.strip()


def get_country_name(country_code: Optional[str]) -> str:
    """
    Convert country code to full country name.
    
    Args:
        country_code: 2-letter ISO country code
        
    Returns:
        Full country name or original code if not found
    """
    if not country_code or pd.isna(country_code) or not isinstance(country_code, str):
        return ''
    
    country_code = country_code.upper().strip()
    return COUNTRY_CODES.get(country_code, country_code)


def parse_date(date_str: Optional[Any]) -> Optional[str]:
    """
    Parse date string into YYYY-MM-DD format.
    
    Args:
        date_str: Date string or pandas Timestamp
        
    Returns:
        Formatted date string or empty string if invalid
    """
    if pd.isna(date_str) or not date_str:
        return ''
    
    try:
        if isinstance(date_str, (pd.Timestamp, datetime)):
            return date_str.strftime('%Y-%m-%d')
            
        # Convert to string and clean
        date_str = str(date_str).strip()
        
        # Handle common date formats
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d', 
                   '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                continue
                
        # Try to extract just the date part if it's a datetime string
        match = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', date_str)
        if match:
            return parse_date(match.group(1))
            
        # Try to extract just the year
        year_match = re.search(r'(\d{4})', date_str)
        if year_match:
            return f"{year_match.group(1)}-01-01"
            
        return ''
    except Exception as e:
        logger.warning(f"Error parsing date '{date_str}': {str(e)}")
        return ''


def extract_nationalities(row: pd.Series) -> Set[str]:
    """
    Extract nationalities from various possible fields.
    
    Args:
        row: DataFrame row containing nationality-related fields
        
    Returns:
        Set of unique nationalities
    """
    nationalities = set()
    
    # Check all possible nationality fields
    nat_fields = [
        'Citizenship_CountryDescription',
        'BirthDate_CountryDescription',
        'Address_CountryDescription',
        'Citizenship_CountryIso2Code',
        'BirthDate_CountryIso2Code',
        'Address_CountryIso2Code'
    ]
    
    for field in nat_fields:
        if field in row and pd.notna(row[field]) and str(row[field]).strip():
            value = str(row[field]).strip()
            # If it's a country code, convert to full name
            if field.endswith('Iso2Code'):
                country_name = get_country_name(value)
                if country_name:
                    nationalities.add(country_name)
            else:
                nationalities.add(value)
    
    return nationalities


def extract_addresses(row: pd.Series) -> str:
    """
    Extract and format address information.
    
    Args:
        row: DataFrame row containing address fields
        
    Returns:
        Semicolon-separated string of addresses
    """
    address_parts = []
    
    # Street address
    street = row.get('Address_Street')
    if pd.notna(street) and str(street).strip():
        address_parts.append(str(street).strip())
    
    # City
    city = row.get('Address_City')
    if pd.notna(city) and str(city).strip():
        address_parts.append(str(city).strip())
    
    # Region/State
    region = row.get('Address_Region')
    if pd.notna(region) and str(region).strip():
        address_parts.append(str(region).strip())
    
    # Postal code
    zip_code = row.get('Address_ZipCode')
    if pd.notna(zip_code) and str(zip_code).strip():
        address_parts.append(str(zip_code).strip())
    
    # Country
    country = row.get('Address_CountryDescription')
    if pd.notna(country) and str(country).strip():
        address_parts.append(str(country).strip())
    
    # If no address parts, try to use place
    if not address_parts:
        place = row.get('Address_Place')
        if pd.notna(place) and str(place).strip():
            address_parts.append(str(place).strip())
    
    return ', '.join(address_parts) if address_parts else ''


def extract_identification(row: pd.Series) -> str:
    """
    Extract and format identification documents.
    
    Args:
        row: DataFrame row containing ID fields
        
    Returns:
        Semicolon-separated string of ID documents
    """
    id_parts = []
    
    # Check if we have any ID information
    if pd.notna(row.get('Identification_Number')) and str(row['Identification_Number']).strip():
        id_type = clean_name(row.get('Identification_TypeDescription', 'ID'))
        id_number = str(row['Identification_Number']).strip()
        
        # Add issuing country if available
        country = ''
        if pd.notna(row.get('Identification_CountryDescription')):
            country = f" ({row['Identification_CountryDescription']})"
        elif pd.notna(row.get('Identification_CountryIso2Code')):
            country = f" ({get_country_name(row['Identification_CountryIso2Code'])})"
        
        id_parts.append(f"{id_type}: {id_number}{country}")
    
    return '; '.join(id_parts)

def create_normalized_eu_data(eu_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create normalized EU sanctions data from the raw EU DataFrame.
    
    Args:
        eu_df: Raw EU sanctions DataFrame
        
    Returns:
        Normalized DataFrame with standardized schema
    """
    if eu_df.empty:
        logger.error("No EU data to process")
        return pd.DataFrame()
    
    logger.info("Creating normalized EU data")
    
    # Create a copy to avoid SettingWithCopyWarning
    df = eu_df.copy()
    
    # Clean up the data
    df['Entity_SubjectType'] = df['Entity_SubjectType'].fillna('').astype(str).str.strip()
    
    # Map EU subject types to our record types
    subject_type_map = {
        'P': 'individual',
        'person': 'individual',
        'E': 'entity',
        'entity': 'entity',
        'G': 'government',
        'government': 'government',
        'T': 'vessel',
        'vessel': 'vessel',
        'O': 'organization',
        'organization': 'organization',
        '': 'other'  # Default for unknown types
    }
    
    # Initialize lists to store normalized records
    records = []
    
    # Group by entity to aggregate all aliases and other info
    entity_groups = df.groupby('Entity_LogicalId')
    
    logger.info(f"Processing {len(entity_groups)} unique entities")
    
    for entity_id, group in entity_groups:
        # Get the first row for entity-level information
        first_row = group.iloc[0]
        
        # Determine record type
        record_type = subject_type_map.get(
            first_row.get('Entity_SubjectType', '').strip().lower(), 
            'entity'  # Default to 'entity' if type not found
        )
        
        # Extract primary name
        primary_name = clean_name(first_row.get('NameAlias_WholeName', ''))
        if not primary_name:
            # Try to construct name from parts
            name_parts = [
                clean_name(first_row.get('NameAlias_FirstName', '')),
                clean_name(first_row.get('NameAlias_MiddleName', '')),
                clean_name(first_row.get('NameAlias_LastName', ''))
            ]
            primary_name = ' '.join(filter(None, name_parts)).strip()
        
        # Extract name components if not already available
        first_name = clean_name(first_row.get('NameAlias_FirstName', ''))
        last_name = clean_name(first_row.get('NameAlias_LastName', ''))
        middle_name = clean_name(first_row.get('NameAlias_MiddleName', ''))
        
        # If we have a full name but missing components, try to split
        if primary_name and not (first_name and last_name):
            name_parts = primary_name.split()
            if not first_name and name_parts:
                first_name = name_parts[0]
            if not last_name and len(name_parts) > 1:
                last_name = ' '.join(name_parts[1:])
        
        # Collect all name aliases and alternative names
        aliases = set()
        for _, row in group.iterrows():
            # Check whole name aliases
            alias = clean_name(row.get('NameAlias_WholeName', ''))
            if alias and alias != primary_name:
                aliases.add(alias)
            
            # Check name parts
            for part in ['FirstName', 'MiddleName', 'LastName']:
                part_alias = clean_name(row.get(f'NameAlias_{part}', ''))
                if part_alias and part_alias not in [first_name, middle_name, last_name]:
                    aliases.add(part_alias)
        
        # Extract program/regulation information
        program = clean_name(first_row.get('Entity_Regulation_Programme', ''))
        if not program:
            program = clean_name(first_row.get('NameAlias_Regulation_Programme', ''))
        
        # Extract addresses
        addresses = set()
        for _, row in group.iterrows():
            address = extract_addresses(row)
            if address:
                addresses.add(address)
        
        # Extract identification documents
        id_numbers = set()
        for _, row in group.iterrows():
            id_info = extract_identification(row)
            if id_info:
                id_numbers.add(id_info)
        
        # Extract nationalities from all possible fields
        nationalities = set()
        for _, row in group.iterrows():
            nat = extract_nationalities(row)
            nationalities.update(nat)
        
        # Extract date of birth information
        dob = ''
        if pd.notna(first_row.get('BirthDate_BirthDate')):
            dob = parse_date(first_row['BirthDate_BirthDate'])
        elif pd.notna(first_row.get('BirthDate_Year')):
            year = str(first_row['BirthDate_Year']).strip()
            if year.isdigit() and len(year) == 4:
                dob = f"{year}-01-01"  # Default to Jan 1 if only year is known
        
        # Extract place of birth
        pob_cities = set()
        pob_countries = set()
        
        for _, row in group.iterrows():
            if pd.notna(row.get('BirthDate_Place')):
                pob_cities.add(clean_name(row['BirthDate_Place']))
            if pd.notna(row.get('BirthDate_City')):
                pob_cities.add(clean_name(row['BirthDate_City']))
            if pd.notna(row.get('BirthDate_Region')):
                pob_cities.add(clean_name(row['BirthDate_Region']))
            if pd.notna(row.get('BirthDate_CountryDescription')):
                pob_countries.add(clean_name(row['BirthDate_CountryDescription']))
            elif pd.notna(row.get('BirthDate_CountryIso2Code')):
                country = get_country_name(row['BirthDate_CountryIso2Code'])
                if country:
                    pob_countries.add(country)
        
        # Create the normalized record with all fields
        record = {
            'source': 'EU',
            'source_file': '20251121-FULL-1_1.csv',
            'record_type': record_type,
            'dataid': clean_name(first_row.get('Entity_EU_ReferenceNumber', '')),
            'reference_number': clean_name(first_row.get('Entity_UnitedNationId', '')),
            'name': primary_name,
            'first_name': first_name,
            'second_name': middle_name,
            'third_name': last_name if last_name and last_name not in [first_name, middle_name] else '',
            'fourth_name': '',  # Reserved for any additional name parts
            'aliases': '; '.join(sorted(aliases)) if aliases else '',
            'gender': clean_name(first_row.get('NameAlias_Gender', '')),
            'title': clean_name(first_row.get('NameAlias_Title', '')),
            'function': clean_name(first_row.get('NameAlias_Function', '')),
            'nationalities': '; '.join(sorted(nationalities)) if nationalities else '',
            'pob_cities': '; '.join(sorted(pob_cities)) if pob_cities else '',
            'pob_countries': '; '.join(sorted(pob_countries)) if pob_countries else '',
            'dob_dates': dob if dob else '',
            'dob_years': str(first_row.get('BirthDate_Year', '')).strip() if pd.notna(first_row.get('BirthDate_Year')) else '',
            'un_list_type': clean_name(first_row.get('Entity_Remark', '')),
            'list_type': 'EU Sanctions List',
            'program': program,
            'regulations': clean_name(first_row.get('Entity_Regulation_NumberTitle', '')),
            'comments': clean_name(first_row.get('Entity_DesignationDetails', '')),
            'listed_on': parse_date(first_row.get('Entity_DesignationDate')),
            'last_updated': parse_date(first_row.get('fileGenerationDate')),
            'addresses': '; '.join(sorted(addresses)) if addresses else '',
            'id_numbers': '; '.join(sorted(id_numbers)) if id_numbers else '',
            'additional_info': ''  # For any additional information
        }
        
        # Clean all string fields to ensure no NaN values
        for key, value in record.items():
            if isinstance(value, str):
                record[key] = value.strip()
            elif pd.isna(value):
                record[key] = ''
        
        records.append(record)
    
    # Create DataFrame from records
    normalized_df = pd.DataFrame(records)
    
    # Define the complete schema with all possible columns
    schema_columns = [
        # Core identification
        'source', 'source_file', 'record_type', 'dataid', 'reference_number',
        
        # Name information
        'name', 'first_name', 'second_name', 'third_name', 'fourth_name',
        'aliases', 'gender', 'title', 'function',
        
        # Location information
        'nationalities', 'pob_cities', 'pob_countries', 'pob_regions',
        'addresses', 'countries', 'regions', 'cities',
        
        # Date information
        'dob_dates', 'dob_years', 'listed_on', 'last_updated', 'updated_at',
        
        # Classification and references
        'un_list_type', 'list_type', 'program', 'regulations', 'reference_url',
        
        # Additional information
        'comments', 'id_numbers', 'additional_info',
        
        # Sanction details
        'authority', 'authority_uri', 'reason', 'source_information_url',
        'source_list_url', 'source_name', 'source_type', 'source_updated_at',
        'source_created_at', 'source_updated_in_db', 'source_created_in_db',
        'source_type_description', 'source_description', 'source_url',
        'source_aliases', 'source_remarks',
        
        # Status
        'is_individual', 'is_entity', 'is_vessel', 'is_government',
        'is_organization', 'is_other', 'is_active', 'is_removed'
    ]
    
    # Add any missing columns with empty values
    for col in schema_columns:
        if col not in normalized_df.columns:
            normalized_df[col] = ''
    
    # Reorder columns to match schema
    final_columns = [col for col in schema_columns if col in normalized_df.columns]
    normalized_df = normalized_df[final_columns]
    
    # Log summary statistics
    logger.info(f"Created {len(normalized_df)} normalized records")
    
    # Log record type distribution
    if 'record_type' in normalized_df.columns:
        type_counts = normalized_df['record_type'].value_counts().to_dict()
        logger.info(f"Record type distribution: {type_counts}")
    
    # Log nationality distribution
    if 'nationalities' in normalized_df.columns:
        nat_counts = normalized_df[normalized_df['nationalities'] != '']['nationalities'].value_counts().head(10).to_dict()
        logger.info(f"Top nationalities: {nat_counts}")
    
    # Log date ranges
    if 'listed_on' in normalized_df.columns:
        min_date = normalized_df[normalized_df['listed_on'] != '']['listed_on'].min()
        max_date = normalized_df[normalized_df['listed_on'] != '']['listed_on'].max()
        logger.info(f"Listing date range: {min_date} to {max_date}")
    
    return normalized_df

def main():
    """
    Main conversion function.
    
    This function orchestrates the entire process of loading, normalizing,
    and saving the EU sanctions data.
    """
    logger.info("\n" + "="*80)
    logger.info("EU Sanctions Data Normalization")
    logger.info("="*80)
    
    start_time = datetime.now()
    
    # Load EU data
    logger.info("\n[1/3] Loading EU sanctions data...")
    eu_df = load_eu_data()
    
    if eu_df.empty:
        logger.error("No EU data loaded. Cannot proceed.")
        return 1
    
    # Create normalized data
    logger.info("\n[2/3] Normalizing data...")
    normalized_df = create_normalized_eu_data(eu_df)
    
    if normalized_df.empty:
        logger.error("Failed to create normalized data")
        return 1
    
    # Save to output file
    logger.info("\n[3/3] Saving results...")
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_dir = project_root / 'app' / 'data' / 'sanctions' / 'normalized' / 'eu'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create timestamped output file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = output_dir / f'eu_sanctions_{timestamp}.csv'
    latest_file = output_dir / 'eu_sanctions_latest.csv'
    
    # Save the normalized data
    try:
        normalized_df.to_csv(output_file, index=False, encoding='utf-8')
        
        # Create/update the latest file symlink
        if latest_file.exists():
            latest_file.unlink()
        latest_file.symlink_to(output_file.name)
        
    except Exception as e:
        logger.error(f"Error saving output file: {str(e)}")
        return 1
    
    # Calculate statistics
    duration = (datetime.now() - start_time).total_seconds()
    records_per_second = len(normalized_df) / duration if duration > 0 else 0
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("NORMALIZATION COMPLETE")
    logger.info("="*80)
    logger.info(f"Records processed: {len(normalized_df):,}")
    logger.info(f"Processing time: {duration:.2f} seconds ({records_per_second:.1f} records/sec)")
    
    # Show record type distribution
    if 'record_type' in normalized_df.columns:
        logger.info("\nRecord type distribution:")
        type_counts = normalized_df['record_type'].value_counts()
        for rtype, count in type_counts.items():
            logger.info(f"  {rtype}: {count:,}")
    
    # Show sample records
    logger.info("\nSample records:")
    sample = normalized_df.head(3).to_dict('records')
    for i, row in enumerate(sample, 1):
        logger.info(f"\n[{i}] {row.get('name', '')}")
        logger.info(f"    Type: {row.get('record_type', '')}")
        logger.info(f"    Nationalities: {row.get('nationalities', '')}")
        logger.info(f"    DOB: {row.get('dob_dates', '')} ({row.get('dob_years', '')})")
        if row.get('addresses'):
            logger.info(f"    Address: {row.get('addresses', '')[:100]}...")
    
    logger.info("\nNext steps:")
    logger.info("1. Review the CSV file to ensure data looks correct")
    logger.info("2. Test with: python -c \"from app.services.sanctions_loader import SanctionsLoader; df = SanctionsLoader.load_sanctions(); eu = df[df['source'] == 'EU']; print(f'EU records: {len(eu)}'); print(eu[['name', 'record_type', 'nationalities']].head())\"")
    logger.info("3. Update the sanctions loader if the schema has changed")
    
    return 0

if __name__ == "__main__":
    import sys
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\nFatal error: {str(e)}", exc_info=True)
        sys.exit(1)