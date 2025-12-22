#!/usr/bin/env python3
"""
Auto-update script for sanctions lists.

This script automatically downloads fresh sanctions lists from:
- UN: https://scsanctions.un.org/resources/xml/en/consolidated.xml
- OFAC: https://www.treasury.gov/ofac/downloads/sdn.csv (and alt.csv, add.csv)
- UK: https://search-uk-sanctions-list.service.gov.uk/ (automated via Playwright)
- EU: https://data.europa.eu/data/datasets/... (automated via Playwright)

Then converts and combines them into a single unified list.

Can be run manually, scheduled via cron, or called from API startup.
Requires Playwright for UK/EU downloads: pip install playwright && playwright install chromium
"""

import requests
import logging
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import subprocess
import asyncio
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

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

# UK and EU require more complex handling
UK_SANCTIONS_URL = "https://search-uk-sanctions-list.service.gov.uk/"
EU_SANCTIONS_URL = "https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions?locale=en"

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


async def download_uk_sanctions_async() -> Tuple[bool, Optional[Path]]:
    """Download UK sanctions file using Playwright."""
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available. Install with: pip install playwright && playwright install chromium")
        return False, None
    
    output_dir = RAW_DIR / "uk"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            
            logger.info(f"Navigating to {UK_SANCTIONS_URL}...")
            await page.goto(UK_SANCTIONS_URL, wait_until="networkidle", timeout=30000)
            
            logger.info("Waiting for download link...")
            await page.wait_for_selector("a.app-download-link", timeout=30000)
            
            timestamp = datetime.now().strftime("%Y%m%d")
            output_path = output_dir / f"uk_sanctions_{timestamp}.csv"
            
            async with page.expect_download(timeout=60000) as download_info:
                await page.click("a.app-download-link")
            
            download = await download_info.value
            await download.save_as(output_path)
            
            await browser.close()
            
            if output_path.exists():
                file_size = output_path.stat().st_size
                logger.info(f"✅ Downloaded UK sanctions: {file_size / 1024 / 1024:.2f} MB to {output_path.name}")
                return True, output_path
            else:
                logger.error("Download completed but file not found")
                return False, None
                
    except Exception as e:
        logger.error(f"Failed to download UK sanctions: {str(e)}", exc_info=True)
        return False, None


def download_uk_sanctions() -> Tuple[bool, Optional[Path]]:
    """Download UK sanctions file (synchronous wrapper)."""
    try:
        return asyncio.run(download_uk_sanctions_async())
    except Exception as e:
        logger.error(f"Error in UK download: {str(e)}")
        return False, None


async def download_eu_sanctions_async() -> Tuple[bool, Optional[Path]]:
    """Download EU sanctions file using Playwright."""
    if not PLAYWRIGHT_AVAILABLE:
        logger.error("Playwright not available. Install with: pip install playwright && playwright install chromium")
        return False, None
    
    output_dir = RAW_DIR / "eu"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(accept_downloads=True)
            page = await context.new_page()
            
            logger.info(f"Navigating to {EU_SANCTIONS_URL}...")
            await page.goto(EU_SANCTIONS_URL, wait_until="networkidle", timeout=30000)
            
            # Wait a bit for page to fully load
            await page.wait_for_timeout(2000)
            
            # Look for download button/link - common patterns for EU data portal
            # Try multiple selectors that might be used
            download_selectors = [
                "a[href*='download']",
                "a[href*='.csv']",
                "a[href*='.zip']",
                "button[aria-label*='download' i]",
                "button:has-text('Download')",
                ".download-button",
                "a:has-text('Download')",
                "a:has-text('CSV')",
                "a:has-text('Download dataset')",
                "[data-testid*='download']"
            ]
            
            download_clicked = False
            output_path = None
            timestamp = datetime.now().strftime("%Y%m%d")
            
            for selector in download_selectors:
                try:
                    logger.info(f"Trying selector: {selector}")
                    element = await page.wait_for_selector(selector, timeout=10000, state="visible")
                    if element:
                        # Check if it's a CSV or ZIP file
                        href = await element.get_attribute("href")
                        if href and (".csv" in href.lower() or ".zip" in href.lower()):
                            output_path = output_dir / f"eu_sanctions_FULL_{timestamp}.csv"
                            if ".zip" in href.lower():
                                output_path = output_dir / f"eu_sanctions_FULL_{timestamp}.zip"
                            
                            async with page.expect_download(timeout=60000) as download_info:
                                await element.click()
                            
                            download = await download_info.value
                            await download.save_as(output_path)
                            download_clicked = True
                            logger.info(f"Downloaded via selector: {selector}")
                            break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {str(e)}")
                    continue
            
            # If no download button found, try to find direct links on the page
            if not download_clicked:
                logger.info("No download button found, searching for direct CSV/ZIP links...")
                links = await page.query_selector_all("a[href]")
                for link in links:
                    href = await link.get_attribute("href")
                    if href and (".csv" in href.lower() or (".zip" in href.lower() and "sanction" in href.lower())):
                        full_url = href if href.startswith("http") else f"{EU_SANCTIONS_URL.rstrip('/')}/{href.lstrip('/')}"
                        logger.info(f"Found direct link: {full_url}")
                        # Use requests to download directly
                        try:
                            response = requests.get(full_url, timeout=300, stream=True)
                            response.raise_for_status()
                            output_path = output_dir / f"eu_sanctions_FULL_{timestamp}.csv"
                            if ".zip" in href.lower():
                                output_path = output_dir / f"eu_sanctions_FULL_{timestamp}.zip"
                            
                            with open(output_path, 'wb') as f:
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                            download_clicked = True
                            logger.info(f"Downloaded via direct link")
                            break
                        except Exception as e:
                            logger.debug(f"Direct link download failed: {str(e)}")
                            continue
            
            await browser.close()
            
            if download_clicked and output_path and output_path.exists():
                file_size = output_path.stat().st_size
                logger.info(f"✅ Downloaded EU sanctions: {file_size / 1024 / 1024:.2f} MB to {output_path.name}")
                return True, output_path
            else:
                logger.warning("Could not download EU sanctions automatically. You may need to update the selectors.")
                return False, None
                
    except Exception as e:
        logger.error(f"Failed to download EU sanctions: {str(e)}", exc_info=True)
        return False, None


def download_eu_sanctions() -> Tuple[bool, Optional[Path]]:
    """Download EU sanctions file (synchronous wrapper)."""
    try:
        return asyncio.run(download_eu_sanctions_async())
    except Exception as e:
        logger.error(f"Error in EU download: {str(e)}")
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
    
    results = {'un': False, 'ofac': False, 'uk': False, 'eu': False}
    
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


def main() -> int:
    """Main function for command-line usage."""
    return update_sanctions_lists(force=False)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.info("\nUpdate interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)
