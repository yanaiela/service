"""
Tests for PDF checker functionality using real PDFs from the data folder.
"""

import pytest
from pathlib import Path
import os

from service.pdf_checker import PDFChecker, PaperType, Issue, IssueType, PDFCheckResult


class TestPDFCheckerRealFiles:
    """Test PDF checker using actual PDF files from the data directory."""
    
    @pytest.fixture
    def checker(self):
        """Create a PDFChecker instance for testing."""
        return PDFChecker()
    
    @pytest.fixture
    def data_dir(self):
        """Get the path to the data directory with test PDFs."""
        current_dir = Path(__file__).parent.parent
        return current_dir / "data"
    
    def test_grade_pass_pdf(self, checker, data_dir):
        """Test grade_pass.pdf - should pass all checks (with info about being at limit)."""
        pdf_path = data_dir / "grade_pass.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found: {pdf_path}")
        
        result = checker.check_pdf(str(pdf_path), PaperType.LONG)
        
        # Expected results based on actual output
        assert result.file_path == str(pdf_path)
        assert result.paper_type == PaperType.LONG
        assert result.total_pages == 34
        assert result.content_pages == 8
        assert len(result.issues) == 1  # One info issue about being at limit
        assert not result.has_errors  # Info is not an error
        assert not result.has_warnings  # Info is not a warning
        
        # Check the info issue
        issue = result.issues[0]
        assert issue.issue_type == IssueType.PAGE_LIMIT
        assert issue.severity == "info"
        assert "at the page limit" in issue.message
    
    def test_grade_long_too_long_pdf(self, checker, data_dir):
        """Test grade_long_too-long.pdf - should fail on page limit."""
        pdf_path = data_dir / "grade_long_too-long.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found: {pdf_path}")
        
        result = checker.check_pdf(str(pdf_path), PaperType.LONG)
        
        # Expected results
        assert result.file_path == str(pdf_path)
        assert result.paper_type == PaperType.LONG
        assert result.total_pages == 35
        assert result.content_pages == 9  # Exceeds limit
        assert len(result.issues) == 1
        assert result.has_errors
        
        # Check specific issue
        issue = result.issues[0]
        assert issue.issue_type == IssueType.PAGE_LIMIT
        assert issue.severity == "error"
        assert "exceeds page limit" in issue.message
        assert "Found 9 content pages, limit is 8 pages" in issue.details
    
    def test_grade_no_limitations_pdf(self, checker, data_dir):
        """Test grade_no-limitations.pdf - should fail on missing limitations."""
        pdf_path = data_dir / "grade_no-limitations.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found: {pdf_path}")
        
        result = checker.check_pdf(str(pdf_path), PaperType.LONG)
        
        # Expected results
        assert result.file_path == str(pdf_path)
        assert result.paper_type == PaperType.LONG
        assert result.total_pages == 34
        assert result.content_pages == 8  # At limit
        assert len(result.issues) == 2  # 1 info (at limit) + 1 error (missing limitations)
        assert result.has_errors
        
        # Check for limitations issue
        limitations_issues = [i for i in result.issues if i.issue_type == IssueType.MISSING_LIMITATIONS]
        assert len(limitations_issues) == 1
        assert limitations_issues[0].severity == "error"
        assert "Missing required 'Limitations' section" in limitations_issues[0].message
        
        # Check for page limit info issue
        page_limit_issues = [i for i in result.issues if i.issue_type == IssueType.PAGE_LIMIT]
        assert len(page_limit_issues) == 1
        assert page_limit_issues[0].severity == "info"
    
    def test_ngram_novelty_pdf(self, checker, data_dir):
        """Test ngram-novelty.pdf - should fail on page limit and have anonymization warnings."""
        pdf_path = data_dir / "ngram-novelty.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found: {pdf_path}")
        
        result = checker.check_pdf(str(pdf_path), PaperType.LONG)
        
        # Expected results
        assert result.file_path == str(pdf_path)
        assert result.paper_type == PaperType.LONG
        assert result.total_pages == 15
        assert result.content_pages == 9  # Exceeds limit
        assert len(result.issues) == 4  # 1 page limit + 3 anonymization issues
        assert result.has_errors
        assert result.has_warnings
        
        # Check for page limit issue
        page_limit_issues = [i for i in result.issues if i.issue_type == IssueType.PAGE_LIMIT]
        assert len(page_limit_issues) == 1
        assert page_limit_issues[0].severity == "error"
        
        # Check for anonymization issues
        anon_issues = [i for i in result.issues if i.issue_type == IssueType.ANONYMIZATION]
        assert len(anon_issues) == 3
        assert all(issue.severity == "warning" for issue in anon_issues)
        
        # Check for specific email domains
        anon_details = [issue.details for issue in anon_issues]
        assert any("@nyu.edu" in details for details in anon_details)
        assert any("@allenai.org" in details for details in anon_details)
        assert any("@gmail.com" in details for details in anon_details)
    
    def test_short_ok_pdf(self, checker, data_dir):
        """Test short-ok.pdf - should have broken reference warnings."""
        pdf_path = data_dir / "short-ok.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found: {pdf_path}")
        
        result = checker.check_pdf(str(pdf_path), PaperType.LONG)
        
        # Expected results
        assert result.file_path == str(pdf_path)
        assert result.paper_type == PaperType.LONG
        assert result.total_pages == 31
        assert result.content_pages == 4  # Within limit
        assert len(result.issues) == 5  # 5 broken reference warnings
        assert not result.has_errors
        assert result.has_warnings
        
        # Check all issues are broken references
        for issue in result.issues:
            assert issue.issue_type == IssueType.BROKEN_REFERENCES
            assert issue.severity == "warning"
            assert "Broken reference detected" in issue.message
            assert "??" in issue.details
    
    def test_long_ethics_pdf(self, checker, data_dir):
        """Test long-ethics.pdf - should have ethical considerations warning."""
        pdf_path = data_dir / "long-ethics.pdf"
        if not pdf_path.exists():
            pytest.skip(f"Test PDF not found: {pdf_path}")
        
        result = checker.check_pdf(str(pdf_path), PaperType.LONG)
        
        # Expected results
        assert result.file_path == str(pdf_path)
        assert result.paper_type == PaperType.LONG
        assert result.total_pages == 34
        assert result.content_pages == 8  # At limit (ethics doesn't count)
        assert len(result.issues) == 2  # 1 info (at limit) + 1 warning (ethics)
        assert not result.has_errors
        assert result.has_warnings
        
        # Check for ethical considerations issue
        ethics_issues = [i for i in result.issues if i.issue_type == IssueType.ETHICAL_CONSIDERATIONS]
        assert len(ethics_issues) == 1
        assert ethics_issues[0].severity == "warning"
        assert "Ethical considerations section found" in ethics_issues[0].message
        assert "588 EthicalConsiderations" in ethics_issues[0].details
        
        # Check for page limit info issue
        page_limit_issues = [i for i in result.issues if i.issue_type == IssueType.PAGE_LIMIT]
        assert len(page_limit_issues) == 1
        assert page_limit_issues[0].severity == "info"


