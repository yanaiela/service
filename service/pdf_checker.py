"""
PDF checker module for validating academic paper submissions.
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

import pdfplumber
import PyPDF2
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn


class PaperType(Enum):
    SHORT = "short"
    LONG = "long"


class IssueType(Enum):
    PAGE_LIMIT = "page_limit"
    MISSING_LIMITATIONS = "missing_limitations"
    ANONYMIZATION = "anonymization"
    BROKEN_REFERENCES = "broken_references"
    ETHICAL_CONSIDERATIONS = "ethical_considerations"


@dataclass
class Issue:
    """Represents an issue found in a PDF."""
    issue_type: IssueType
    severity: str  # "error", "warning", "info"
    message: str
    details: Optional[str] = None
    
    def get_code(self) -> str:
        """Get short code for this issue type."""
        code_map = {
            IssueType.PAGE_LIMIT: "LEN",
            IssueType.MISSING_LIMITATIONS: "LIM", 
            IssueType.ANONYMIZATION: "ANO",
            IssueType.BROKEN_REFERENCES: "REF",
            IssueType.ETHICAL_CONSIDERATIONS: "ETH"
        }
        return code_map.get(self.issue_type, "UNK")


@dataclass
class PDFCheckResult:
    """Results of checking a PDF file."""
    file_path: str
    paper_type: PaperType
    total_pages: int
    content_pages: int
    issues: List[Issue]
    
    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)
    
    @property
    def has_warnings(self) -> bool:
        return any(issue.severity == "warning" for issue in self.issues)


class PDFChecker:
    """Main class for checking PDF submissions against academic requirements."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        
        # Single comprehensive regex for all section detection
        self.section_patterns = re.compile(
            r'(?:'
            # Limitations patterns - handle various numbering schemes and positions
            r'^\s*\d*\.?\s*limitations?\s*$|'                    # "Limitations", "5. Limitations" (exact match)
            r'^\s*[a-z]\)?\s*limitations?\s*$|'                  # "a) Limitations" (exact match)
            r'^\s*[ivxlcdm]+\.?\s*limitations?\s*$|'             # "iv. Limitations" (exact match)
            r'^\s*\d{1,3}\.\s*limitations?\s*$|'                 # "5. Limitations" (section number with dot)
            r'^\s*\d{1,3}\s+limitations?\s*$|'                   # "5 Limitations" (section number without dot)
            r'^\s*limitations?\s+|'                              # "Limitations " (at start of line, more flexible)
            r'\b\d{1,4}\s+limitations?\b|'                       # "592 Limitations" (anywhere, not necessarily end of line)
            r'\blimitations?\s*$|'                               # "Limitations" (end of line, standalone)
            
            # Ethical considerations patterns - handle various formats
            r'^\s*\d*\.?\s*ethical?\s+considerations?\s*$|'      # "Ethical Considerations", "5. Ethical Considerations" (exact match)
            r'^\s*\d*\.?\s*ethicalconsiderations?\s*$|'          # "EthicalConsiderations" (one word, exact match)
            r'^\s*\d{1,4}\s+ethicalconsiderations?\s+|'          # "588 EthicalConsiderations " (number + one word, flexible)
            r'^\s*\d*\.?\s*ethics?\s*$|'                         # "Ethics", "5. Ethics" (exact match)
            r'^\s*\d{1,3}\.\s*ethical?\s+considerations?\s*$|'   # "5. Ethical Considerations" (section number with dot)
            r'^\s*\d{1,3}\s+ethical?\s+considerations?\s*$|'     # "5 Ethical Considerations" (section number without dot)
            r'\b\d{1,4}\s+ethical?\s+considerations?\b|'         # "592 Ethical Considerations" (anywhere)
            r'\bethical?\s+considerations?\s*$|'                 # "Ethical Considerations" (end of line, standalone)
            r'\bethicalconsiderations?\s*$|'                     # "EthicalConsiderations" (one word, end of line)
            r'\bethics?\s*$|'                                    # "Ethics" (end of line, standalone)
            
            # References patterns - handle various formats
            r'^\s*\d*\.?\s*references?\s*$|'                     # "References", "5. References" (exact match)
            r'^\s*\d*\.?\s*bibliography\s*$|'                    # "Bibliography", "5. Bibliography" (exact match)
            r'^\s*\d{1,3}\.\s*references?\s*$|'                  # "5. References" (section number with dot)
            r'^\s*\d{1,3}\s+references?\s*$|'                    # "5 References" (section number without dot)
            r'\b\d{1,4}\s+references?\b|'                        # "588 References" (number + references anywhere)
            r'\breferences?\s+\d{3,4}\s*$|'                      # "References 639" (with line numbers)
            r'\breferences?\s*$|'                                # "References" (end of line, standalone)
            r'^\s*\[1\]|'                                        # "[1]" - start of references
            r'^\s*1\.\s+[A-Z]|'                                  # "1. Author" - numbered references
            
            # Appendix patterns - handle various formats
            r'^\s*\d*\.?\s*appendix\s*[a-z]?\s*$|'              # "Appendix", "Appendix A" (exact match)
            r'^\s*\d*\.?\s*appendices\s*$|'                     # "Appendices" (exact match)
            r'^\s*\d{1,3}\.\s*appendix\s*[a-z]?\s*$|'          # "A.1 Appendix" (section number with dot)
            r'^\s*\d{1,3}\s+appendix\s*[a-z]?\s*$|'            # "A1 Appendix" (section number without dot)
            r'^\s*appendix\s*[a-z]?\s*:|'                       # "Appendix A:" (with colon)
            r'\bsupplementary\s+materials?\s*$|'                # "Supplementary materials" (end of line)
            r'\badditional\s+results\s*$'                       # "Additional results" (end of line)
            r')',
            re.IGNORECASE | re.MULTILINE
        )
        
        # Anonymization patterns (kept separate as they're different purpose)
        self.anonymization_patterns = [
            r'\b[A-Z][a-z]+ University\b',
            r'\b[A-Z][a-z]+ Institute\b',
            r'\b[A-Z][a-z]+ College\b',
            r'@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # Email addresses
            r'\b(?:Author|Authors?):\s*[A-Z]',
            r'\b(?:Affiliation|Department):\s*[A-Z]',
            r'\{[a-z]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\}',  # LaTeX emails
        ]
    
    def check_pdf(self, file_path: str, paper_type: PaperType) -> PDFCheckResult:
        """
        Check a single PDF file against submission requirements.
        
        Args:
            file_path: Path to the PDF file
            paper_type: Type of paper (SHORT or LONG)
            
        Returns:
            PDFCheckResult with all issues found
        """
        issues = []
        
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                
                # Extract text from all pages for analysis
                full_text = ""
                page_texts = []
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    page_texts.append(page_text)
                    full_text += page_text + "\n"
                
                # Calculate content pages (excluding references, etc.)
                content_pages = self._calculate_content_pages(page_texts)
                
                # Check page limits
                page_limit_issues = self._check_page_limits(content_pages, paper_type)
                issues.extend(page_limit_issues)
                
                # Check for limitations section
                limitations_issues = self._check_limitations_section(full_text)
                issues.extend(limitations_issues)
                
                # Check anonymization
                anonymization_issues = self._check_anonymization(full_text)
                issues.extend(anonymization_issues)
                
                # Check for broken references
                broken_ref_issues = self._check_broken_references(full_text)
                issues.extend(broken_ref_issues)
                
                # Check for ethical considerations section
                ethical_issues = self._check_ethical_considerations(full_text)
                issues.extend(ethical_issues)
                
        except Exception as e:
            issues.append(Issue(
                issue_type=IssueType.PAGE_LIMIT,
                severity="error",
                message=f"Failed to process PDF: {str(e)}"
            ))
            total_pages = 0
            content_pages = 0
        
        return PDFCheckResult(
            file_path=file_path,
            paper_type=paper_type,
            total_pages=total_pages,
            content_pages=content_pages,
            issues=issues
        )
    
    def _calculate_content_pages(self, page_texts: List[str]) -> int:
        """
        Calculate the number of content pages, excluding references, appendices, 
        limitations, and ethics sections from the page limit.
        
        Strategy: Find where the main content ends and supplementary content begins,
        accounting for sections that start mid-page.
        """
        if not page_texts:
            return 0
        
        # Try to find where limitations/references start (can be mid-page)
        content_end = self._find_main_content_end(page_texts)
        
        if content_end is not None:
            # If limitations/references start mid-page, count that page as content
            # if it contains substantial main content before the section starts
            page_idx, is_mid_page = content_end
            if is_mid_page:
                return page_idx + 1  # Count the page where limitations start
            else:
                return page_idx  # Don't count the page where limitations start
        
        # Fallback: analyze each page individually
        content_pages = 0
        for i, page_text in enumerate(page_texts):
            if not self._page_is_excluded_content(page_text, i):
                content_pages += 1
        
        # Ensure we have at least 1 content page (sanity check)
        return max(1, content_pages)
    
    def _find_main_content_end(self, page_texts: List[str]) -> tuple:
        """
        Find where main content ends and limitations/references/appendices begin.
        Returns (page_index, is_mid_page) or None if not found.
        """
        for page_idx, page_text in enumerate(page_texts):
            lines = [line.strip() for line in page_text.split('\n') if line.strip()]
            
            for line_idx, line in enumerate(lines):
                # Use the unified section pattern
                if self.section_patterns.search(line):
                    # Additional validation for numbered reference patterns
                    if re.match(r'^\s*1\.\s+[A-Z]', line):
                        # Check if this looks like start of references by examining following lines
                        if self._looks_like_reference_section(lines, line_idx):
                            # Determine if this is mid-page or start of page
                            is_mid_page = line_idx > 10 or (
                                line_idx > 0 and 
                                sum(1 for l in lines[:line_idx] if len(l.split()) > 3) > 5
                            )
                            return (page_idx, is_mid_page)
                        # If it doesn't look like references, continue searching
                        continue
                    
                    # For all other patterns, accept the match
                    # Determine if this is mid-page or start of page
                    is_mid_page = line_idx > 10 or (
                        line_idx > 0 and 
                        sum(1 for l in lines[:line_idx] if len(l.split()) > 3) > 5
                    )
                    return (page_idx, is_mid_page)
        
        return None
    
    def _looks_like_reference_section(self, lines: List[str], start_idx: int) -> bool:
        """
        Check if a line starting with "1." is actually the beginning of a reference section
        by examining the following lines for reference-like patterns.
        """
        # Check the next few lines for numbered references
        reference_count = 0
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            line = lines[i].strip()
            # Look for numbered references like "1.", "2.", etc.
            if re.match(r'^\s*\d+\.\s+[A-Z]', line):
                reference_count += 1
            # Also look for bracket references like "[1]", "[2]", etc.
            elif re.match(r'^\s*\[\d+\]', line):
                reference_count += 1
        
        # If we found at least 2 consecutive reference-like lines, it's likely a reference section
        return reference_count >= 2


    def _page_is_excluded_content(self, page_text: str, page_idx: int) -> bool:
        """
        Determine if a page contains only excluded content (references, appendices, etc.).
        """
        lines = [line.strip() for line in page_text.split('\n') if line.strip()]
        
        if not lines:
            return True  # Empty page
        
        # Count lines that look like references
        reference_like_lines = 0
        total_substantial_lines = 0
        
        for line in lines:
            # Skip very short lines (likely headers/footers)
            if len(line.split()) < 3:
                continue
                
            total_substantial_lines += 1
            
            # Check if line looks like a reference
            if (re.search(r'^\s*\[\d+\]', line) or
                re.search(r'^\s*\d+\.\s+[A-Z]', line) or
                re.search(r'^\s*[A-Z][^.]*\.\s*\([12]\d{3}\)', line) or  # Author (year)
                re.search(r'^\s*[A-Z][^.]*\.\s+[A-Z][^.]*\.\s+\([12]\d{3}\)', line)):  # Author. Title. (year)
                reference_like_lines += 1
        
        # If more than 70% of substantial lines look like references, exclude this page
        if total_substantial_lines > 0 and reference_like_lines / total_substantial_lines > 0.7:
            return True
        
        # Check for appendix content patterns
        appendix_indicators = [
            r'\bappendix\b',
            r'\bsupplementary\b',
            r'\badditional\s+results\b',
            r'\bdetailed\s+proofs\b'
        ]
        
        text_lower = page_text.lower()
        appendix_matches = sum(1 for pattern in appendix_indicators 
                              if re.search(pattern, text_lower))
        
        # If page has multiple appendix indicators, likely appendix content
        if appendix_matches >= 2:
            return True
        
        return False
    
    def _is_likely_section_header(self, lines: List[str], target_line: str, page_index: int) -> bool:
        """
        Determine if a line is likely a section header by looking at context.
        """
        target_line_clean = target_line.strip()
        
        # Look for formatting cues that suggest this is a header
        # Headers are often:
        # - Centered or have specific formatting
        # - Followed by content
        # - Not part of a paragraph
        
        line_idx = None
        for i, line in enumerate(lines):
            if line.strip() == target_line_clean:
                line_idx = i
                break
        
        if line_idx is None:
            return False
        
        # Check if it's isolated (empty lines around it or start/end of page)
        prev_line_empty = line_idx == 0 or not lines[line_idx - 1].strip()
        next_line_empty = line_idx == len(lines) - 1 or not lines[line_idx + 1].strip()
        
        # Headers are often isolated or have content following them
        if prev_line_empty or next_line_empty:
            return True
        
        # Check if it's at the start of the page (common for new sections)
        if line_idx <= 3:  # Within first few lines
            return True
        
        return False
    
    def _check_page_limits(self, content_pages: int, paper_type: PaperType) -> List[Issue]:
        """Check if the paper exceeds page limits."""
        issues = []
        
        if paper_type == PaperType.SHORT:
            limit = 4
            paper_desc = "short paper"
        else:
            limit = 8
            paper_desc = "long paper"
        
        if content_pages > limit:
            issues.append(Issue(
                issue_type=IssueType.PAGE_LIMIT,
                severity="error",
                message=f"Paper exceeds page limit for {paper_desc}",
                details=f"Found {content_pages} content pages, limit is {limit} pages"
            ))
        elif content_pages == limit:
            issues.append(Issue(
                issue_type=IssueType.PAGE_LIMIT,
                severity="info",
                message=f"Paper is at the page limit for {paper_desc}",
                details=f"{content_pages} content pages (limit: {limit})"
            ))
        
        return issues
    
    def _check_limitations_section(self, text: str) -> List[Issue]:
        """Check if the paper has a limitations section using the unified regex pattern."""
        issues = []
        
        # Use the unified section pattern but filter for limitations
        lines = text.split('\n')
        for line in lines:
            line_clean = line.strip()
            if self.section_patterns.search(line_clean) and 'limitation' in line_clean.lower():
                return []  # Found limitations section
        
        # No limitations section found
        issues.append(Issue(
            issue_type=IssueType.MISSING_LIMITATIONS,
            severity="error",
            message="Missing required 'Limitations' section",
            details="Papers must include a section discussing limitations"
        ))
        
        return issues
    
    def _check_anonymization(self, text: str) -> List[Issue]:
        """Check if the paper is properly anonymized."""
        issues = []
        
        for pattern in self.anonymization_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract context around the match
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].replace('\n', ' ').strip()
                
                issues.append(Issue(
                    issue_type=IssueType.ANONYMIZATION,
                    severity="warning",
                    message="Potential anonymization issue detected",
                    details=f"Found: '{match.group()}' in context: '...{context}...'"
                ))
        
        return issues
    
    def _check_broken_references(self, text: str) -> List[Issue]:
        """Check for broken references indicated by '??' in the text."""
        issues = []
        
        # Look for ?? patterns that typically indicate broken references
        broken_ref_patterns = [
            r'\?\?',  # Double question marks
            r'\[.*\?\?.*\]',  # Question marks inside brackets like [??]
            r'\(.*\?\?.*\)',  # Question marks inside parentheses like (??)
        ]
        
        for pattern in broken_ref_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Extract context around the match
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].replace('\n', ' ').strip()
                
                issues.append(Issue(
                    issue_type=IssueType.BROKEN_REFERENCES,
                    severity="warning",
                    message="Broken reference detected",
                    details=f"Found: '{match.group()}' in context: '...{context}...'"
                ))
        
        return issues
    
    def _check_ethical_considerations(self, text: str) -> List[Issue]:
        """Check for ethical considerations section (warning if present)."""
        issues = []
        
        # Look for ethical considerations patterns in the text
        ethical_patterns = [
            r'^\s*\d*\.?\s*ethical?\s+considerations?\s*$',      # "Ethical Considerations", "5. Ethical Considerations"
            r'^\s*\d*\.?\s*ethicalconsiderations?\s*$',          # "EthicalConsiderations" (one word, exact match)
            r'^\s*\d{1,4}\s+ethicalconsiderations?\s+',          # "588 EthicalConsiderations " (number + one word, flexible)
            r'^\s*\d*\.?\s*ethics?\s*$',                         # "Ethics", "5. Ethics"
            r'^\s*\d{1,3}\.\s*ethical?\s+considerations?\s*$',   # "5. Ethical Considerations"
            r'^\s*\d{1,3}\s+ethical?\s+considerations?\s*$',     # "5 Ethical Considerations"
            r'\b\d{1,4}\s+ethical?\s+considerations?\b',         # "592 Ethical Considerations"
            r'\bethical?\s+considerations?\s*$',                 # "Ethical Considerations" (end of line)
            r'\bethicalconsiderations?\s*$',                     # "EthicalConsiderations" (one word, end of line)
            r'\bethics?\s*$',                                    # "Ethics" (end of line)
        ]
        
        found_ethical = False
        for pattern in ethical_patterns:
            if found_ethical:
                break
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                # Extract context around the match
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                context = text[start:end].replace('\n', ' ').strip()
                
                issues.append(Issue(
                    issue_type=IssueType.ETHICAL_CONSIDERATIONS,
                    severity="warning",
                    message="Ethical considerations section found",
                    details=f"Found: '{match.group().strip()}' in context: '...{context}...'"
                ))
                found_ethical = True
                break  # Only report once per paper
        
        return issues
    
    def check_directory(self, directory_path: str, paper_type: PaperType) -> List[PDFCheckResult]:
        """
        Check all PDF files in a directory.
        
        Args:
            directory_path: Path to directory containing PDF files
            paper_type: Type of papers to check
            
        Returns:
            List of PDFCheckResult for each PDF found
        """
        results = []
        directory = Path(directory_path)
        
        if not directory.exists():
            self.console.print(f"[red]Error: Directory '{directory_path}' does not exist[/red]")
            return results
        
        pdf_files = list(directory.glob("*.pdf"))
        if not pdf_files:
            self.console.print(f"[yellow]Warning: No PDF files found in '{directory_path}'[/yellow]")
            return results
        
        # Create progress bar
        with Progress(
            TextColumn("[blue]Checking PDFs"),
            BarColumn(bar_width=40),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=False  # Keep progress bar visible after completion
        ) as progress:
            task = progress.add_task("", total=len(pdf_files))
            
            for pdf_file in pdf_files:
                # Update progress with current file name at the end
                progress.update(task, description=f"[cyan]{pdf_file.name}[/cyan]")
                
                result = self.check_pdf(str(pdf_file), paper_type)
                results.append(result)
                
                # Advance progress
                progress.advance(task)
            
            # Update to completion status
            progress.update(task, description=f"[green]Completed![/green]")
        
        # Add a blank line after progress bar
        self.console.print()
        
        return results
    
    def print_results(self, results: List[PDFCheckResult]) -> None:
        """Print formatted results to console."""
        if not results:
            self.console.print("[yellow]No results to display[/yellow]")
            return
        
        total_errors = 0
        total_warnings = 0
        
        # Count totals for summary
        for result in results:
            error_count = sum(1 for issue in result.issues if issue.severity == "error")
            warning_count = sum(1 for issue in result.issues if issue.severity == "warning")
            total_errors += error_count
            total_warnings += warning_count
        
        # Detailed issues first - only show errors and warnings, not info messages
        for result in results:
            # Only show issues that are errors or warnings, not info messages
            significant_issues = [issue for issue in result.issues if issue.severity in ["error", "warning"]]
            if significant_issues:
                self.console.print()
                filename = os.path.basename(result.file_path)
                panel_title = f"Issues in {filename}"
                
                issue_text = ""
                for issue in significant_issues:
                    if issue.severity == "error":
                        icon = "❌"
                        color = "red"
                    elif issue.severity == "warning":
                        icon = "⚠️"
                        color = "yellow"
                    else:
                        icon = "ℹ️"
                        color = "blue"
                    
                    issue_text += f"{icon} [{color}]{issue.message}[/{color}]\n"
                    if issue.details:
                        issue_text += f"   {issue.details}\n"
                    issue_text += "\n"
                
                self.console.print(Panel(issue_text.strip(), title=panel_title))
        
        # Summary table at the end
        table = Table(title="PDF Check Summary")
        table.add_column("File", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Pages", justify="right")
        table.add_column("Content Pages", justify="right")
        table.add_column("Status", justify="center")
        table.add_column("Issues", justify="right")
        
        for result in results:
            filename = os.path.basename(result.file_path)
            paper_type = result.paper_type.value
            
            # Determine status
            if result.has_errors:
                status = "[red]FAIL[/red]"
            elif result.has_warnings:
                status = "[yellow]WARN[/yellow]"
            else:
                status = "[green]PASS[/green]"
            
            error_count = sum(1 for issue in result.issues if issue.severity == "error")
            warning_count = sum(1 for issue in result.issues if issue.severity == "warning")
            
            # Create unique issue codes list instead of counts
            error_codes = list(set(issue.get_code() for issue in result.issues if issue.severity == "error"))
            warning_codes = list(set(issue.get_code() for issue in result.issues if issue.severity == "warning"))
            
            issues_text = ""
            if error_codes:
                issues_text += f"[red]{','.join(sorted(error_codes))}[/red]"
            if warning_codes:
                if issues_text:
                    issues_text += " "
                issues_text += f"[yellow]{','.join(sorted(warning_codes))}[/yellow]"
            if not issues_text:
                issues_text = "[green]✓[/green]"
            
            table.add_row(
                filename,
                paper_type,
                str(result.total_pages),
                str(result.content_pages),
                status,
                issues_text
            )
        
        self.console.print()
        self.console.print(table)