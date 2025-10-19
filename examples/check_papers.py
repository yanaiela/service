#!/usr/bin/env python3
"""
Example usage of the PDF checker programmatically.
"""

from service.pdf_checker import PDFChecker, PaperType
from rich.console import Console

def main():
    # Create console for output
    console = Console()
    
    # Initialize the PDF checker
    checker = PDFChecker(console=console)
    
    # Example 1: Check a single PDF file
    console.print("[bold blue]Example 1: Checking a single PDF[/bold blue]")
    
    # Note: This would work with a real PDF file
    # result = checker.check_pdf("sample_paper.pdf", PaperType.LONG)
    # checker.print_results([result])
    
    console.print("Would check 'sample_paper.pdf' as a long paper (8 pages max)")
    console.print()
    
    # Example 2: Check all PDFs in a directory
    console.print("[bold blue]Example 2: Checking directory of PDFs[/bold blue]")
    
    # Note: This would work with a real directory
    # results = checker.check_directory("./submissions", PaperType.SHORT)
    # checker.print_results(results)
    
    console.print("Would check all PDFs in './submissions' as short papers (4 pages max)")
    console.print()
    
    # Example 3: Programmatically handle results
    console.print("[bold blue]Example 3: Programmatic result handling[/bold blue]")
    
    # Create a mock result for demonstration
    from service.pdf_checker import PDFCheckResult, Issue, IssueType
    
    mock_result = PDFCheckResult(
        file_path="example.pdf",
        paper_type=PaperType.LONG,
        total_pages=10,
        content_pages=9,
        issues=[
            Issue(
                issue_type=IssueType.PAGE_LIMIT,
                severity="error",
                message="Paper exceeds page limit for long paper",
                details="Found 9 content pages, limit is 8 pages"
            ),
            Issue(
                issue_type=IssueType.ANONYMIZATION,
                severity="warning",
                message="Potential anonymization issue detected",
                details="Found: 'Stanford University' in context"
            )
        ]
    )
    
    # Process results programmatically
    if mock_result.has_errors:
        console.print(f"[red]❌ {mock_result.file_path} has critical errors[/red]")
        
        # Handle each error
        for issue in mock_result.issues:
            if issue.severity == "error":
                console.print(f"  - Error: {issue.message}")
                if issue.details:
                    console.print(f"    Details: {issue.details}")
    
    if mock_result.has_warnings:
        console.print(f"[yellow]⚠️  {mock_result.file_path} has warnings[/yellow]")
        
        # Handle each warning
        for issue in mock_result.issues:
            if issue.severity == "warning":
                console.print(f"  - Warning: {issue.message}")


if __name__ == "__main__":
    main()