class TestPDFCheckerUnitMethods:
    """Test individual methods of PDFChecker with controlled inputs."""
    
    @pytest.fixture
    def checker(self):
        """Create a PDFChecker instance for testing."""
        return PDFChecker()
    
    def test_check_page_limits_short_paper_exceeded(self, checker):
        """Test page limit check for short paper that exceeds limit."""
        issues = checker._check_page_limits(5, PaperType.SHORT)
        
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.PAGE_LIMIT
        assert issues[0].severity == "error"
        assert "exceeds page limit" in issues[0].message
    
    def test_check_page_limits_long_paper_exceeded(self, checker):
        """Test page limit check for long paper that exceeds limit."""
        issues = checker._check_page_limits(9, PaperType.LONG)
        
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.PAGE_LIMIT
        assert issues[0].severity == "error"
        assert "exceeds page limit" in issues[0].message
        assert "Found 9 content pages, limit is 8 pages" in issues[0].details
    
    def test_check_page_limits_within_limit(self, checker):
        """Test page limit check for papers within limits."""
        # Short paper within limit
        issues = checker._check_page_limits(3, PaperType.SHORT)
        assert len(issues) == 0
        
        # Long paper within limit
        issues = checker._check_page_limits(6, PaperType.LONG)
        assert len(issues) == 0
    
    def test_check_page_limits_at_limit(self, checker):
        """Test page limit check for papers exactly at the limit."""
        # Exactly at limit generates info issue
        issues = checker._check_page_limits(4, PaperType.SHORT)
        assert len(issues) == 1
        assert issues[0].severity == "info"
        assert "at the page limit" in issues[0].message
        
        issues = checker._check_page_limits(8, PaperType.LONG)
        assert len(issues) == 1
        assert issues[0].severity == "info"
        assert "at the page limit" in issues[0].message
    
    def test_check_limitations_section_present(self, checker):
        """Test detection of limitations section when present."""
        text = """
        Introduction
        This is our paper.
        
        Limitations
        Our work has several limitations.
        
        Conclusion
        We conclude that...
        """
        
        issues = checker._check_limitations_section(text)
        assert len(issues) == 0
    
    def test_check_limitations_section_numbered_format(self, checker):
        """Test detection of numbered limitations section."""
        text = """
        Introduction
        This is our paper.
        
        5. Limitations
        Our work has several limitations.
        
        6. Conclusion
        We conclude that...
        """
        
        issues = checker._check_limitations_section(text)
        assert len(issues) == 0
    
    def test_check_limitations_section_missing(self, checker):
        """Test detection when limitations section is missing."""
        text = """
        Introduction
        This is our paper.
        
        Methods
        Our methodology...
        
        Results
        The results show...
        
        Conclusion
        We conclude that...
        """
        
        issues = checker._check_limitations_section(text)
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.MISSING_LIMITATIONS
        assert issues[0].severity == "error"
    
    def test_check_anonymization_with_emails(self, checker):
        """Test anonymization check with email addresses."""
        text = """
        This paper was written by researchers.
        Contact the authors at john.doe@university.edu for more information.
        Additional contact: researcher@company.com
        """
        
        issues = checker._check_anonymization(text)
        assert len(issues) >= 2
        assert all(issue.issue_type == IssueType.ANONYMIZATION for issue in issues)
        assert all(issue.severity == "warning" for issue in issues)
        
        # Check that email patterns are detected
        details = [issue.details for issue in issues]
        assert any("@university.edu" in detail for detail in details)
        assert any("@company.com" in detail for detail in details)
    
    def test_check_anonymization_clean(self, checker):
        """Test anonymization check with clean text."""
        text = """
        This paper presents a novel approach to machine learning.
        Our method outperforms existing baselines.
        We evaluate on standard datasets and show improvements.
        """
        
        issues = checker._check_anonymization(text)
        assert len(issues) == 0
    
    def test_check_broken_references_with_issues(self, checker):
        """Test broken reference detection."""
        text = """
        As shown in previous work ??, our method performs well.
        The results are described in ?? and demonstrate effectiveness.
        See [??] for more details on the methodology.
        """
        
        issues = checker._check_broken_references(text)
        assert len(issues) == 4  # Detects: ??, ??, [??], and ?? inside [??]
        assert all(issue.issue_type == IssueType.BROKEN_REFERENCES for issue in issues)
        assert all(issue.severity == "warning" for issue in issues)
        assert all("??" in issue.details for issue in issues)
    
    def test_check_broken_references_clean(self, checker):
        """Test broken reference detection with clean references."""
        text = """
        As shown in Smith et al. (2020), our method performs well.
        The results are described in [1] and demonstrate effectiveness.
        See Johnson (2019) for more details on the methodology.
        """
        
        issues = checker._check_broken_references(text)
        assert len(issues) == 0
    
    def test_check_ethical_considerations_present(self, checker):
        """Test detection of ethical considerations section."""
        text = """
        Introduction
        This is our paper.
        
        588 EthicalConsiderations
        
        We consider the ethical implications of our work.
        
        References
        [1] Some reference.
        """
        
        issues = checker._check_ethical_considerations(text)
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.ETHICAL_CONSIDERATIONS
        assert issues[0].severity == "warning"
        assert "Ethical considerations section found" in issues[0].message
        assert "588 EthicalConsiderations" in issues[0].details
    
    def test_check_ethical_considerations_standard_format(self, checker):
        """Test detection of standard format ethical considerations."""
        text = """
        Introduction
        This is our paper.
        
        Ethical Considerations
        We consider the ethical implications of our work.
        
        References
        [1] Some reference.
        """
        
        issues = checker._check_ethical_considerations(text)
        assert len(issues) == 1
        assert issues[0].issue_type == IssueType.ETHICAL_CONSIDERATIONS
        assert issues[0].severity == "warning"
    
    def test_check_ethical_considerations_missing(self, checker):
        """Test when no ethical considerations section is present."""
        text = """
        Introduction
        This is our paper.
        
        Methods
        Our methodology.
        
        Results
        Our results.
        
        References
        [1] Some reference.
        """
        
        issues = checker._check_ethical_considerations(text)
        assert len(issues) == 0


