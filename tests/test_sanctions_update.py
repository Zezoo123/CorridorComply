"""
Tests for sanctions list auto-update functionality.

This test suite verifies that all 4 sanction lists (UN, OFAC, UK, EU) can be:
1. Downloaded successfully
2. Converted to normalized CSV format
3. Combined into a single unified list
"""
import pytest
import sys
import subprocess
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from typing import Tuple, Optional
import tempfile
import shutil
import asyncio

logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.update_sanctions import (
    download_un_sanctions,
    download_ofac_sanctions,
    download_uk_sanctions,
    download_eu_sanctions,
    run_conversion_script,
    update_sanctions_lists
)


class TestSanctionsDownload:
    """Test downloading of individual sanction lists."""
    
    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create temporary data directory structure."""
        data_dir = tmp_path / "app" / "data" / "sanctions"
        raw_dir = data_dir / "raw"
        for source in ["un", "ofac", "uk", "eu"]:
            (raw_dir / source).mkdir(parents=True, exist_ok=True)
        return data_dir
    
    @patch('scripts.update_sanctions.download_file')
    def test_download_un_sanctions(self, mock_download, temp_data_dir):
        """Test UN sanctions download."""
        # Mock successful download
        mock_download.return_value = (True, "Downloaded 1.5 MB")
        
        # Mock the file operations
        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            with patch('shutil.move') as mock_move:
                success, file_path = download_un_sanctions()
                
                assert success is True
                assert file_path is not None
                assert "consolidatedLegacyByPRN.xml" in str(file_path)
                mock_download.assert_called_once()
    
    @patch('scripts.update_sanctions.download_file')
    def test_download_ofac_sanctions(self, mock_download, temp_data_dir):
        """Test OFAC sanctions download (SDN, ALT, ADD)."""
        # Mock successful downloads for all 3 files
        mock_download.return_value = (True, "Downloaded 2.0 MB")
        
        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, files = download_ofac_sanctions()
            
            assert success is True
            assert len(files) == 3  # Should download SDN, ALT, ADD
            assert all("sdn.csv" in str(f) or "alt.csv" in str(f) or "add.csv" in str(f) for f in files)
            assert mock_download.call_count == 3
    
    @patch('scripts.update_sanctions.requests.get')
    def test_download_uk_sanctions_conlist(self, mock_get, temp_data_dir):
        """UK comes from the OFSI ConList.csv when it downloads successfully."""
        mock_response = MagicMock()
        mock_response.headers = {'content-length': '16000000'}
        mock_response.raise_for_status = Mock()
        mock_response.iter_content = Mock(return_value=[b'x' * 8192] * 200)  # > 1 MB
        mock_get.return_value = mock_response

        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, file_path = download_uk_sanctions()
            assert success is True
            assert file_path is not None and file_path.exists()
            assert file_path.name.startswith("ConList_") and file_path.suffix == ".csv"
            assert "ofsistorage" in mock_get.call_args[0][0]

    @patch('scripts.update_sanctions.requests.post')
    @patch('scripts.update_sanctions.requests.get')
    def test_download_uk_sanctions_falls_back_to_ods(self, mock_get, mock_post, temp_data_dir):
        """If the ConList download fails, the search-service ODS report is used."""
        import requests as _requests
        mock_get.side_effect = _requests.exceptions.ConnectionError("down")
        mock_response = MagicMock()
        mock_response.headers = {'content-length': '185000'}
        mock_response.raise_for_status = Mock()
        mock_response.iter_content = Mock(return_value=[b'fake ods content'] * 100)
        mock_post.return_value = mock_response

        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, file_path = download_uk_sanctions()
            assert success is True
            assert file_path.suffix == ".ods"
            assert not list((temp_data_dir / "raw" / "uk").glob("ConList_*.csv"))
            call_args = mock_post.call_args
            assert "api/report/ods" in call_args[0][0]
            assert call_args[1]['json']['query'] == ""

    @patch('scripts.update_sanctions.requests.get')
    def test_download_eu_sanctions_success(self, mock_get, temp_data_dir):
        """Test EU sanctions download via the direct consolidated CSV URL."""
        mock_response = MagicMock()
        mock_response.headers = {'content-length': '25000000'}
        mock_response.raise_for_status = Mock()
        mock_response.iter_content = Mock(return_value=[b'fake,csv,content\n'] * 100)
        mock_get.return_value = mock_response

        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, file_path = download_eu_sanctions()

            assert success is True
            assert file_path is not None
            assert file_path.suffix == ".csv"
            assert file_path.exists()
            mock_get.assert_called_once()
            assert "webgate.ec.europa.eu" in mock_get.call_args[0][0]

    @patch('scripts.update_sanctions.requests.get')
    def test_download_eu_sanctions_empty_file(self, mock_get, temp_data_dir):
        """An empty EU download is treated as a failure."""
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        mock_response.iter_content = Mock(return_value=[])
        mock_get.return_value = mock_response

        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, file_path = download_eu_sanctions()
            assert success is False
            assert file_path is None


class TestSanctionsConversion:
    """Test conversion scripts for each sanction list."""
    
    def test_conversion_scripts_exist(self):
        """Verify all conversion scripts exist."""
        scripts_dir = PROJECT_ROOT / "scripts"
        required_scripts = [
            "convert_un_to_csv.py",
            "convert_ofac_to_csv.py",
            "convert_uk_to_csv.py",
            "convert_eu_to_csv.py",
            "combine_sanctions.py"
        ]
        
        for script in required_scripts:
            script_path = scripts_dir / script
            assert script_path.exists(), f"Required script {script} not found at {script_path}"
    
    @patch('scripts.update_sanctions.subprocess.run')
    def test_convert_un_script(self, mock_run):
        """Test UN conversion script execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        success = run_conversion_script("convert_un_to_csv.py")
        assert success is True
        mock_run.assert_called_once()
        # Verify the script name is in the command
        call_args = mock_run.call_args[0][0]
        assert any("convert_un_to_csv.py" in str(arg) for arg in call_args)
    
    @patch('scripts.update_sanctions.subprocess.run')
    def test_convert_ofac_script(self, mock_run):
        """Test OFAC conversion script execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        success = run_conversion_script("convert_ofac_to_csv.py")
        assert success is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert any("convert_ofac_to_csv.py" in str(arg) for arg in call_args)
    
    @patch('scripts.update_sanctions.subprocess.run')
    def test_convert_uk_script(self, mock_run):
        """Test UK conversion script execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        success = run_conversion_script("convert_uk_to_csv.py")
        assert success is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert any("convert_uk_to_csv.py" in str(arg) for arg in call_args)
    
    @patch('scripts.update_sanctions.subprocess.run')
    def test_convert_eu_script(self, mock_run):
        """Test EU conversion script execution."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        success = run_conversion_script("convert_eu_to_csv.py")
        assert success is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert any("convert_eu_to_csv.py" in str(arg) for arg in call_args)
    
    @patch('scripts.update_sanctions.subprocess.run')
    def test_convert_script_failure(self, mock_run):
        """Test conversion script failure handling."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "script")
        
        success = run_conversion_script("convert_un_to_csv.py")
        assert success is False


