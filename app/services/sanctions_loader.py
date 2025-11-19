import pandas as pd
from pathlib import Path

SANCTIONS_DIR = Path(__file__).parent.parent / "data" / "sanctions"

class SanctionsLoader:
    _cache = None

    @classmethod
    def load_sanctions(cls):
        if cls._cache is not None:
            return cls._cache

        # Look for CSV files in normalized subdirectories
        normalized_dir = SANCTIONS_DIR / "normalized"
        sanctions_files = []
        for subdir in ["un", "ofac", "uk", "eu"]:
            sanctions_files.extend((normalized_dir / subdir).glob("*.csv"))
        
        dfs = []

        for f in sanctions_files:
            # Skip empty files
            if f.stat().st_size == 0:
                continue
            
            try:
                df = pd.read_csv(f)
                # Check if DataFrame is empty
                if df.empty:
                    continue
                
                # Extract source from parent directory name (un, ofac, uk, eu)
                source = f.parent.name.upper()
                df["source"] = source
                dfs.append(df)
            except (pd.errors.EmptyDataError, ValueError) as e:
                # Skip files that can't be parsed
                continue

        if dfs:
            cls._cache = pd.concat(dfs, ignore_index=True)
        else:
            # Return empty DataFrame with expected columns
            cls._cache = pd.DataFrame(columns=["name", "source"])

        return cls._cache
