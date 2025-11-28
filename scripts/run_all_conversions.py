#!/usr/bin/env python3
"""
Run all conversion scripts in sequence.
"""
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

def run_script(script_path: str) -> Tuple[bool, str]:
    """Run a Python script and return success status and output."""
    try:
        result = subprocess.run(
            [sys.executable, script_path],
            check=True,
            capture_output=True,
            text=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def main():
    script_dir = Path(__file__).parent
    scripts = [
        script_dir / 'convert_eu_to_csv.py',
        script_dir / 'convert_ofac_to_csv.py',
        script_dir / 'convert_uk_to_csv.py',
        script_dir / 'convert_un_to_csv.py'
    ]

    print("Starting all conversion scripts...\n" + "="*50)
    
    for script in scripts:
        if not script.exists():
            print(f"⚠️  Script not found: {script}")
            continue
            
        print(f"\n🚀 Running {script.name}...")
        success, output = run_script(str(script))
        
        if success:
            print(f"✅ {script.name} completed successfully!")
            if output.strip():
                print(f"Output:\n{output}")
        else:
            print(f"❌ {script.name} failed!")
            print(f"Error:\n{output}")
    
    print("\n" + "="*50)
    print("All conversions completed!")

if __name__ == "__main__":
    main()
