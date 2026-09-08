#!/usr/bin/env python3
"""
Auto-update script for sanctions lists.

This script automatically downloads fresh sanctions lists from:
- UN: https://scsanctions.un.org/resources/xml/en/consolidated.xml
- OFAC: https://www.treasury.gov/ofac/downloads/sdn.csv (and alt.csv, add.csv)
- UK: https://search-uk-sanctions-list.service.gov.uk/api/report/ods (API endpoint)
- EU: https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content (direct CSV)
- Qatar NCTC unified record (UNSC + domestic designations): MOI portal JSON

Then converts and combines them into a single unified list.

Can be run manually, scheduled via cron, or called from API startup.
"""

import requests
import logging
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sanctions_update.log')
    ]
)
logger = logging.getLogger(__name__)

# Project paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "app" / "data" / "sanctions"
RAW_DIR = DATA_DIR / "raw"
NORMALIZED_DIR = DATA_DIR / "normalized"
COMBINED_DIR = DATA_DIR / "combined"

# Download URLs
UN_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
OFAC_ALT_URL = "https://www.treasury.gov/ofac/downloads/alt.csv"
OFAC_ADD_URL = "https://www.treasury.gov/ofac/downloads/add.csv"

# UK and EU sanctions URLs
UK_SANCTIONS_URL = "https://search-uk-sanctions-list.service.gov.uk/"
# EU Financial Sanctions List - Consolidated XML format
EU_SANCTIONS_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw"
# Alternative CSV format (if needed)
# EU_SANCTIONS_CSV_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw=="

# Qatar NCTC unified sanction record (UNSC designations as applied in Qatar + domestic designations)
QA_NCTC_URL = ("https://portal.moi.gov.qa/wps/portal/NCTC/sanctionlist/unifiedsanctionlist/!ut/p/z1/jY_BDoIwAEM_aXUbIMdByLa4iZgRcBeyk1mi6MH4_RL16qS3Jq9tSjwZiZ_DM57DI97mcFn8yeeTLimnilPT1lygY5V2lllImZHhDWTKNJLvsJeFq9C1VLn8qCiwIX5NHj8ksC6fAHy6fiD-MyGsBuUwbVMvDaVyqmbA9lB8gdTFfyP3a9-PiPoFJNS7hg!!/dz/d5/L3dDZyEvUUZRSS9ZTlEh/p0/IZ7_I9242H42LOC4A0Q3BITM3M0G85=CZ6_I9242H42LOC4A0Q3BITM3M0GG5=NJgetSanctionList=/?lang=en&name=&qid=&passport=&listType=")

# User agent for downloads
USER_AGENT = "Mozilla/5.0 (compatible; CorridorComply/1.0; +https://github.com/Zezoo123/CorridorComply)"


