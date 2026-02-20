"""
Command-line interface for service-utils.
"""

import os
import re
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


def _openreview_ac_setup():
    """
    Shared setup for OpenReview AC commands: authenticate, select a venue,
    and fetch assigned paper IDs.

    Returns (client, user_id, venue_id, paper_ids), or None on a soft exit
    (no venues / no papers) after printing an explanation.
    """
    from .openreview_client import (
        get_client,
        get_area_chair_venues,
        get_ac_paper_assignments,
    )

    try:
        client = get_client()
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    profile = client.get_profile()
    user_id = profile.id
    console.print(f"[blue]Logged in as: {user_id}[/blue]")

    venues = get_area_chair_venues(client, user_id)
    if not venues:
        console.print("[yellow]No Area Chair venues found for your account.[/yellow]")
        return None

    console.print("\n[bold]Your Area Chair venues:[/bold]")
    for i, v in enumerate(venues, 1):
        console.print(f"  {i}. {v['venue_id']}")

    choice = click.prompt("\nSelect a venue", type=click.IntRange(1, len(venues)))
    venue_id = venues[choice - 1]["venue_id"]
    console.print(f"\n[blue]Selected: {venue_id}[/blue]")

    console.print("[blue]Fetching paper assignments...[/blue]")
    paper_ids = get_ac_paper_assignments(client, venue_id, user_id)
    if not paper_ids:
        console.print("[yellow]No papers assigned to you as AC in this venue.[/yellow]")
        return None
    console.print(f"[blue]Found {len(paper_ids)} assigned paper(s).[/blue]")

    return client, user_id, venue_id, paper_ids


def _openreview_reviewer_setup():
    """
    Shared setup for OpenReview reviewer commands: authenticate, select a venue,
    and fetch assigned paper IDs.

    Returns (client, user_id, venue_id, paper_ids), or None on a soft exit
    (no venues / no papers) after printing an explanation.
    """
    from .openreview_client import (
        get_client,
        get_reviewer_venues,
        get_reviewer_paper_assignments,
    )

    try:
        client = get_client()
    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.Abort()

    profile = client.get_profile()
    user_id = profile.id
    console.print(f"[blue]Logged in as: {user_id}[/blue]")

    venues = get_reviewer_venues(client, user_id)
    if not venues:
        console.print("[yellow]No Reviewer venues found for your account.[/yellow]")
        return None

    console.print("\n[bold]Your Reviewer venues:[/bold]")
    for i, v in enumerate(venues, 1):
        console.print(f"  {i}. {v['venue_id']}")

    choice = click.prompt("\nSelect a venue", type=click.IntRange(1, len(venues)))
    venue_id = venues[choice - 1]["venue_id"]
    console.print(f"\n[blue]Selected: {venue_id}[/blue]")

    console.print("[blue]Fetching paper assignments...[/blue]")
    paper_ids = get_reviewer_paper_assignments(client, venue_id, user_id)
    if not paper_ids:
        console.print("[yellow]No papers assigned to you as Reviewer in this venue.[/yellow]")
        return None
    console.print(f"[blue]Found {len(paper_ids)} assigned paper(s).[/blue]")

    return client, user_id, venue_id, paper_ids


def _select_papers(client, paper_ids):
    """
    Interactively prompt the user to select a subset of papers (or all).

    Returns the filtered list of paper_ids.
    """
    from .openreview_client import get_paper_summaries

    console.print("[blue]Fetching paper list...[/blue]")
    summaries = get_paper_summaries(client, paper_ids)

    console.print("\n[bold]Available papers:[/bold]")
    console.print("  [cyan]0.[/cyan] All papers")
    for i, s in enumerate(summaries, 1):
        console.print(f"  [cyan]{i}.[/cyan] #{s['number']}: {s['title']}")

    raw = click.prompt(
        "\nSelect papers (comma-separated indices, or 0 for all)",
        default="0",
    )

    choices = {c.strip() for c in raw.split(",") if c.strip()}
    if "0" in choices:
        return paper_ids

    id_map = {str(i): s["paper_id"] for i, s in enumerate(summaries, 1)}
    selected = []
    for c in sorted(choices, key=lambda x: int(x)):
        if c not in id_map:
            console.print(f"[yellow]Warning: index {c} is out of range, skipping.[/yellow]")
        else:
            selected.append(id_map[c])
    return selected


