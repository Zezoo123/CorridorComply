#!/usr/bin/env python3
"""
Convert OFAC sanctions CSV files to normalized format
Combines sdn.csv, alt.csv, and add.csv into a single normalized CSV file
compatible with UN sanctions CSV schema.
"""
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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


def create_normalized_ofac_data(sdn_df: pd.DataFrame, alt_df: pd.DataFrame, add_df: pd.DataFrame) -> pd.DataFrame:
    """
    Create normalized OFAC sanctions data compatible with UN sanctions schema
    """
    logger.info("Creating normalized OFAC data")
    
    if sdn_df.empty:
        logger.error("No SDN data available")
        return pd.DataFrame()
    
    # Start with SDN data as base
    result_df = sdn_df.copy()
    
    # Log available columns for debugging
    logger.info(f"SDN columns available: {list(result_df.columns)}")
    
    # Ensure we have the required columns
    if 'ent_num' not in result_df.columns:
        logger.error("ent_num column not found in SDN data")
        return pd.DataFrame()
    
    if 'sdn_name' not in result_df.columns:
        logger.error("sdn_name column not found in SDN data")
        return pd.DataFrame()
    
    # Split primary name into components
    name_components = result_df['sdn_name'].apply(split_name_parts)
    name_df = pd.DataFrame(name_components.tolist())
    result_df = pd.concat([result_df.reset_index(drop=True), name_df], axis=1)
    
    # Process aliases
    if not alt_df.empty and 'ent_num' in alt_df.columns:
        logger.info("Processing aliases")
        logger.info(f"ALT columns available: {list(alt_df.columns)}")
        
        # Debug: Show sample of ALT data
        logger.info(f"Sample ALT data:")
        for idx, row in alt_df.head(5).iterrows():
            logger.info(f"  ent_num: {row['ent_num']}, alt_type: {row['alt_type']}, alt_name: {repr(row['alt_name'])}, alt_reg_date: {repr(row['alt_reg_date'])}")
        
        # Group aliases by ent_num
        # The actual alias name is in column 'alt_reg_date' (4th column), not 'alt_name'
        alias_groups = alt_df.groupby('ent_num')['alt_reg_date'].apply(lambda x: '; '.join(filter(None, x.astype(str))))
        result_df['aliases'] = result_df['ent_num'].map(alias_groups).fillna('')
        
        # Debug: Show sample of grouped aliases
        logger.info(f"Sample grouped aliases:")
        for ent_num, aliases in alias_groups.head(5).items():
            logger.info(f"  ent_num {ent_num}: {repr(aliases)}")
    else:
        logger.warning("No ALT data available")
        result_df['aliases'] = ''
    
    # Group addresses by ent_num
    if not add_df.empty:
        logger.info("Processing addresses")
        logger.info(f"ADD columns available: {list(add_df.columns)}")
        
        # Combine address parts if columns exist
        if 'address' in add_df.columns:
            add_df['address_part'] = add_df['address'].fillna('')
        else:
            add_df['address_part'] = ''
            
        if 'city_state_zip' in add_df.columns:
            add_df['address_part'] = add_df['address_part'] + ', ' + add_df['city_state_zip'].fillna('')
        
        if 'country' in add_df.columns:
            add_df['address_part'] = add_df['address_part'] + ', ' + add_df['country'].fillna('')
        
        if 'ent_num' in add_df.columns:
            address_groups = add_df.groupby('ent_num')['address_part'].apply(lambda x: '; '.join(filter(None, x.astype(str))))
            result_df['addresses'] = result_df['ent_num'].map(address_groups).fillna('')
        else:
            logger.warning("ADD file missing ent_num column")
            result_df['addresses'] = ''
    else:
        result_df['addresses'] = ''
    
    # Map to UN sanctions schema
    # Initialize with data to avoid NaN issues
    data = {}
    
    # Required fields with OFAC data mapping
    data['source'] = ['OFAC'] * len(result_df)  # Ensure source is set to OFAC
    data['source_file'] = ['sdn.csv'] * len(result_df)
    data['record_type'] = result_df.get('sdn_type', '').apply(lambda x: 'individual' if str(x).upper() == 'INDIVIDUAL' else 'entity')
    data['dataid'] = result_df['ent_num'].astype(str)
    data['reference_number'] = result_df['ent_num'].astype(str)
    data['name'] = result_df['sdn_name'].fillna('').str.upper()
    data['first_name'] = result_df['first_name']
    data['second_name'] = result_df['second_name']
    data['third_name'] = result_df['third_name']
    data['fourth_name'] = result_df['fourth_name']
    data['aliases'] = result_df['aliases']
    data['gender'] = [''] * len(result_df)  # OFAC doesn't provide gender
    data['nationalities'] = [''] * len(result_df)  # OFAC doesn't provide nationality
    data['pob_cities'] = [''] * len(result_df)  # OFAC doesn't provide place of birth
    data['pob_countries'] = [''] * len(result_df)  # OFAC doesn't provide place of birth
    data['dob_dates'] = [''] * len(result_df)  # OFAC doesn't provide date of birth
    data['dob_years'] = [''] * len(result_df)  # OFAC doesn't provide date of birth
    data['un_list_type'] = [''] * len(result_df)  # Not applicable for OFAC
    data['list_type'] = ['OFAC List'] * len(result_df)
    data['program'] = result_df.get('program', '').fillna('')
    data['comments'] = result_df.get('remarks', '').fillna('')
    data['listed_on'] = [''] * len(result_df)  # OFAC doesn't provide this
    data['last_updated'] = [''] * len(result_df)  # OFAC doesn't provide this
    data['addresses'] = result_df['addresses']
    data['id_numbers'] = [''] * len(result_df)  # OFAC doesn't provide this
    
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


def main():
    """Main function"""
    logger.info("Starting OFAC sanctions conversion")
    
    # Define paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    raw_dir = project_root / "app" / "data" / "sanctions" / "raw" / "ofac"
    output_dir = project_root / "app" / "data" / "sanctions" / "normalized" / "ofac"
    
    # Input files
    sdn_file = raw_dir / "sdn.csv"
    alt_file = raw_dir / "alt.csv"
    add_file = raw_dir / "add.csv"
    
    # Output file
    output_file = output_dir / "ofac_sanctions.csv"
    
    # Load data
    sdn_df = load_sdn_data(sdn_file)
    alt_df = load_alt_data(alt_file)
    add_df = load_add_data(add_file)
    
    if sdn_df.empty:
        logger.error("No SDN data loaded. Cannot proceed.")
        return
    
    # Create normalized data
    normalized_df = create_normalized_ofac_data(sdn_df, alt_df, add_df)
    
    if normalized_df.empty:
        logger.error("Failed to create normalized data")
        return
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save to CSV
    logger.info(f"Saving normalized data to {output_file}")
    
    # Debug: Check the DataFrame before saving
    logger.info(f"DataFrame shape: {normalized_df.shape}")
    logger.info(f"DataFrame columns: {list(normalized_df.columns)}")
    logger.info(f"First row of DataFrame:")
    logger.info(f"  Source: {repr(normalized_df.iloc[0]['source'])}")
    logger.info(f"  Name: {repr(normalized_df.iloc[0]['name'])}")
    
    normalized_df.to_csv(output_file, index=False)
    
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
    main()