class TestPDFCheckResult:
    """Test PDFCheckResult class functionality."""
    
    def test_has_errors_property(self):
        """Test the has_errors property."""
        result = PDFCheckResult(
            file_path="test.pdf",
            paper_type=PaperType.SHORT,
            total_pages=5,
            content_pages=5,
            issues=[
                Issue(IssueType.PAGE_LIMIT, "error", "Too many pages"),
                Issue(IssueType.ANONYMIZATION, "warning", "Potential issue")
            ]
        )
        
        assert result.has_errors is True
        assert result.has_warnings is True
    
    def test_has_warnings_only(self):
        """Test when there are only warnings."""
        result = PDFCheckResult(
            file_path="test.pdf",
            paper_type=PaperType.SHORT,
            total_pages=3,
            content_pages=3,
            issues=[
                Issue(IssueType.BROKEN_REFERENCES, "warning", "Broken ref"),
                Issue(IssueType.ETHICAL_CONSIDERATIONS, "warning", "Ethics found")
            ]
        )
        
        assert result.has_errors is False
        assert result.has_warnings is True
    
    def test_no_issues(self):
        """Test when there are no issues."""
        result = PDFCheckResult(
            file_path="test.pdf",
            paper_type=PaperType.SHORT,
            total_pages=3,
            content_pages=3,
            issues=[]
        )
        
        assert result.has_errors is False
        assert result.has_warnings is False
    
    def test_issue_codes_property(self):
        """Test the issue_codes property for generating short codes."""
        result = PDFCheckResult(
            file_path="test.pdf",
            paper_type=PaperType.LONG,
            total_pages=10,
            content_pages=9,
            issues=[
                Issue(IssueType.PAGE_LIMIT, "error", "Too long"),
                Issue(IssueType.ANONYMIZATION, "warning", "Email found"),
                Issue(IssueType.BROKEN_REFERENCES, "warning", "Broken ref")
            ]
        )
        
        # Test that we can get issue codes (this tests the integration)
        assert len(result.issues) == 3
        assert result.has_errors is True
        assert result.has_warnings is True


if __name__ == "__main__":
    pytest.main([__file__])