@main.command("pull-reviewer-reviews")
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default="./reviews",
    help="Directory to save review markdown files (default: ./reviews).",
)
@click.option(
    "--paper", "-p",
    type=str,
    default=None,
    help="Comma-separated paper numbers to pull (e.g. 42,57). Pulls all if omitted.",
)
def pull_reviewer_reviews(output_dir: str, paper: str):
    """Pull all reviews for papers you're assigned to as a Reviewer and save as markdown files."""
    from .openreview_client import get_paper_reviews, filter_paper_ids_by_number

    setup = _openreview_reviewer_setup()
    if setup is None:
        return
    client, user_id, venue_id, paper_ids = setup

    if paper:
        requested = {int(n.strip()) for n in paper.split(",") if n.strip()}
        paper_ids, unknown = filter_paper_ids_by_number(client, paper_ids, requested)
        for num in sorted(unknown):
            console.print(f"[yellow]Warning: paper #{num} not found in your assignments.[/yellow]")
        if not paper_ids:
            console.print("[yellow]No matching papers found.[/yellow]")
            return
    else:
        paper_ids = _select_papers(client, paper_ids)
        if not paper_ids:
            console.print("[yellow]No papers selected.[/yellow]")
            return

    console.print("[blue]Pulling reviews...[/blue]")
    papers = get_paper_reviews(client, venue_id, paper_ids)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for paper in papers:
        md = _render_paper_markdown(paper)
        safe_title = re.sub(r"[^\w\s-]", "", paper["title"])[:60].strip().replace(" ", "_")
        filename = f"paper_{paper['paper_number']}_{safe_title}.md"
        filepath = out / filename
        filepath.write_text(md, encoding="utf-8")
        console.print(f"  [green]Saved: {filepath}[/green]")

    console.print(f"\n[green]Done! {len(papers)} paper(s) saved to {out}/[/green]")


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
@click.option(
    "--post-comment",
    is_flag=True,
    default=False,
    help="Post a private comment on each paper's forum (visible to SACs/PCs/ACs) indicating you've contacted late reviewers.",
)
def missing_reviews(send_email: str, test_email: str, post_comment: bool):
    """Find reviewers with missing reviews for your AC papers."""
    from .openreview_client import get_missing_reviews, post_ac_comment

    setup = _openreview_ac_setup()
    if setup is None:
        return
    client, user_id, venue_id, paper_ids = setup

    console.print("[blue]Checking for missing reviews...[/blue]")
    missing = get_missing_reviews(client, venue_id, paper_ids)

    if not missing:
        console.print("[green]All reviewers have submitted their reviews![/green]")
        return

    table = Table(title="Missing Reviews")
    table.add_column("Paper #", style="cyan", justify="right")
    table.add_column("Paper Title", style="white")
    table.add_column("OpenReview Link", style="blue")
    table.add_column("Reviewer Name", style="yellow")
    table.add_column("Reviewer Email", style="red")
    table.add_column("Flag", style="bright_red")

    for entry in missing:
        link = f"https://openreview.net/forum?id={entry['paper_id']}"
        table.add_row(
            str(entry["paper_number"]),
            entry["paper_title"],
            link,
            entry["reviewer_name"],
            entry["reviewer_email"],
            entry["flag"],
        )

    console.print(table)
    console.print(f"\n[red]Total missing reviews: {len(missing)}[/red]")

    if test_email and not send_email:
        console.print("[red]Error: --test-email requires --send-email.[/red]")
        raise click.Abort()

    if send_email:
        if test_email:
            console.print(f"\n[yellow]TEST MODE: all emails will be sent to {test_email}[/yellow]")
        emergency_count = sum(1 for e in missing if e.get("flag") == "Emergency")
        if emergency_count:
            console.print(f"[yellow]Note: {emergency_count} reviewer(s) declared emergency and will NOT be emailed.[/yellow]")
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
                if "emergency" in error.lower():
                    console.print(f"  [yellow]Skipped {target}: reviewer declared emergency[/yellow]")
                else:
                    console.print(f"  [red]Failed to send to {target}: {error}[/red]")
        console.print("[blue]Done.[/blue]")

    if post_comment:
        # Collect unique papers from missing entries
        papers = {}
        for entry in missing:
            pid = entry["paper_id"]
            if pid not in papers:
                papers[pid] = {
                    "paper_id": pid,
                    "paper_number": entry["paper_number"],
                    "paper_title": entry["paper_title"],
                }

        console.print(f"\n[bold]Papers to comment on ({len(papers)}):[/bold]")
        for p in papers.values():
            console.print(f"  - #{p['paper_number']}: {p['paper_title']}")

        if not click.confirm("\nPost a private comment on each paper's forum?"):
            console.print("[yellow]Comment posting cancelled.[/yellow]")
        else:
            console.print("[blue]Posting comments...[/blue]")
            for p in list(papers.values()):
                result = post_ac_comment(
                    client, venue_id, p["paper_id"], p["paper_number"], user_id
                )
                if result[1]:
                    console.print(f"  [green]Posted comment on paper #{result[0]}[/green]")
                else:
                    error = result[2] if len(result) > 2 else "Unknown error"
                    console.print(f"  [red]Failed on paper #{result[0]}: {error}[/red]")
            console.print("[blue]Done posting comments.[/blue]")


