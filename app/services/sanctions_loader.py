import pandas as pd
from pathlib import Path
from typing import Optional, ClassVar, List, Set, Dict, Any, Union, Tuple
import logging
import re
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SanctionsLoader:
    """Loader for combined sanctions data with caching and data normalization."""
    
    _cache: ClassVar[Optional[pd.DataFrame]] = None
    _REQUIRED_COLUMNS = {"source", "record_type", "dataid", "name"}
    _STRING_COLUMNS = [
        "aliases", "nationalities", "pob_cities", "pob_countries",
        "dob_dates", "dob_years", "comments", "addresses", "listed_on",
        "last_updated", "processing_date", "first_name", "middle_name",
        "last_name", "un_list_type", "list_type", "program", "gender",
        "id_numbers", "reference_number", "source_file"
    ]

    @classmethod
    def _find_latest_sanctions_file(cls, directory: Path) -> Path:
        """Find the most recent combined sanctions file in the given directory."""
        pattern = "combined_sanctions_*.csv"
        files = list(directory.glob(pattern))
        
        if not files:
            # Also check in the parent directory for backward compatibility
            parent_files = list(directory.parent.glob(pattern))
            if parent_files:
                files = parent_files
            else:
                raise FileNotFoundError(
                    f"No combined sanctions files found matching '{pattern}' in {directory} or its parent directory"
                )
        
        # Sort by modification time and pick the latest
        latest = max(files, key=lambda f: f.stat().st_mtime)
        logger.info(f"Using sanctions file: {latest}")
        return latest

    @classmethod
    def _normalize_dataframe(cls, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize the sanctions DataFrame according to requirements."""
        # Create a copy to avoid modifying the original
        df = df.copy()
        
        # Ensure required columns exist
        missing_columns = cls._REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Drop rows with empty/None names
        initial_count = len(df)
        df = df[df['name'].notna() & (df['name'] != '')].copy()
        if len(df) < initial_count:
            logger.info(f"Dropped {initial_count - len(df)} rows with empty names")
        
        # Ensure all string columns exist and are properly typed
        for col in cls._STRING_COLUMNS:
            if col not in df.columns:
                df[col] = ""
            else:
                df[col] = df[col].fillna("").astype(str)
        
        # Add/update special columns
        df['updated_at'] = df['last_updated'].fillna(df.get('processing_date', '')).fillna('')
        df['search_name'] = df['name'].str.upper().str.strip().str.replace(r'\s+', ' ', regex=True)
        df['search_aliases'] = df['aliases'].fillna('').str.upper().str.strip().str.replace(r'\s+', ' ', regex=True)
        
        return df

    @classmethod
    def load(cls, path: Optional[Union[Path, str]] = None) -> pd.DataFrame:
        """
        Load and normalize the combined sanctions data.
        
        Args:
            path: Optional path to a specific sanctions file. If not provided,
                 automatically finds the latest combined sanctions file.
        
        Returns:
            DataFrame containing the normalized sanctions data.
        
        Raises:
            FileNotFoundError: If no sanctions file is found.
            ValueError: If the file is missing required columns.
        """
        # If we have a cached version and no specific path is requested, return it
        if cls._cache is not None and path is None:
            return cls._cache
        
        # Resolve the path to the sanctions file
        if path is None:
            sanctions_dir = Path(__file__).parent.parent / "data" / "sanctions" / "combined"
            sanctions_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
            path = cls._find_latest_sanctions_file(sanctions_dir)
        else:
            path = Path(path)
            if not path.exists():
                # Try relative to the project root
                project_root = Path(__file__).parent.parent.parent
                alt_path = project_root / path
                if alt_path.exists():
                    path = alt_path
                else:
                    raise FileNotFoundError(f"Sanctions file not found: {path}")

        # Read the CSV with appropriate settings
        logger.info(f"Loading sanctions from {path}")
        try:
            df = pd.read_csv(path, low_memory=False)
            
            # Normalize the data
            df = cls._normalize_dataframe(df)
            
            # Cache the result if no specific path was provided
            if path is None:
                cls._cache = df
            return df
            
        except Exception as e:
            logger.error(f"Error loading sanctions file: {e}")
            raise

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the cached sanctions data."""
        cls._cache = None
        logger.debug("Sanctions cache cleared")
    
    @classmethod
    def check_if_update_needed(cls, update_interval_days: int = 7) -> Tuple[bool, Optional[float]]:
        """
        Check if sanctions lists need to be updated based on file age.
        
        Args:
            update_interval_days: Number of days after which update is needed (default: 7)
            
        Returns:
            Tuple of (needs_update: bool, age_days: Optional[float])
            Returns (True, age_days) if update is needed, (False, age_days) if not
        """
        try:
            sanctions_dir = Path(__file__).parent.parent / "data" / "sanctions" / "combined"
            sanctions_dir.mkdir(parents=True, exist_ok=True)
            
            # Find latest combined file
            try:
                latest_file = cls._find_latest_sanctions_file(sanctions_dir)
            except FileNotFoundError:
                # No combined file exists - definitely needs update
                logger.info("No combined sanctions file found - update needed")
                return True, None
            
            # Check file age
            file_mtime = latest_file.stat().st_mtime
            age_seconds = datetime.now().timestamp() - file_mtime
            age_days = age_seconds / 86400  # Convert to days
            
            needs_update = age_days >= update_interval_days
            
            if needs_update:
                logger.info(f"Sanctions file is {age_days:.1f} days old (threshold: {update_interval_days} days) - update needed")
            else:
                logger.debug(f"Sanctions file is {age_days:.1f} days old - no update needed yet")
            
            return needs_update, age_days
            
        except Exception as e:
            logger.error(f"Error checking if update needed: {str(e)}")
            # On error, assume update is needed to be safe
            return True, None

# For backward compatibility
def load_sanctions(path: Optional[Union[Path, str]] = None) -> pd.DataFrame:
    """
    Load the combined sanctions data.
    
    This is a convenience function that delegates to SanctionsLoader.load().
    
    Example:
        >>> from app.services.sanctions_loader import load_sanctions
        >>> df = load_sanctions()
        >>> print(df.shape)
        >>> print(df.head())
    """
    return SanctionsLoader.load(path=path)

# Bind the load_sanctions method to the class
SanctionsLoader.load_sanctions = SanctionsLoader.load
