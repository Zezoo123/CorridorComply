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

class SanctionsCombiner:
    """Combine multiple sanctions lists into a single consolidated list."""
    
    def __init__(self, base_dir: str, output_dir: str):
        """Initialize the SanctionsCombiner.
        
        Args:
            base_dir: Base directory containing the sanctions data
            output_dir: Directory to save the combined output
        """
        self.base_dir = Path(base_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def find_latest_files(self) -> List[Path]:
        """Find all '*_latest.csv' files in the normalized subdirectories.
        
        Returns:
            List of paths to the latest files
        """
        normalized_dir = self.base_dir / 'normalized'
        if not normalized_dir.exists():
            logger.error(f"Normalized directory not found: {normalized_dir}")
            return []
            
        latest_files = []
        for source_dir in normalized_dir.iterdir():
            if source_dir.is_dir():
                latest_file = next(source_dir.glob('*_latest.csv'), None)
                if latest_file:
                    latest_files.append(latest_file)
                    logger.info(f"Found latest file: {latest_file}")
                else:
                    logger.warning(f"No '*_latest.csv' file found in {source_dir}")
        
        return latest_files
    
    def read_csv_file(self, file_path: Path) -> Optional[pd.DataFrame]:
        """Read a CSV file into a pandas DataFrame.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            DataFrame containing the CSV data, or None if reading fails
        """
        try:
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
                df['source'] = file_path.parent.name.upper()
                
            return df
            
        except Exception as e:
            logger.error(f"Error reading {file_path}: {str(e)}")
            return None
    
    def combine_sanctions(self) -> pd.DataFrame:
        """Combine all latest sanctions lists into a single DataFrame.
        
        Returns:
            Combined DataFrame containing all sanctions
        """
        latest_files = self.find_latest_files()
        
        if not latest_files:
            logger.error("No latest files found to combine")
            return pd.DataFrame()
        
        all_dfs = []
        for file_path in latest_files:
            logger.info(f"Processing {file_path}")
            df = self.read_csv_file(file_path)
            if df is not None and not df.empty:
                all_dfs.append(df)
        
        if not all_dfs:
            logger.warning("No valid data found to combine")
            return pd.DataFrame()
            
        # Combine all DataFrames
        combined_df = pd.concat(all_dfs, ignore_index=True)
        
        # Add a unique ID for each record
        combined_df['id'] = combined_df.index + 1
        
        return combined_df
    
    def save_combined_file(self, df: pd.DataFrame) -> str:
        """Save the combined DataFrame to a CSV file.
        
        Args:
            df: DataFrame to save
            
        Returns:
            Path to the saved file
        """
        if df.empty:
            logger.warning("No data to save")
            return ""
            
        # Create output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"combined_sanctions_{timestamp}.csv"
        
        # Save to CSV
        df.to_csv(output_file, index=False, encoding='utf-8', quoting=1)
        
        # Create/update latest symlink
        latest_file = self.output_dir / "combined_sanctions_latest.csv"
        if latest_file.exists():
            latest_file.unlink()
        latest_file.symlink_to(output_file.name)
        
        return str(output_file)

def main() -> int:
    """Main function to run the sanctions list combination."""
    try:
        logger.info("Starting sanctions combination process")
        start_time = datetime.now()
        
        # Set up paths
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        base_dir = project_root / "app" / "data" / "sanctions"
        output_dir = base_dir / "combined"
        
        # Initialize and run the combiner
        combiner = SanctionsCombiner(base_dir, output_dir)
        combined_df = combiner.combine_sanctions()
        
        if combined_df.empty:
            logger.error("No data was combined. Check the input files and try again.")
            return 1
        
        # Save the combined file
        output_file = combiner.save_combined_file(combined_df)
        
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
        
        # Count by record type if the column exists
        if 'record_type' in combined_df.columns:
            type_counts = combined_df['record_type'].value_counts().to_dict()
            logger.info("\nRecords by type:")
            for rec_type, count in type_counts.items():
                logger.info(f"  {rec_type}: {count:,} records")
        
        logger.info(f"\nProcessing time: {duration:.2f} seconds")
        logger.info(f"Output file: {output_file}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during processing: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