@main.command("nudge-reviewers")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show a summary of non-responsive reviewers without posting any comments.",
)
@click.option(
    "--post-comment",
    is_flag=True,
    default=False,
    help="Post a private forum comment visible only to the reviewer and AC/SAC/PC.",
)
def nudge_reviewers(dry_run: bool, post_comment: bool):
    """Find reviewers who haven't responded to author rebuttals and nudge them."""
    from .openreview_client import (
        get_reviewers_without_response,
        post_reviewer_rebuttal_comment,
    )

    setup = _openreview_ac_setup()
    if setup is None:
        return
    client, user_id, venue_id, paper_ids = setup

    console.print("[blue]Checking for unanswered author responses...[/blue]")
    non_responsive = get_reviewers_without_response(client, venue_id, paper_ids)

    if not non_responsive:
        console.print("[green]All reviewers have responded to the author responses![/green]")
        return

    table = Table(title="Reviewers Without Response to Author Rebuttal")
    table.add_column("Paper #", style="cyan", justify="right")
    table.add_column("Paper Title", style="white")
    table.add_column("OpenReview Link", style="blue")
    table.add_column("Reviewer ID", style="yellow")

    for entry in non_responsive:
        link = f"https://openreview.net/forum?id={entry['paper_id']}"
        table.add_row(
            str(entry["paper_number"]),
            entry["paper_title"],
            link,
            entry["reviewer_id"],
        )

    console.print(table)
    console.print(f"\n[red]Total non-responsive reviewers: {len(non_responsive)}[/red]")

    if dry_run:
        console.print("\n[yellow]Dry run — no comments posted.[/yellow]")
        return

    if post_comment:
        if not click.confirm("\nPost a private comment on each paper forum directed at non-responsive reviewers?"):
            console.print("[yellow]Comment posting cancelled.[/yellow]")
        else:
            # Group non-responsive reviewers by paper, collecting their anon IDs
            papers = {}
            for entry in non_responsive:
                pid = entry["paper_id"]
                if pid not in papers:
                    papers[pid] = {
                        "paper_id": pid,
                        "paper_number": entry["paper_number"],
                        "paper_title": entry["paper_title"],
                        "reviewer_anon_ids": [],
                    }
                anon_id = entry.get("reviewer_anon_id")
                if anon_id:
                    papers[pid]["reviewer_anon_ids"].append(anon_id)

            console.print("[blue]Posting comments...[/blue]")
            for p in papers.values():
                if not p["reviewer_anon_ids"]:
                    console.print(f"  [yellow]Skipped paper #{p['paper_number']}: no anonymous IDs found[/yellow]")
                    continue
                result = post_reviewer_rebuttal_comment(
                    client, venue_id, p["paper_id"], p["paper_number"],
                    user_id, p["reviewer_anon_ids"],
                )
                if result[1]:
                    console.print(f"  [green]Posted comment on paper #{result[0]}[/green]")
                else:
                    error = result[2] if len(result) > 2 else "Unknown error"
                    console.print(f"  [red]Failed on paper #{result[0]}: {error}[/red]")
            console.print("[blue]Done posting comments.[/blue]")


