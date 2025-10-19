"""
Command-line interface for service-utils.
"""

import os
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from .pdf_checker import PDFChecker, PaperType


console = Console()


@click.group()
@click.version_option()
def main():
    """Service Utils - Academic service utilities."""
    pass


@main.command("check-pdf")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--type", "paper_type",
    type=click.Choice(["short", "long"], case_sensitive=False),
    default="long",
    help="Type of paper (short: 4 pages max, long: 8 pages max)"
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output file for results (JSON format)"
)
@click.option(
    "--quiet", "-q",
    is_flag=True,
    help="Suppress output, only show summary"
)
def check_pdf(path: str, paper_type: str, output: Optional[str], quiet: bool):
    """
    Check PDF submission requirements.
    
    PATH can be either a single PDF file or a directory containing PDF files.
    
    Examples:
    
        # Check a single PDF as a long paper
        service-utils check-pdf paper.pdf
        
        # Check a single PDF as a short paper
        service-utils check-pdf paper.pdf --type short
        
        # Check all PDFs in a directory
        service-utils check-pdf ./submissions/ --type long
    """
    if quiet:
        console = Console(file=open(os.devnull, 'w'))
    else:
        console = Console()
    
    checker = PDFChecker(console=console)
    paper_type_enum = PaperType.SHORT if paper_type.lower() == "short" else PaperType.LONG
    
    path_obj = Path(path)
    
    if path_obj.is_file():
        # Check single file
        if not path.lower().endswith('.pdf'):
            console.print("[red]Error: File must be a PDF[/red]")
            raise click.Abort()
        
        console.print(f"[blue]Checking PDF: {path}[/blue]")
        result = checker.check_pdf(path, paper_type_enum)
        results = [result]
        
    elif path_obj.is_dir():
        # Check directory
        console.print(f"[blue]Checking directory: {path}[/blue]")
        results = checker.check_directory(path, paper_type_enum)
        
    else:
        console.print("[red]Error: Path must be a file or directory[/red]")
        raise click.Abort()
    
    if not results:
        console.print("[yellow]No PDF files processed[/yellow]")
        return
    
    # Print results
    if not quiet:
        checker.print_results(results)
    
    # Save to output file if requested
    if output:
        save_results_to_file(results, output)
        console.print(f"[green]Results saved to {output}[/green]")


def save_results_to_file(results, output_path: str):
    """Save results to a JSON file."""
    import json
    from dataclasses import asdict
    
    # Convert results to JSON-serializable format
    json_results = []
    for result in results:
        result_dict = asdict(result)
        # Convert enums to strings
        result_dict['paper_type'] = result.paper_type.value
        for issue in result_dict['issues']:
            issue['issue_type'] = issue['issue_type'].value
        json_results.append(result_dict)
    
    with open(output_path, 'w') as f:
        json.dump(json_results, f, indent=2)


if __name__ == "__main__":
    main()