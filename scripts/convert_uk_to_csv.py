#!/usr/bin/env python3
"""
Convert raw UK sanctions data (ODS format) to normalized CSV format.

This script loads the UK sanctions ODS file and converts it to a normalized
CSV format compatible with the existing UN and OFAC sanctions data.
"""

import pandas as pd
from pathlib import Path
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

def split_name_parts(name):
    """Split a name into first, second, third, fourth parts."""
    if pd.isna(name) or not name:
        return ['', '', '', '']
    
    # Split on spaces and clean up
    parts = str(name).upper().split()
    
    # Pad to 4 parts
    while len(parts) < 4:
        parts.append('')
    
    return parts[:4]

def create_normalized_uk_data(uk_df):
    """Create normalized UK sanctions data from the raw UK DataFrame."""
    if uk_df.empty:
        logger.error("No UK data to process")
        return pd.DataFrame()
    
    logger.info("Creating normalized UK data")
    logger.info(f"UK columns available: {list(uk_df.columns)}")
    
    # Clean up whitespace in Type column
    uk_df['Type'] = uk_df['Type'].str.strip()
    
    # Create result DataFrame with UK data
    result_df = uk_df.copy()
    
    # Split primary name into components
    name_components = result_df['Name'].apply(split_name_parts)
    name_df = pd.DataFrame(name_components.tolist())
    result_df = pd.concat([result_df.reset_index(drop=True), name_df], axis=1)
    
    # Initialize with data to avoid NaN issues
    data = {}
    
    # Required fields with UK data mapping
    data['source'] = ['UK'] * len(result_df)  # Ensure source is set to UK
    data['source_file'] = ['FCDO_SL_Wed_Nov_19_2025.ods'] * len(result_df)
    data['record_type'] = result_df['Type'].apply(lambda x: 'individual' if str(x).upper() == 'INDIVIDUAL' else 'entity' if str(x).upper() == 'ENTITY' else 'vessel')
    data['dataid'] = result_df['Unique ID'].astype(str)
    data['reference_number'] = result_df['Unique ID'].astype(str)
    data['name'] = result_df['Name'].fillna('').str.upper()
    data['first_name'] = result_df[0]  # From split_name_parts
    data['second_name'] = result_df[1]  # From split_name_parts
    data['third_name'] = result_df[2]  # From split_name_parts
    data['fourth_name'] = result_df[3]  # From split_name_parts
    data['aliases'] = [''] * len(result_df)  # UK data doesn't seem to have separate aliases
    data['gender'] = [''] * len(result_df)  # UK doesn't provide gender
    data['nationalities'] = [''] * len(result_df)  # UK doesn't provide nationality
    data['pob_cities'] = [''] * len(result_df)  # UK doesn't provide place of birth
    data['pob_countries'] = [''] * len(result_df)  # UK doesn't provide place of birth
    data['dob_dates'] = [''] * len(result_df)  # UK doesn't provide date of birth
    data['dob_years'] = [''] * len(result_df)  # UK doesn't provide date of birth
    data['un_list_type'] = [''] * len(result_df)  # Not applicable for UK
    data['list_type'] = ['UK Sanctions List'] * len(result_df)
    data['program'] = result_df['Regime Name'].fillna('')
    data['comments'] = result_df['Sanctions Imposed'].fillna('')
    data['listed_on'] = result_df['Date Designated'].fillna('')
    data['last_updated'] = [''] * len(result_df)  # UK doesn't provide this
    data['addresses'] = [''] * len(result_df)  # UK doesn't provide addresses
    data['id_numbers'] = [''] * len(result_df)  # UK doesn't provide this
    
    normalized_df = pd.DataFrame(data)
    
    # Debug: Check the DataFrame before saving
    logger.info(f"DataFrame shape: {normalized_df.shape}")
    logger.info(f"DataFrame columns: {list(normalized_df.columns)}")
    
    # Verify source column
    source_counts = normalized_df['source'].value_counts().to_dict()
    logger.info(f"Source column verification: {source_counts}")
    
    return normalized_df

def main():
    """Main conversion function."""
    logger.info("\n" + "="*60)
    logger.info("Starting UK sanctions conversion")
    logger.info("="*60)
    
    # Load UK data
    uk_df = load_uk_data()
    
    if uk_df.empty:
        logger.error("No UK data loaded. Cannot proceed.")
        return
    
    # Create normalized data
    normalized_df = create_normalized_uk_data(uk_df)
    
    if normalized_df.empty:
        logger.error("Failed to create normalized data")
        return
    
    # Save to output file
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_dir = project_root / 'app' / 'data' / 'sanctions' / 'normalized' / 'uk'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'uk_sanctions.csv'
    
    logger.info(f"Saving normalized data to {output_file}")
    normalized_df.to_csv(output_file, index=False)
    
    logger.info("\n" + "="*60)
    logger.info("Conversion complete!")
    logger.info("="*60)
    logger.info(f"Input file: FCDO_SL_Wed_Nov_19_2025.ods")
    logger.info(f"Output: {len(normalized_df)} normalized records")
    logger.info(f"Output file: {output_file}")
    
    # Show sample records
    logger.info("\nSample records:")
    for idx, row in normalized_df.head(5).iterrows():
        logger.info(f"  {row['name']} ({row['record_type']}) - Program: {row['program']}")
    
    logger.info("\nNext steps:")
    logger.info("1. Review the CSV file to ensure data looks correct")
    logger.info("2. Test with: python -c \"from app.services.sanctions_loader import SanctionsLoader; df = SanctionsLoader.load_sanctions(); uk_records = df[df['source'] == 'UK']; print(f'UK records: {len(uk_records)}'); print(uk_records.head())\"")

if __name__ == "__main__":
    main()