@main.command("pull-reviews")
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default="./reviews",
    help="Directory to save review markdown files (default: ./reviews).",
)
@click.option(
    "--paper", "-p",
    type=str,
    default=None,
    help="Comma-separated paper numbers to pull (e.g. 42,57). Pulls all if omitted.",
)
def pull_reviews(output_dir: str, paper: str):
    """Pull reviews for your AC papers and save as markdown files."""
    from .openreview_client import get_paper_reviews, filter_paper_ids_by_number

    setup = _openreview_ac_setup()
    if setup is None:
        return
    client, user_id, venue_id, paper_ids = setup

    if paper:
        requested = {int(n.strip()) for n in paper.split(",") if n.strip()}
        paper_ids, unknown = filter_paper_ids_by_number(client, paper_ids, requested)
        for num in sorted(unknown):
            console.print(f"[yellow]Warning: paper #{num} not found in your assignments.[/yellow]")
        if not paper_ids:
            console.print("[yellow]No matching papers found.[/yellow]")
            return
    else:
        paper_ids = _select_papers(client, paper_ids)
        if not paper_ids:
            console.print("[yellow]No papers selected.[/yellow]")
            return

    console.print("[blue]Pulling reviews...[/blue]")
    papers = get_paper_reviews(client, venue_id, paper_ids)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for paper in papers:
        md = _render_paper_markdown(paper)
        safe_title = re.sub(r"[^\w\s-]", "", paper["title"])[:60].strip().replace(" ", "_")
        filename = f"paper_{paper['paper_number']}_{safe_title}.md"
        filepath = out / filename
        filepath.write_text(md, encoding="utf-8")
        console.print(f"  [green]Saved: {filepath}[/green]")

    console.print(f"\n[green]Done! {len(papers)} paper(s) saved to {out}/[/green]")


def _render_paper_markdown(paper: dict) -> str:
    """Render a paper's full discussion thread as markdown."""
    lines = []
    lines.append(f"# Paper {paper['paper_number']}: {paper['title']}\n")
    lines.append(f"**Authors:** {paper['authors']}\n")
    lines.append(f"## Abstract\n\n{paper['abstract']}\n")

    # Reviews
    for i, review in enumerate(paper["reviews"], 1):
        sig = ", ".join(review["signatures"])
        lines.append(f"---\n\n## Review {i} ({sig})\n")
        content = review["content"]
        for key, val in content.items():
            if not val:
                continue
            pretty_key = key.replace("_", " ").title()
            # Short values (scores, ratings) as bold key-value pairs
            val_str = str(val)
            if len(val_str) < 100 and "\n" not in val_str:
                lines.append(f"**{pretty_key}:** {val_str}\n")
            else:
                lines.append(f"### {pretty_key}\n\n{val_str}\n")

    # Meta reviews
    for i, meta in enumerate(paper["meta_reviews"], 1):
        sig = ", ".join(meta["signatures"])
        lines.append(f"---\n\n## Meta Review {i} ({sig})\n")
        for key, val in meta["content"].items():
            if not val:
                continue
            pretty_key = key.replace("_", " ").title()
            val_str = str(val)
            if len(val_str) < 100 and "\n" not in val_str:
                lines.append(f"**{pretty_key}:** {val_str}\n")
            else:
                lines.append(f"### {pretty_key}\n\n{val_str}\n")

    # Decisions
    for decision in paper["decisions"]:
        sig = ", ".join(decision["signatures"])
        lines.append(f"---\n\n## Decision ({sig})\n")
        for key, val in decision["content"].items():
            if not val:
                continue
            pretty_key = key.replace("_", " ").title()
            val_str = str(val)
            if len(val_str) < 100 and "\n" not in val_str:
                lines.append(f"**{pretty_key}:** {val_str}\n")
            else:
                lines.append(f"### {pretty_key}\n\n{val_str}\n")

    # Comments
    if paper["comments"]:
        lines.append("---\n\n## Comments\n")
        for comment in paper["comments"]:
            sig = ", ".join(comment["signatures"])
            lines.append(f"### Comment by {sig}\n")
            for key, val in comment["content"].items():
                if not val:
                    continue
                pretty_key = key.replace("_", " ").title()
                val_str = str(val)
                if len(val_str) < 100 and "\n" not in val_str:
                    lines.append(f"**{pretty_key}:** {val_str}\n")
                else:
                    lines.append(f"{val_str}\n")

    return "\n".join(lines)


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