def download_file(url: str, output_path: Path, timeout: int = 300) -> Tuple[bool, str]:
    """Download a file from a URL."""
    try:
        logger.info(f"Downloading from {url}...")
        headers = {'User-Agent': USER_AGENT}
        
        response = requests.get(url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and downloaded % (5 * 1024 * 1024) == 0:
                        percent = (downloaded / total_size) * 100
                        logger.info(f"  Downloaded {downloaded / 1024 / 1024:.1f} MB ({percent:.1f}%)")
        
        file_size = output_path.stat().st_size
        logger.info(f"✅ Downloaded {file_size / 1024 / 1024:.2f} MB to {output_path.name}")
        return True, f"Downloaded {file_size / 1024 / 1024:.2f} MB"
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to download {url}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error downloading {url}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def download_un_sanctions() -> Tuple[bool, Optional[Path]]:
    """Download UN consolidated sanctions list."""
    output_dir = RAW_DIR / "un"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d")
    temp_path = output_dir / f"un_consolidated_{timestamp}.xml"
    
    success, message = download_file(UN_URL, temp_path)
    if success:
        # Rename to expected filename for conversion script
        expected_path = output_dir / "consolidatedLegacyByPRN.xml"
        if expected_path.exists():
            expected_path.unlink()
        shutil.move(temp_path, expected_path)
        logger.info(f"Saved as: {expected_path.name}")
        return True, expected_path
    
    return False, None


def download_ofac_sanctions() -> Tuple[bool, list[Path]]:
    """Download OFAC sanctions lists (SDN, ALT, ADD)."""
    output_dir = RAW_DIR / "ofac"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    downloaded_files = []
    
    urls = [
        (OFAC_SDN_URL, "sdn.csv"),
        (OFAC_ALT_URL, "alt.csv"),
        (OFAC_ADD_URL, "add.csv")
    ]
    
    for url, filename in urls:
        output_path = output_dir / filename
        success, message = download_file(url, output_path)
        if success:
            downloaded_files.append(output_path)
        else:
            logger.warning(f"Failed to download {filename}: {message}")
    
    if downloaded_files:
        return True, downloaded_files
    return False, []


UK_CONLIST_URL = "https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.csv"


def download_uk_sanctions() -> Tuple[bool, Optional[Path]]:
    """Download the OFSI consolidated list (DOB, nationality, aliases); fall back to the search-service ODS."""
    output_dir = RAW_DIR / "uk"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")

    conlist_path = output_dir / f"ConList_{timestamp}.csv"
    ok, _ = download_file(UK_CONLIST_URL, conlist_path)
    if ok and conlist_path.stat().st_size > 1_000_000:
        for old in output_dir.glob("ConList_*.csv"):
            if old != conlist_path:
                old.unlink(missing_ok=True)
        return True, conlist_path
    logger.warning("OFSI ConList download failed or too small; falling back to the search-service ODS export")
    conlist_path.unlink(missing_ok=True)

    output_path = output_dir / f"uk_sanctions_{timestamp}.ods"
    
    try:
        logger.info("Downloading UK sanctions via API...")
        api_url = "https://search-uk-sanctions-list.service.gov.uk/api/report/ods"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "query": "",
            "filters": {},
            "sort": {
                "field": "name",
                "direction": "asc"
            }
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=300, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0 and downloaded % (5 * 1024 * 1024) == 0:
                        percent = (downloaded / total_size) * 100
                        logger.info(f"  Downloaded {downloaded / 1024 / 1024:.1f} MB ({percent:.1f}%)")
        
        file_size = output_path.stat().st_size
        logger.info(f"✅ Downloaded UK sanctions: {file_size / 1024 / 1024:.2f} MB to {output_path.name}")
        return True, output_path
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to download UK sanctions: {str(e)}"
        logger.error(error_msg)
        return False, None
    except Exception as e:
        error_msg = f"Unexpected error downloading UK sanctions: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, None


def download_eu_sanctions() -> Tuple[bool, Optional[Path]]:
    """Download EU sanctions file directly from the EU Financial Sanctions API."""
    output_dir = RAW_DIR / "eu"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d")
    output_path = output_dir / f"eu_sanctions_FULL_{timestamp}.csv"
    
    try:
        logger.info(f"Downloading EU sanctions from {EU_SANCTIONS_URL}...")
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/csv'
        }
        
        response = requests.get(EU_SANCTIONS_URL, headers=headers, stream=True, timeout=300)
        response.raise_for_status()
        
        # Create the output directory if it doesn't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save the file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verify the file was downloaded
        if not output_path.exists():
            logger.error("EU sanctions file was not downloaded successfully")
            return False, None
        
        file_size = output_path.stat().st_size
        if file_size == 0:
            logger.error("Downloaded EU sanctions file is empty")
            output_path.unlink(missing_ok=True)
            return False, None
        
        logger.info(f"✅ Successfully downloaded EU sanctions ({file_size / 1024 / 1024:.2f} MB)")
        return True, output_path
        
    except Exception as e:
        logger.error(f"Error downloading EU sanctions: {str(e)}", exc_info=True)
        return False, None


def download_qa_nctc() -> Tuple[bool, Optional[Path]]:
    """Download Qatar's NCTC unified sanction record (JSON from the MOI portal)."""
    output_dir = RAW_DIR / "qa_nctc"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"nctc_{datetime.now().strftime('%Y%m%d')}.json"
    ok, _ = download_file(QA_NCTC_URL, output_path)
    if not ok:
        return False, None
    try:
        import json
        data = json.loads(output_path.read_text(encoding="utf-8"))
        n = len(data.get("content", [])) if isinstance(data, dict) else 0
        if n < 100:
            logger.error(f"NCTC download looks wrong ({n} records); keeping the previous file")
            output_path.unlink(missing_ok=True)
            return False, None
        logger.info(f"NCTC unified record: {n} entries")
        for old in output_dir.glob("nctc_*.json"):
            if old != output_path:
                old.unlink(missing_ok=True)
        return True, output_path
    except Exception as e:
        logger.error(f"NCTC download is not valid JSON: {e}")
        output_path.unlink(missing_ok=True)
        return False, None


def run_conversion_script(script_name: str) -> bool:
    """Run a conversion script."""
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        logger.error(f"Conversion script not found: {script_path}")
        return False
    
    logger.info(f"Running conversion: {script_name}...")
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=600
        )
        logger.info(f"✅ {script_name} completed successfully")
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {script_name} timed out after 10 minutes")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ {script_name} failed with exit code {e.returncode}")
        if e.stderr:
            logger.error(f"Error: {e.stderr[:500]}")
        return False
    except Exception as e:
        logger.error(f"❌ Error running {script_name}: {str(e)}")
        return False


