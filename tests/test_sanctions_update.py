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
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
from typing import Tuple, Optional
import tempfile
import shutil
import asyncio

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
    
    @patch('scripts.update_sanctions.PLAYWRIGHT_AVAILABLE', False)
    def test_download_uk_sanctions_no_playwright(self, temp_data_dir):
        """Test UK sanctions download when Playwright is not available."""
        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, file_path = download_uk_sanctions()
            # Should return False when Playwright is not available
            assert success is False
            assert file_path is None
    
    @patch('scripts.update_sanctions.PLAYWRIGHT_AVAILABLE', True)
    @patch('asyncio.run')
    def test_download_uk_sanctions_with_playwright(self, mock_run, temp_data_dir):
        """Test UK sanctions download when Playwright is available."""
        # Mock asyncio.run to return success
        mock_run.return_value = (True, temp_data_dir / "raw" / "uk" / "test.csv")
        
        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, file_path = download_uk_sanctions()
            # Should call asyncio.run with the async function
            assert mock_run.called
            assert success is True
            assert file_path is not None
    
    @patch('scripts.update_sanctions.PLAYWRIGHT_AVAILABLE', False)
    def test_download_eu_sanctions_no_playwright(self, temp_data_dir):
        """Test EU sanctions download when Playwright is not available."""
        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, file_path = download_eu_sanctions()
            # Should return False when Playwright is not available
            assert success is False
            assert file_path is None
    
    @patch('scripts.update_sanctions.PLAYWRIGHT_AVAILABLE', True)
    @patch('asyncio.run')
    def test_download_eu_sanctions_with_playwright(self, mock_run, temp_data_dir):
        """Test EU sanctions download when Playwright is available."""
        # Mock asyncio.run to return success
        mock_run.return_value = (True, temp_data_dir / "raw" / "eu" / "test.csv")
        
        with patch('scripts.update_sanctions.RAW_DIR', temp_data_dir / "raw"):
            success, file_path = download_eu_sanctions()
            # Should call asyncio.run with the async function
            assert mock_run.called
            assert success is True
            assert file_path is not None


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
    @patch('scripts.update_sanctions.run_conversion_script')
    def test_update_all_four_lists(
        self,
        mock_convert,
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
    @patch('scripts.update_sanctions.run_conversion_script')
    def test_update_with_partial_failures(
        self,
        mock_convert,
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
