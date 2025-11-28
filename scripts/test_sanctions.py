#!/usr/bin/env python3
"""Test script for sanctions loading and matching."""
import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set the PYTHONPATH environment variable
os.environ['PYTHONPATH'] = str(project_root)

# Now import the modules
from app.services.sanctions_loader import SanctionsLoader
from app.services.aml_service import AMLService
import pandas as pd

def test_sanctions_loading():
    """Test loading the sanctions data."""
    print("Testing sanctions data loading...")
    try:
        # Load the sanctions data directly
        sanctions_df = SanctionsLoader.load()
        print(f"✅ Successfully loaded {len(sanctions_df)} sanctions records")
        
        # Check if the expected columns are present
        expected_columns = {"name", "source", "record_type"}
        missing_columns = expected_columns - set(sanctions_df.columns)
        if missing_columns:
            print(f"❌ Missing expected columns: {missing_columns}")
        else:
            print("✅ All expected columns are present")
            
        # Show a sample of the data
        print("\nSample data:")
        print(sanctions_df[list(expected_columns)].head(3))
        
    except Exception as e:
        print(f"❌ Error loading sanctions data: {e}")
        import traceback
        traceback.print_exc()

def test_aml_matching():
    """Test AML name matching."""
    print("\nTesting AML name matching...")
    try:
        # Test with a known name from the sanctions list
        test_cases = [
            {"name": "ERIC BADEGE", "dob": "1971-01-01", "nationality": "DEMOCRATIC REPUBLIC OF THE CONGO"},
            {"name": "GASTON IYAMUREMYE", "dob": "1948-01-01", "nationality": "RWANDA"},
            {"name": "JOHN SMITH", "dob": "1980-01-01", "nationality": "UNITED STATES"}  # Should not match
        ]
        
        for i, test in enumerate(test_cases, 1):
            print(f"\nTest case {i}: {test['name']}")
            try:
                result = AMLService.screen(
                    request_id=f"test_{i}",
                    full_name=test["name"],
                    dob=test["dob"],
                    nationality=test["nationality"]
                )
                print("✅ Successfully processed")
                print("Result:", result)
            except Exception as e:
                print(f"❌ Error in test case {i}: {e}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"❌ Error in test_aml_matching: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_sanctions_loading()
    test_aml_matching()
