"""
Tests for the sanctions_loader module.
"""
import pytest
import pandas as pd
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
from typing import Dict, Union

# Import the module to test
from app.services.sanctions_loader import SanctionsLoader, load_sanctions

# Sample test data
SAMPLE_DATA = """source,source_file,record_type,dataid,name,aliases,nationalities,last_updated,processing_date
UN,un_sanctions_2023.csv,individual,1,John Doe,J. Doe,US;UK,2023-01-01,2023-01-02
EU,eu_sanctions_2023.csv,entity,2,ACME Corp,,US,2023-01-03,2023-01-04
"""

# Test data with missing name
TEST_MISSING_NAME = """source,source_file,record_type,dataid,name,aliases,nationalities
UN,test.csv,individual,1,John Doe,J. Doe,US
EU,test.csv,entity,2,,,"""

@pytest.fixture
def temp_sanctions_dir(tmp_path):
    """Create a temporary directory with a sample sanctions file."""
    # Create directory structure
    sanctions_dir = tmp_path / "data" / "sanctions"
    combined_dir = sanctions_dir / "combined"
    combined_dir.mkdir(parents=True)
    
    # Create a sample file with a timestamp in the name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sample_file = combined_dir / f"combined_sanctions_{timestamp}.csv"
    sample_file.write_text(SAMPLE_DATA)
    
    # Also create a test file in the parent directory for backward compatibility
    parent_file = sanctions_dir / "combined_sanctions_legacy.csv"
    parent_file.write_text(SAMPLE_DATA)
    
    # Create a test file with a missing name
    missing_name_file = tmp_path / "test_missing_name.csv"
    missing_name_file.write_text(TEST_MISSING_NAME)
    
    return {
        'root': tmp_path,
        'sanctions_dir': sanctions_dir,
        'combined_dir': combined_dir,
        'sample_file': sample_file,
        'parent_file': parent_file,
        'missing_name_file': missing_name_file
    }

def test_load_returns_dataframe(temp_sanctions_dir: Dict[str, Union[Path, str]]) -> None:
    """Test that load() returns a DataFrame with the expected structure."""
    # Test loading the sample file directly
    df = SanctionsLoader.load(temp_sanctions_dir['sample_file'])
    
    # Check basic structure
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2  # Should have exactly our test records
    
    # Check required columns
    required_columns = {
        "source", "record_type", "dataid", "name", "aliases", 
        "search_name", "updated_at"
    }
    assert required_columns.issubset(df.columns)
    
    # Check that search_name was created correctly
    assert "search_name" in df.columns
    assert df[df["name"] == "John Doe"]["search_name"].iloc[0] == "JOHN DOE"
    
    # Check that updated_at was set correctly
    john_doe = df[df["name"] == "John Doe"].iloc[0]
    assert john_doe["updated_at"] == "2023-01-01"  # Should use last_updated
    
    acme = df[df["name"] == "ACME Corp"].iloc[0]
    assert acme["updated_at"] == "2023-01-03"  # Should use last_updated

def test_no_nans_in_string_columns(temp_sanctions_dir: Dict[str, Union[Path, str]]) -> None:
    """Test that string columns contain no NaN values."""
    df = SanctionsLoader.load(temp_sanctions_dir['sample_file'])
    
    string_columns = [
        "aliases", "nationalities", "pob_cities", "pob_countries",
        "dob_dates", "dob_years", "comments", "addresses"
    ]
    
    for col in string_columns:
        if col in df.columns:
            assert df[col].isna().sum() == 0, f"Column {col} contains NaN values"

def test_drop_rows_without_name(temp_sanctions_dir: Dict[str, Union[Path, str]]) -> None:
    """Test that rows without a name are dropped."""
    # Create a test file with one valid and one invalid row
    test_data = """source,source_file,record_type,dataid,name,aliases,nationalities,last_updated,processing_date
UN,test.csv,individual,1,John Doe,J. Doe,US,2023-01-01,2023-01-02
EU,test.csv,entity,2,,,US,2023-01-03,2023-01-04"""
    test_file = temp_sanctions_dir['combined_dir'] / "test_missing_name.csv"
    test_file.write_text(test_data)
    
    df = SanctionsLoader.load(test_file)
    assert len(df) == 1
    assert df.iloc[0]["name"] == "John Doe"

def test_cache_behavior(temp_sanctions_dir: Dict[str, Union[Path, str]]) -> None:
    """Test that caching works as expected."""
    # Clear any existing cache
    SanctionsLoader.clear_cache()
    
    # First call should load from disk
    df1 = SanctionsLoader.load(temp_sanctions_dir['sample_file'])
    
    # Second call should return the same data (may not be same object due to pandas internals)
    df2 = SanctionsLoader.load(temp_sanctions_dir['sample_file'])
    assert df1.equals(df2)  # Should have the same data
    
    # After clearing cache, should load fresh
    SanctionsLoader.clear_cache()
    df3 = SanctionsLoader.load(temp_sanctions_dir['sample_file'])
    assert df1.equals(df3)  # Should have the same data

def test_load_sanctions_function(temp_sanctions_dir: Dict[str, Union[Path, str]]) -> None:
    """Test that the load_sanctions() function works as expected."""
    # Test that the function loads data correctly
    df = load_sanctions(temp_sanctions_dir['sample_file'])
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    
    # Test that the class method works the same way
    df2 = SanctionsLoader.load_sanctions(temp_sanctions_dir['sample_file'])
    assert df.equals(df2)

def test_missing_file_error() -> None:
    """Test that appropriate error is raised when file is missing."""
    with pytest.raises(FileNotFoundError) as excinfo:
        SanctionsLoader.load("this_file_does_not_exist_1234567890.csv")
    assert "not found" in str(excinfo.value).lower()

def test_find_latest_file(temp_sanctions_dir: Dict[str, Union[Path, str]]) -> None:
    """Test that the latest file is found correctly."""
    # Create a new file with a newer timestamp
    new_file = temp_sanctions_dir['combined_dir'] / "combined_sanctions_newest.csv"
    new_file.write_text(SAMPLE_DATA)
    
    # The loader should pick the newest file
    found_file = SanctionsLoader._find_latest_sanctions_file(temp_sanctions_dir['combined_dir'])
    assert found_file.name == "combined_sanctions_newest.csv"

def test_backward_compatibility(temp_sanctions_dir: Dict[str, Union[Path, str]]) -> None:
    """Test backward compatibility with the old API."""
    # Test that the old load_sanctions method works
    df = SanctionsLoader.load_sanctions(temp_sanctions_dir['sample_file'])
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0
    
    # Test that the top-level function works
    df2 = load_sanctions(temp_sanctions_dir['sample_file'])
    assert df.equals(df2)

@patch('pandas.read_csv')
def test_error_handling(mock_read_csv: MagicMock) -> None:
    """Test error handling when reading the CSV fails."""
    # Set up the mock to raise an exception
    mock_read_csv.side_effect = Exception("Test error")
    
    # Create a temporary file
    test_file = Path("test_error.csv")
    test_file.touch()  # Create an empty file
    
    try:
        with pytest.raises(Exception) as excinfo:
            SanctionsLoader.load(test_file)
        assert "Test error" in str(excinfo.value)
    finally:
        # Clean up
        if test_file.exists():
            test_file.unlink()
