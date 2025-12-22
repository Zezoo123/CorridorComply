# Sanctions List Auto-Update

## Overview

The system automatically checks and updates sanctions lists when the API server starts. This ensures your sanctions data stays current without manual intervention.

## How It Works

### Automatic Update on Server Startup

When the API server starts, it:

1. **Checks the age of the latest combined sanctions file**
   - Looks in `app/data/sanctions/combined/` for the most recent `combined_sanctions_*.csv` file
   - Calculates how many days old the file is

2. **Compares against update interval**
   - Default: 7 days (configurable via `SANCTIONS_UPDATE_INTERVAL_DAYS`)
   - If file is older than the threshold → triggers update
   - If file is newer → skips update

3. **Runs update in background** (if needed)
   - Downloads fresh UN and OFAC lists
   - Checks for UK/EU files (manual download)
   - Converts all lists to normalized format
   - Combines into single unified list
   - Clears cache so new data is used

4. **Non-blocking**
   - Update runs in a background thread
   - Server starts immediately (doesn't wait for update)
   - Update completes in background

## Configuration

### Environment Variables

Set these in your environment or `.env` file:

```bash
# Enable/disable auto-update (default: true)
SANCTIONS_AUTO_UPDATE_ENABLED=true

# Update interval in days (default: 7)
SANCTIONS_UPDATE_INTERVAL_DAYS=7
```

### Disable Auto-Update

To disable automatic updates:

```bash
export SANCTIONS_AUTO_UPDATE_ENABLED=false
```

Or set in `.env`:
```
SANCTIONS_AUTO_UPDATE_ENABLED=false
```

## Manual Update

You can also run the update script manually:

```bash
python3 scripts/update_sanctions.py
```

Or force an update regardless of file age:

```python
from scripts.update_sanctions import update_sanctions_lists
update_sanctions_lists(force=True)
```

## Update Process

The update script performs these steps:

1. **Downloads UN sanctions** (XML format)
   - URL: `https://scsanctions.un.org/resources/xml/en/consolidated.xml`
   - Saves to: `app/data/sanctions/raw/un/consolidatedLegacyByPRN.xml`

2. **Downloads OFAC sanctions** (CSV format)
   - SDN list: `https://www.treasury.gov/ofac/downloads/sdn.csv`
   - ALT list: `https://www.treasury.gov/ofac/downloads/alt.csv`
   - ADD list: `https://www.treasury.gov/ofac/downloads/add.csv`
   - Saves to: `app/data/sanctions/raw/ofac/`

3. **Checks UK sanctions** (requires manual download)
   - Looks for existing ODS files in `app/data/sanctions/raw/uk/`
   - Provides instructions if file not found or too old

4. **Checks EU sanctions** (requires manual download)
   - Looks for existing CSV files in `app/data/sanctions/raw/eu/`
   - Provides instructions if file not found or too old

5. **Converts all lists** to normalized CSV format
   - Runs: `convert_un_to_csv.py`
   - Runs: `convert_ofac_to_csv.py`
   - Runs: `convert_uk_to_csv.py` (if file available)
   - Runs: `convert_eu_to_csv.py` (if file available)

6. **Combines all lists** into single file
   - Runs: `combine_sanctions.py`
   - Output: `app/data/sanctions/combined/combined_sanctions_YYYYMMDD_HHMMSS.csv`

## Example Startup Log

When the server starts, you'll see logs like:

```
INFO: Checking if sanctions lists need updating...
INFO: Sanctions lists are 8.5 days old (threshold: 7 days)
INFO: Starting automatic sanctions list update...
INFO: Sanctions update running in background...
```

Or if up to date:

```
INFO: Checking if sanctions lists need updating...
INFO: Sanctions lists are up to date (age: 3.2 days)
```

## Benefits

1. **Automatic**: No manual intervention needed
2. **Non-blocking**: Server starts immediately
3. **Configurable**: Adjust update frequency as needed
4. **Safe**: Update failures don't crash the server
5. **Efficient**: Only updates when needed (based on file age)

## Troubleshooting

### Update Not Running

1. Check if auto-update is enabled:
   ```bash
   echo $SANCTIONS_AUTO_UPDATE_ENABLED
   ```

2. Check server logs for update messages

3. Verify the update script exists:
   ```bash
   ls -la scripts/update_sanctions.py
   ```

### Update Failing

1. Check network connectivity (for UN/OFAC downloads)
2. Verify `requests` library is installed: `pip install requests`
3. Check logs in `sanctions_update.log`
4. Manually run the script to see detailed errors:
   ```bash
   python3 scripts/update_sanctions.py
   ```

### UK/EU Downloads Failing

UK and EU downloads use Playwright browser automation. If they fail:

1. **Install Playwright**:
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **Check browser installation**:
   ```bash
   playwright --version
   ```

3. **Run manually to see detailed errors**:
   ```bash
   python3 scripts/update_sanctions.py
   ```

4. **Update selectors if website changes**: The script tries multiple selectors, but if the website structure changes, you may need to update the selectors in `download_uk_sanctions_async()` or `download_eu_sanctions_async()` functions.

## Alternative: Cron Scheduling

If you prefer scheduled updates instead of startup checks, you can use cron:

```bash
# Run every Monday at 2 AM
0 2 * * 1 cd /path/to/CorridorComply && /usr/bin/python3 scripts/update_sanctions.py >> logs/sanctions_update_cron.log 2>&1
```

Then disable auto-update on startup:
```bash
export SANCTIONS_AUTO_UPDATE_ENABLED=false
```

## Testing

Comprehensive tests are available to verify that all 4 sanction lists can be updated:

### Run All Tests

```bash
# Run all sanctions update tests (fast, uses mocks)
pytest tests/test_sanctions_update.py -v

# Run with real downloads (slow, requires internet)
pytest tests/test_sanctions_update.py -v --run-slow
```

### Test Coverage

The test suite (`tests/test_sanctions_update.py`) verifies:

1. **Download Tests** (mocked):
   - ✅ UN sanctions download
   - ✅ OFAC sanctions download (SDN, ALT, ADD)
   - ✅ UK sanctions download (Playwright)
   - ✅ EU sanctions download (Playwright)

2. **Conversion Tests**:
   - ✅ All conversion scripts exist
   - ✅ UN conversion script execution
   - ✅ OFAC conversion script execution
   - ✅ UK conversion script execution
   - ✅ EU conversion script execution
   - ✅ Error handling for failed conversions

3. **Integration Tests**:
   - ✅ Full update process for all 4 lists
   - ✅ Partial failure handling (some lists fail)
   - ✅ Critical sources (UN, OFAC) must succeed

4. **Real Download Tests** (optional, slow):
   - ✅ Real UN download (use `--run-slow`)
   - ✅ Real OFAC download (use `--run-slow`)

### Test Structure

```
tests/test_sanctions_update.py
├── TestSanctionsDownload      # Tests individual downloads
├── TestSanctionsConversion    # Tests conversion scripts
├── TestSanctionsUpdateIntegration  # Full integration tests
└── TestSanctionsUpdateReal    # Real download tests (optional)
```

### Example Test Output

```bash
$ pytest tests/test_sanctions_update.py -v

tests/test_sanctions_update.py::TestSanctionsDownload::test_download_un_sanctions PASSED
tests/test_sanctions_update.py::TestSanctionsDownload::test_download_ofac_sanctions PASSED
tests/test_sanctions_update.py::TestSanctionsDownload::test_download_uk_sanctions PASSED
tests/test_sanctions_update.py::TestSanctionsDownload::test_download_eu_sanctions PASSED
tests/test_sanctions_update.py::TestSanctionsConversion::test_conversion_scripts_exist PASSED
tests/test_sanctions_update.py::TestSanctionsConversion::test_convert_un_script PASSED
tests/test_sanctions_update.py::TestSanctionsConversion::test_convert_ofac_script PASSED
tests/test_sanctions_update.py::TestSanctionsConversion::test_convert_uk_script PASSED
tests/test_sanctions_update.py::TestSanctionsConversion::test_convert_eu_script PASSED
tests/test_sanctions_update.py::TestSanctionsUpdateIntegration::test_update_all_four_lists PASSED
tests/test_sanctions_update.py::TestSanctionsUpdateIntegration::test_update_with_partial_failures PASSED
```

## Summary

The auto-update system ensures your sanctions lists stay current by:
- ✅ Checking file age on server startup
- ✅ Automatically downloading fresh UN, OFAC, UK, and EU lists
- ✅ Using Playwright for automated browser-based downloads (UK/EU)
- ✅ Running updates in background (non-blocking)
- ✅ Configurable update interval
- ✅ Safe error handling (won't crash server)
- ✅ Comprehensive test coverage for all 4 lists

**Fully automated** - no manual intervention needed! Just start your server and all lists update automatically when needed.

### Requirements

For full automation, ensure Playwright is installed:
```bash
pip install playwright
playwright install chromium
```
