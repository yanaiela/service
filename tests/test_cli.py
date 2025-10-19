"""
Tests for CLI functionality.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, Mock
from pathlib import Path

from service.cli import main
from service.pdf_checker import PDFCheckResult, PaperType, Issue, IssueType


class TestCLI:
    
    def setup_method(self):
        self.runner = CliRunner()
    
    @patch('service.cli.PDFChecker')
    @patch('pathlib.Path.is_file')
    def test_check_pdf_single_file(self, mock_is_file, mock_pdf_checker_class):
        """Test checking a single PDF file."""
        mock_is_file.return_value = True
        
        # Mock the PDFChecker instance and its methods
        mock_checker = Mock()
        mock_pdf_checker_class.return_value = mock_checker
        
        mock_result = PDFCheckResult(
            file_path="test.pdf",
            paper_type=PaperType.LONG,
            total_pages=6,
            content_pages=6,
            issues=[]
        )
        mock_checker.check_pdf.return_value = mock_result
        
        with self.runner.isolated_filesystem():
            # Create a test PDF file
            Path("test.pdf").touch()
            
            result = self.runner.invoke(main, ['check-pdf', 'test.pdf', '--type', 'long'])
            
            assert result.exit_code == 0
            mock_checker.check_pdf.assert_called_once()
            mock_checker.print_results.assert_called_once()
    
    @patch('service.cli.PDFChecker')
    @patch('pathlib.Path.is_dir')
    def test_check_pdf_directory(self, mock_is_dir, mock_pdf_checker_class):
        """Test checking PDFs in a directory."""
        mock_is_dir.return_value = True
        
        # Mock the PDFChecker instance
        mock_checker = Mock()
        mock_pdf_checker_class.return_value = mock_checker
        
        mock_results = [
            PDFCheckResult(
                file_path="paper1.pdf",
                paper_type=PaperType.SHORT,
                total_pages=4,
                content_pages=4,
                issues=[]
            )
        ]
        mock_checker.check_directory.return_value = mock_results
        
        with self.runner.isolated_filesystem():
            Path("papers").mkdir()
            
            result = self.runner.invoke(main, ['check-pdf', 'papers', '--type', 'short'])
            
            assert result.exit_code == 0
            mock_checker.check_directory.assert_called_once()
    
    def test_check_pdf_invalid_file(self):
        """Test checking a non-PDF file."""
        with self.runner.isolated_filesystem():
            Path("test.txt").write_text("Not a PDF")
            
            result = self.runner.invoke(main, ['check-pdf', 'test.txt'])
            
            assert result.exit_code != 0
            assert "must be a PDF" in result.output
    
    def test_check_pdf_nonexistent_path(self):
        """Test checking a non-existent path."""
        result = self.runner.invoke(main, ['check-pdf', 'nonexistent.pdf'])
        
        assert result.exit_code != 0
    
    @patch('service.cli.PDFChecker')
    @patch('pathlib.Path.is_file')
    def test_check_pdf_with_errors_exits_normally(self, mock_is_file, mock_pdf_checker_class):
        """Test that CLI exits normally (code 0) even when PDF has issues."""
        mock_is_file.return_value = True
        
        mock_checker = Mock()
        mock_pdf_checker_class.return_value = mock_checker
        
        # Create a result with errors
        mock_result = PDFCheckResult(
            file_path="test.pdf",
            paper_type=PaperType.SHORT,
            total_pages=6,
            content_pages=6,
            issues=[
                Issue(IssueType.PAGE_LIMIT, "error", "Too many pages")
            ]
        )
        mock_checker.check_pdf.return_value = mock_result
        
        with self.runner.isolated_filesystem():
            Path("test.pdf").touch()
            
            result = self.runner.invoke(main, ['check-pdf', 'test.pdf'])
            
            # CLI exits normally even with errors (user preference)
            assert result.exit_code == 0
    
    @patch('service.cli.save_results_to_file')
    @patch('service.cli.PDFChecker')
    @patch('pathlib.Path.is_file')
    def test_check_pdf_with_output_file(self, mock_is_file, mock_pdf_checker_class, mock_save):
        """Test saving results to output file."""
        mock_is_file.return_value = True
        
        mock_checker = Mock()
        mock_pdf_checker_class.return_value = mock_checker
        
        mock_result = PDFCheckResult(
            file_path="test.pdf",
            paper_type=PaperType.LONG,
            total_pages=6,
            content_pages=6,
            issues=[]
        )
        mock_checker.check_pdf.return_value = mock_result
        
        with self.runner.isolated_filesystem():
            Path("test.pdf").touch()
            
            result = self.runner.invoke(main, ['check-pdf', 'test.pdf', '--output', 'results.json'])
            
            assert result.exit_code == 0
            mock_save.assert_called_once()
            assert "saved to results.json" in result.output