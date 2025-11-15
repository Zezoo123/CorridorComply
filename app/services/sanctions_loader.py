import pandas as pd
from pathlib import Path

SANCTIONS_DIR = Path(__file__).parent.parent / "data" / "sanctions"

class SanctionsLoader:
    _cache = None

    @classmethod
    def load_sanctions(cls):
        if cls._cache is not None:
            return cls._cache

        sanctions_files = SANCTIONS_DIR.glob("*.csv")
        dfs = []

        for f in sanctions_files:
            df = pd.read_csv(f)
            df["source"] = f.stem
            dfs.append(df)

        if dfs:
            cls._cache = pd.concat(dfs, ignore_index=True)
        else:
            cls._cache = pd.DataFrame()

        return cls._cache