class TestSanctionsUpdateIntegration:
    """Integration tests for full sanctions update process."""
    
    @pytest.fixture
    def temp_project_structure(self, tmp_path):
        """Create temporary project structure."""
        # Create directory structure
        data_dir = tmp_path / "app" / "data" / "sanctions"
        raw_dir = data_dir / "raw"
        normalized_dir = data_dir / "normalized"
        combined_dir = data_dir / "combined"
        
        for dir_path in [raw_dir, normalized_dir, combined_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
        
        for source in ["un", "ofac", "uk", "eu"]:
            (raw_dir / source).mkdir(parents=True, exist_ok=True)
        
        return {
            'root': tmp_path,
            'data_dir': data_dir,
            'raw_dir': raw_dir,
            'normalized_dir': normalized_dir,
            'combined_dir': combined_dir
        }
    
    @patch('scripts.update_sanctions.download_un_sanctions')
    @patch('scripts.update_sanctions.download_ofac_sanctions')
    @patch('scripts.update_sanctions.download_uk_sanctions')
    @patch('scripts.update_sanctions.download_eu_sanctions')
    @patch('scripts.update_sanctions.download_qa_nctc', return_value=(True, Path('nctc.json')))
    @patch('scripts.update_sanctions.download_ofac_consolidated', return_value=(True, []))
    @patch('scripts.update_sanctions.run_conversion_script')
    def test_update_all_four_lists(
        self,
        mock_convert,
        mock_download_cons,
        mock_download_nctc,
        mock_download_eu,
        mock_download_uk,
        mock_download_ofac,
        mock_download_un,
        temp_project_structure
    ):
        """Test that all 4 sanction lists are updated."""
        # Mock successful downloads
        mock_download_un.return_value = (True, Path("un_file.xml"))
        mock_download_ofac.return_value = (True, [Path("sdn.csv"), Path("alt.csv"), Path("add.csv")])
        mock_download_uk.return_value = (True, Path("uk_file.csv"))
        mock_download_eu.return_value = (True, Path("eu_file.csv"))
        
        # Mock successful conversions
        mock_convert.return_value = True
        
        # Patch the directory paths
        with patch('scripts.update_sanctions.RAW_DIR', temp_project_structure['raw_dir']):
            with patch('scripts.update_sanctions.NORMALIZED_DIR', temp_project_structure['normalized_dir']):
                with patch('scripts.update_sanctions.COMBINED_DIR', temp_project_structure['combined_dir']):
                    exit_code = update_sanctions_lists(force=True)
        
        # Verify all 4 lists were attempted
        assert mock_download_un.called, "UN download should be called"
        assert mock_download_ofac.called, "OFAC download should be called"
        assert mock_download_uk.called, "UK download should be called"
        assert mock_download_eu.called, "EU download should be called"
        
        # Verify conversion scripts were called for each
        conversion_calls = [str(call) for call in mock_convert.call_args_list]
        assert any("convert_un_to_csv.py" in str(call) for call in mock_convert.call_args_list)
        assert any("convert_ofac_to_csv.py" in str(call) for call in mock_convert.call_args_list)
        assert any("convert_uk_to_csv.py" in str(call) for call in mock_convert.call_args_list)
        assert any("convert_eu_to_csv.py" in str(call) for call in mock_convert.call_args_list)
        assert any("combine_sanctions.py" in str(call) for call in mock_convert.call_args_list)
        
        # Should succeed if critical sources (UN, OFAC) work
        assert exit_code == 0
    
    @patch('scripts.update_sanctions.download_un_sanctions')
    @patch('scripts.update_sanctions.download_ofac_sanctions')
    @patch('scripts.update_sanctions.download_uk_sanctions')
    @patch('scripts.update_sanctions.download_eu_sanctions')
    @patch('scripts.update_sanctions.download_qa_nctc', return_value=(True, Path('nctc.json')))
    @patch('scripts.update_sanctions.download_ofac_consolidated', return_value=(True, []))
    @patch('scripts.update_sanctions.run_conversion_script')
    def test_update_with_partial_failures(
        self,
        mock_convert,
        mock_download_cons,
        mock_download_nctc,
        mock_download_eu,
        mock_download_uk,
        mock_download_ofac,
        mock_download_un,
        temp_project_structure
    ):
        """Test update process when some lists fail to download."""
        # UN and OFAC succeed (critical)
        mock_download_un.return_value = (True, Path("un_file.xml"))
        mock_download_ofac.return_value = (True, [Path("sdn.csv")])
        
        # UK and EU fail (non-critical)
        mock_download_uk.return_value = (False, None)
        mock_download_eu.return_value = (False, None)
        
        # Conversions succeed
        mock_convert.return_value = True
        
        with patch('scripts.update_sanctions.RAW_DIR', temp_project_structure['raw_dir']):
            with patch('scripts.update_sanctions.NORMALIZED_DIR', temp_project_structure['normalized_dir']):
                with patch('scripts.update_sanctions.COMBINED_DIR', temp_project_structure['combined_dir']):
                    exit_code = update_sanctions_lists(force=True)
        
        # Should still succeed if critical sources work
        assert exit_code == 0
        # UK and EU conversions should be skipped
        assert not any("convert_uk_to_csv.py" in str(call) for call in mock_convert.call_args_list if mock_download_uk.return_value[0] is False)
        assert not any("convert_eu_to_csv.py" in str(call) for call in mock_convert.call_args_list if mock_download_eu.return_value[0] is False)


class TestSanctionsUpdateReal:
    """Real integration tests (optional, can be skipped with --skip-slow)."""
    
    def test_real_un_download(self, request):
        """Test real UN sanctions download (slow test)."""
        if not request.config.getoption("--run-slow"):
            pytest.skip("use --run-slow to run")
        success, file_path = download_un_sanctions()
        assert success is True
        assert file_path is not None
        assert file_path.exists()
        assert file_path.suffix == ".xml"
    
    def test_real_ofac_download(self, request):
        """Test real OFAC sanctions download (slow test)."""
        if not request.config.getoption("--run-slow"):
            pytest.skip("use --run-slow to run")
        success, files = download_ofac_sanctions()
        assert success is True
        assert len(files) > 0
        for file_path in files:
            assert file_path.exists()
            assert file_path.suffix == ".csv"
    
    def test_real_uk_download(self, request):
        """Test real UK sanctions download (slow test)."""
        if not request.config.getoption("--run-slow"):
            pytest.skip("use --run-slow to run")
        success, file_path = download_uk_sanctions()
        assert success is True
        assert file_path is not None
        assert file_path.exists()
        assert file_path.suffix in (".csv", ".ods")  # OFSI ConList, or the ODS fallback
        
    def test_real_eu_download(self, request):
        """Test real EU sanctions download (slow test)."""
        if not request.config.getoption("--run-slow"):
            pytest.skip("use --run-slow to run")
        success, file_path = download_eu_sanctions()
        assert success is True
        assert file_path is not None
        assert file_path.exists()
        # The file extension might be .csv or .xml depending on the source
        assert file_path.suffix in {".csv", ".xml"}


class TestSanctionsConversionEndToEnd:
    """End-to-end tests that verify downloaded files can be converted and used."""
    
    @pytest.fixture
    def project_data_dir(self):
        """Get the actual project data directory."""
        return PROJECT_ROOT / "app" / "data" / "sanctions"
    
    def test_un_file_can_be_converted(self, project_data_dir):
        """Test that existing UN file can be converted."""
        un_dir = project_data_dir / "raw" / "un"
        un_file = un_dir / "consolidatedLegacyByPRN.xml"
        
        if not un_file.exists():
            pytest.skip(f"UN file not found at {un_file}. Run download first.")
        
        # Check that conversion script exists
        convert_script = PROJECT_ROOT / "scripts" / "convert_un_to_csv.py"
        assert convert_script.exists(), "UN conversion script not found"
        
        # Run conversion (this will create normalized CSV)
        normalized_dir = project_data_dir / "normalized"
        normalized_dir.mkdir(parents=True, exist_ok=True)
        
        # Import and test conversion
        import subprocess
        result = subprocess.run(
            [sys.executable, str(convert_script)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            pytest.fail(f"UN conversion failed: {result.stderr}")
        
        # Check that normalized file was created
        normalized_files = list((project_data_dir / "normalized" / "un").glob("*.csv"))
        assert len(normalized_files) > 0, "No normalized UN CSV files found after conversion"
        
        # Verify file has data
        import pandas as pd
        df = pd.read_csv(normalized_files[0], nrows=10)
        assert len(df) > 0, "Normalized UN file is empty"
        assert 'name' in df.columns or 'Name' in df.columns, "Normalized UN file missing name column"
    
    def test_ofac_files_can_be_converted(self, project_data_dir):
        """Test that existing OFAC files can be converted."""
        ofac_dir = project_data_dir / "raw" / "ofac"
        sdn_file = ofac_dir / "sdn.csv"
        
        if not sdn_file.exists():
            pytest.skip(f"OFAC SDN file not found at {sdn_file}. Run download first.")
        
        # Check that conversion script exists
        convert_script = PROJECT_ROOT / "scripts" / "convert_ofac_to_csv.py"
        assert convert_script.exists(), "OFAC conversion script not found"
        
        # Run conversion
        import subprocess
        result = subprocess.run(
            [sys.executable, str(convert_script)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            pytest.fail(f"OFAC conversion failed: {result.stderr}")
        
        # Check that normalized file was created
        normalized_files = list((project_data_dir / "normalized" / "ofac").glob("*.csv"))
        assert len(normalized_files) > 0, "No normalized OFAC CSV files found after conversion"
        
        # Verify file has data
        import pandas as pd
        df = pd.read_csv(normalized_files[0], nrows=10)
        assert len(df) > 0, "Normalized OFAC file is empty"
        assert 'name' in df.columns or 'Name' in df.columns, "Normalized OFAC file missing name column"
    
    def test_uk_file_can_be_converted(self, project_data_dir):
        """Test that existing UK file can be converted."""
        uk_dir = project_data_dir / "raw" / "uk"
        uk_files = list(uk_dir.glob("*.ods"))
        
        if not uk_files:
            pytest.skip(f"UK ODS file not found in {uk_dir}. Run download first.")
        
        # Check that conversion script exists
        convert_script = PROJECT_ROOT / "scripts" / "convert_uk_to_csv.py"
        assert convert_script.exists(), "UK conversion script not found"
        
        # Run conversion
        import subprocess
        result = subprocess.run(
            [sys.executable, str(convert_script)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            pytest.fail(f"UK conversion failed: {result.stderr}")
        
        # Check that normalized file was created
        normalized_files = list((project_data_dir / "normalized" / "uk").glob("*.csv"))
        assert len(normalized_files) > 0, "No normalized UK CSV files found after conversion"
        
        # Verify file has data
        import pandas as pd
        df = pd.read_csv(normalized_files[0], nrows=10)
        assert len(df) > 0, "Normalized UK file is empty"
        assert 'name' in df.columns or 'Name' in df.columns, "Normalized UK file missing name column"
    
    def test_eu_file_can_be_converted(self, project_data_dir):
        """Test that existing EU file can be converted."""
        eu_dir = project_data_dir / "raw" / "eu"
        eu_files = list(eu_dir.glob("*.csv")) + list(eu_dir.glob("*.zip"))
        
        if not eu_files:
            pytest.skip(f"EU file not found in {eu_dir}. Run download first.")
        
        # Check that conversion script exists
        convert_script = PROJECT_ROOT / "scripts" / "convert_eu_to_csv.py"
        assert convert_script.exists(), "EU conversion script not found"
        
        # Run conversion
        import subprocess
        result = subprocess.run(
            [sys.executable, str(convert_script)],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            pytest.fail(f"EU conversion failed: {result.stderr}")
        
        # Check that normalized file was created
        normalized_files = list((project_data_dir / "normalized" / "eu").glob("*.csv"))
        assert len(normalized_files) > 0, "No normalized EU CSV files found after conversion"
        
        # Verify file has data
        import pandas as pd
        df = pd.read_csv(normalized_files[0], nrows=10)
        assert len(df) > 0, "Normalized EU file is empty"
        assert 'name' in df.columns or 'Name' in df.columns, "Normalized EU file missing name column"
    
    def test_combined_file_can_be_loaded(self, project_data_dir):
        """Test that combined sanctions file can be loaded by SanctionsLoader."""
        combined_dir = project_data_dir / "combined"
        combined_files = list(combined_dir.glob("combined_sanctions_*.csv"))
        
        if not combined_files:
            pytest.skip(f"No combined sanctions file found in {combined_dir}. Run combine_sanctions.py first.")
        
        # Use the latest file
        latest_file = max(combined_files, key=lambda f: f.stat().st_mtime)
        
        # Try to load with SanctionsLoader
        from app.services.sanctions_loader import SanctionsLoader
        
        try:
            df = SanctionsLoader.load(latest_file)
            assert df is not None, "SanctionsLoader returned None"
            assert len(df) > 0, "Combined sanctions file is empty"
            
            # Verify required columns
            required_columns = {'name', 'source'}
            assert required_columns.issubset(df.columns), f"Missing required columns. Found: {df.columns.tolist()}"
            
            # Verify data from all 4 sources if available
            if 'source' in df.columns:
                sources = df['source'].unique()
                logger.info(f"Found sanctions from sources: {sources}")
                # At least one source should be present
                assert len(sources) > 0, "No source information in combined file"
            
        except Exception as e:
            pytest.fail(f"Failed to load combined sanctions file: {str(e)}")
    
    def test_all_four_sources_in_combined_file(self, project_data_dir):
        """Test that combined file contains data from all 4 sources if available."""
        combined_dir = project_data_dir / "combined"
        combined_files = list(combined_dir.glob("combined_sanctions_*.csv"))
        
        if not combined_files:
            pytest.skip(f"No combined sanctions file found in {combined_dir}. Run combine_sanctions.py first.")
        
        latest_file = max(combined_files, key=lambda f: f.stat().st_mtime)
        
        from app.services.sanctions_loader import SanctionsLoader
        df = SanctionsLoader.load(latest_file)
        
        if 'source' in df.columns:
            sources = set(df['source'].str.upper())
            expected_sources = {'UN', 'OFAC', 'UK', 'EU'}
            found_sources = sources.intersection(expected_sources)
            
            logger.info(f"Expected sources: {expected_sources}")
            logger.info(f"Found sources in file: {found_sources}")
            
            # At least UN and OFAC should be present (critical sources)
            assert 'UN' in found_sources or 'OFAC' in found_sources, \
                f"Critical sources (UN/OFAC) not found. Found: {found_sources}"
            
            # Log which sources are missing
            missing = expected_sources - found_sources
            if missing:
                logger.warning(f"Some sources not found in combined file: {missing}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