def update_sanctions_lists(force: bool = False) -> int:
    """
    Update all sanctions lists by downloading, converting, and combining.
    
    Args:
        force: If True, update even if files are recent
        
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    start_time = datetime.now()
    logger.info("="*70)
    logger.info("Starting Sanctions List Auto-Update")
    logger.info("="*70)
    logger.info(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")
    
    # Ensure directories exist
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
    COMBINED_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {'un': False, 'ofac': False, 'uk': False, 'eu': False, 'qa_nctc': False}
    
    # Download UN sanctions
    logger.info("\n" + "-"*70)
    logger.info("1. Downloading UN Sanctions")
    logger.info("-"*70)
    un_success, un_file = download_un_sanctions()
    results['un'] = un_success
    
    # Download OFAC sanctions
    logger.info("\n" + "-"*70)
    logger.info("2. Downloading OFAC Sanctions")
    logger.info("-"*70)
    ofac_success, ofac_files = download_ofac_sanctions()
    results['ofac'] = ofac_success
    
    # Download UK sanctions
    logger.info("\n" + "-"*70)
    logger.info("3. Downloading UK Sanctions")
    logger.info("-"*70)
    uk_success, uk_file = download_uk_sanctions()
    results['uk'] = uk_success
    
    # Download EU sanctions
    logger.info("\n" + "-"*70)
    logger.info("4. Downloading EU Sanctions")
    logger.info("-"*70)
    eu_success, eu_file = download_eu_sanctions()
    results['eu'] = eu_success
    
    # Download Qatar NCTC unified record
    logger.info("\n" + "-"*70)
    logger.info("4b. Downloading Qatar NCTC unified sanction record")
    logger.info("-"*70)
    nctc_success, _ = download_qa_nctc()
    results['qa_nctc'] = nctc_success

    # Run conversion scripts
    logger.info("\n" + "-"*70)
    logger.info("5. Converting Sanctions Lists")
    logger.info("-"*70)
    
    conversion_results = {}
    
    if results['un']:
        conversion_results['un'] = run_conversion_script("convert_un_to_csv.py")
    else:
        logger.warning("Skipping UN conversion (download failed)")
        conversion_results['un'] = False
    
    if results['ofac']:
        conversion_results['ofac'] = run_conversion_script("convert_ofac_to_csv.py")
    else:
        logger.warning("Skipping OFAC conversion (download failed)")
        conversion_results['ofac'] = False
    
    if results['uk']:
        conversion_results['uk'] = run_conversion_script("convert_uk_to_csv.py")
    else:
        logger.warning("Skipping UK conversion (no file available)")
        conversion_results['uk'] = False
    
    if results['eu']:
        conversion_results['eu'] = run_conversion_script("convert_eu_to_csv.py")
    else:
        logger.warning("Skipping EU conversion (no file available)")
        conversion_results['eu'] = False
    
    if results['qa_nctc']:
        conversion_results['qa_nctc'] = run_conversion_script("convert_qa_nctc_to_csv.py")
    else:
        logger.warning("Skipping Qatar NCTC conversion (download failed)")
        conversion_results['qa_nctc'] = False

    # Combine all sanctions
    logger.info("\n" + "-"*70)
    logger.info("6. Combining Sanctions Lists")
    logger.info("-"*70)
    
    combine_success = run_conversion_script("combine_sanctions.py")
    
    # Summary
    duration = (datetime.now() - start_time).total_seconds()
    logger.info("\n" + "="*70)
    logger.info("Update Summary")
    logger.info("="*70)
    logger.info(f"Total time: {duration:.2f} seconds ({duration/60:.1f} minutes)")
    logger.info("")
    logger.info("Download Results:")
    for source, success in results.items():
        status = "✅ Success" if success else "❌ Failed/Skipped"
        logger.info(f"  {source.upper():6s}: {status}")
    
    logger.info("")
    logger.info("Conversion Results:")
    for source, success in conversion_results.items():
        status = "✅ Success" if success else "❌ Failed/Skipped"
        logger.info(f"  {source.upper():6s}: {status}")
    
    logger.info("")
    logger.info(f"Combination: {'✅ Success' if combine_success else '❌ Failed'}")
    
    # Determine overall success
    critical_sources = ['un', 'ofac']
    critical_success = all(results.get(s) and conversion_results.get(s, False) for s in critical_sources)
    
    if critical_success and combine_success:
        logger.info("")
        logger.info("✅ Sanctions update completed successfully!")
        logger.info(f"Combined file available at: {COMBINED_DIR}")
        return 0
    else:
        logger.warning("")
        logger.warning("⚠️  Sanctions update completed with warnings")
        logger.warning("Some sources may not have been updated")
        return 1


def latest_combined_age_hours() -> Optional[float]:
    files = [f for f in COMBINED_DIR.glob("combined_sanctions_*.csv") if not f.is_symlink()]
    if not files:
        return None
    newest = max(f.stat().st_mtime for f in files)
    return (datetime.now().timestamp() - newest) / 3600


def main() -> int:
    """Command-line usage: update_sanctions.py [--max-age-hours N]

    With --max-age-hours, the update is skipped when the newest combined file
    is younger than N hours. Suitable for an hourly cron entry.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Download, convert and combine sanctions lists")
    parser.add_argument("--max-age-hours", type=float, default=None,
                        help="skip when the combined list is younger than this many hours")
    args = parser.parse_args()
    if args.max_age_hours is not None:
        age = latest_combined_age_hours()
        if age is not None and age < args.max_age_hours:
            logger.info(f"Combined list is {age:.1f}h old (< {args.max_age_hours}h); nothing to do")
            return 0
    return update_sanctions_lists(force=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\nUpdate interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
