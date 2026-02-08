"""
Command-line interface for service-utils.
"""

import os
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from rich.table import Table

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


@main.command("missing-reviews")
@click.option(
    "--send-email",
    type=str,
    default=None,
    help="Send reminder emails from this email address (e.g. you@gmail.com).",
)
@click.option(
    "--test-email",
    type=str,
    default=None,
    help="Send all emails to this address instead of the actual reviewers (for testing).",
)
def missing_reviews(send_email: str, test_email: str):
    """Find reviewers with missing reviews for your AC papers."""
    from .openreview_client import (
        get_client,
        get_area_chair_venues,
        get_ac_paper_assignments,
        get_missing_reviews,
    )

    # 1. Authenticate
    try:
        client = get_client()
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    # 2. Get user profile
    profile = client.get_profile()
    user_id = profile.id
    console.print(f"[blue]Logged in as: {user_id}[/blue]")

    # 3. Discover AC venues
    venues = get_area_chair_venues(client, user_id)
    if not venues:
        console.print("[yellow]No Area Chair venues found for your account.[/yellow]")
        return

    console.print("\n[bold]Your Area Chair venues:[/bold]")
    for i, v in enumerate(venues, 1):
        console.print(f"  {i}. {v['venue_id']}")

    choice = click.prompt(
        "\nSelect a venue",
        type=click.IntRange(1, len(venues)),
    )
    selected = venues[choice - 1]
    venue_id = selected["venue_id"]
    console.print(f"\n[blue]Selected: {venue_id}[/blue]")

    # 4. Fetch AC paper assignments
    console.print("[blue]Fetching paper assignments...[/blue]")
    paper_ids = get_ac_paper_assignments(client, venue_id, user_id)
    if not paper_ids:
        console.print("[yellow]No papers assigned to you as AC in this venue.[/yellow]")
        return
    console.print(f"[blue]Found {len(paper_ids)} assigned paper(s).[/blue]")

    # 5. Find missing reviews
    console.print("[blue]Checking for missing reviews...[/blue]")
    missing = get_missing_reviews(client, venue_id, paper_ids)

    # 6. Display results
    if not missing:
        console.print("[green]All reviewers have submitted their reviews![/green]")
        return

    table = Table(title="Missing Reviews")
    table.add_column("Paper #", style="cyan", justify="right")
    table.add_column("Paper Title", style="white")
    table.add_column("OpenReview Link", style="blue")
    table.add_column("Reviewer Name", style="yellow")
    table.add_column("Reviewer Email", style="red")

    for entry in missing:
        link = f"https://openreview.net/forum?id={entry['paper_id']}"
        table.add_row(
            str(entry["paper_number"]),
            entry["paper_title"],
            link,
            entry["reviewer_name"],
            entry["reviewer_email"],
        )

    console.print(table)
    console.print(f"\n[red]Total missing reviews: {len(missing)}[/red]")

    if test_email and not send_email:
        console.print("[red]Error: --test-email requires --send-email.[/red]")
        raise click.Abort()

    if send_email:
        if test_email:
            console.print(f"\n[yellow]TEST MODE: all emails will be sent to {test_email}[/yellow]")
        if not click.confirm("\nSend reminder emails to all listed reviewers?"):
            console.print("[yellow]Email sending cancelled.[/yellow]")
            return

        sender_name = click.prompt("Your name (for email signature)")
        password = click.prompt("Email password (app password)", hide_input=True)
        console.print("[blue]Sending reminder emails...[/blue]")
        from .email_sender import send_reminder_emails
        email_results = send_reminder_emails(
            sender_email=send_email,
            sender_name=sender_name,
            password=password,
            missing_entries=missing,
            test_email=test_email,
        )
        for result in email_results:
            target = result[0]
            success = result[1]
            if success:
                console.print(f"  [green]Sent to {target}[/green]")
            else:
                error = result[2] if len(result) > 2 else "Unknown error"
                console.print(f"  [red]Failed to send to {target}: {error}[/red]")
        console.print("[blue]Done.[/blue]")



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