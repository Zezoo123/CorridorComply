#!/usr/bin/env python3
"""
Combine multiple sanctions lists into a single unified file.

This script combines normalized sanctions data from EU, UK, and UN sources
into a single comprehensive sanctions list with a consistent format.
"""

import pandas as pd
from pathlib import Path
import logging
from datetime import datetime
from typing import List, Dict, Any, Set, Optional
import unicodedata

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sanctions_combine.log')
    ]
)
logger = logging.getLogger(__name__)

def clean_text(text: Any) -> str:
    """Clean and normalize text by removing extra whitespace and normalizing unicode."""
    if not text or pd.isna(text):
        return ''
    
    # Convert to string and normalize unicode
    text = str(text)
    text = unicodedata.normalize('NFKC', text)
    
    # Remove extra whitespace and newlines
    text = ' '.join(text.split())
    
    return text.strip()

def combine_sanctions_lists(input_dirs: List[Path], output_dir: Path) -> Path:
    """
    Combine multiple sanctions lists into a single file.
    
    Args:
        input_dirs: List of directories containing normalized sanctions files
        output_dir: Directory to save the combined output
        
    Returns:
        Path to the combined output file
    """
    start_time = datetime.now()
    logger.info("\n" + "="*60)
    logger.info("Starting sanctions list combination")
    logger.info("="*60)
    
    # Find all latest files
    latest_files = []
    for dir_path in input_dirs:
        # First try to follow the 'latest' symlink
        latest = dir_path / "latest"
        if latest.exists():
            latest_files.append(latest.resolve())
        else:
            # If no symlink, find the most recent CSV file
            files = list(dir_path.glob("*.csv"))
            if files:
                latest_file = max(files, key=lambda x: x.stat().st_mtime)
                latest_files.append(latest_file)
    
    if not latest_files:
        logger.error("No input files found in the specified directories")
        raise FileNotFoundError("No input files found")
    
    # Load and combine all data
    dfs = []
    for file_path in latest_files:
        try:
            logger.info(f"Loading {file_path}")
            
            # Read the CSV file with appropriate parameters
            df = pd.read_csv(
                file_path, 
                dtype=str, 
                keep_default_na=False,
                encoding='utf-8',
                quotechar='"',
                escapechar='\\',
                quoting=1  # Quote all fields
            )
            
            # Ensure consistent column names (convert to lowercase and replace spaces with underscores)
            df.columns = [str(col).lower().replace(' ', '_') for col in df.columns]
            
            # Add source column if not present
            if 'source' not in df.columns:
                # Try to get source from directory name
                source = file_path.parent.name.upper()
                df['source'] = source
            
            # Ensure all required columns exist
            required_columns = [
                'source', 'source_file', 'record_type', 'dataid', 'reference_number',
                'name', 'first_name', 'middle_name', 'last_name', 'aliases', 'gender',
                'nationalities', 'pob_cities', 'pob_countries', 'dob_dates', 'dob_years',
                'addresses', 'id_numbers', 'program', 'comments', 'listed_on', 'last_updated',
                'processing_date', 'list_type'
            ]
            
            # Add missing columns with empty strings
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ''
            
            # Clean all string columns
            for col in df.select_dtypes(include=['object']).columns:
                df[col] = df[col].apply(clean_text)
            
            dfs.append(df)
            logger.info(f"  Loaded {len(df)} records from {file_path.name}")
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}", exc_info=True)
            continue
    
    if not dfs:
        logger.error("No data was loaded from any source files")
        raise ValueError("No data available to combine")
    
    # Combine all dataframes
    logger.info("Combining data...")
    combined_df = pd.concat(dfs, ignore_index=True)
    
    # Standardize column names and add missing columns
    required_columns = {
        'source', 'source_file', 'record_type', 'dataid', 'reference_number',
        'name', 'first_name', 'middle_name', 'last_name', 'aliases', 'gender',
        'nationalities', 'pob_cities', 'pob_countries', 'dob_dates', 'dob_years',
        'addresses', 'id_numbers', 'program', 'comments', 'listed_on', 'last_updated',
        'processing_date', 'list_type'
    }
    
    # Add missing columns with empty values
    for col in required_columns:
        if col not in combined_df.columns:
            combined_df[col] = ''
    
    # Select and reorder columns
    existing_columns = [col for col in required_columns if col in combined_df.columns]
    combined_df = combined_df[existing_columns]
    
    # Create output filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f"combined_sanctions_{timestamp}.csv"
    output_path = output_dir / output_filename
    latest_path = output_dir / "combined_sanctions_latest.csv"
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the combined data
    logger.info(f"Saving combined data to {output_path}")
    combined_df.to_csv(
        output_path,
        index=False,
        encoding='utf-8',
        quoting=1,  # Quote all fields
        quotechar='"',
        escapechar='\\'
    )
    
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
    logger.info("\n" + "="*60)
    logger.info("Combination complete!")
    logger.info("="*60)
    logger.info(f"Total records: {len(combined_df):,}")
    
    # Count by source
    if 'source' in combined_df.columns:
        source_counts = combined_df['source'].value_counts().to_dict()
        logger.info("\nRecords by source:")
        for source, count in source_counts.items():
            logger.info(f"  {source}: {count:,} records")
    
    # Count by record type
    if 'record_type' in combined_df.columns:
        type_counts = combined_df['record_type'].value_counts().to_dict()
        logger.info("\nRecords by type:")
        for rec_type, count in type_counts.items():
            logger.info(f"  {rec_type}: {count:,} records")
    
    logger.info(f"\nProcessing time: {duration:.2f} seconds")
    logger.info(f"Output file: {output_path}")
    
    return output_path

def main() -> int:
    """Main function to run the sanctions list combination."""
    try:
        # Set up paths
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        data_dir = project_root / "app" / "data" / "sanctions" / "normalized"
        
        # Define input directories
        input_dirs = [
            data_dir / "eu",
            data_dir / "uk",
            data_dir / "un",
            # Add more directories as needed
        ]
        
        # Set output directory
        output_dir = data_dir / "combined"
        
        # Run the combination
        combine_sanctions_lists(input_dirs, output_dir)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
