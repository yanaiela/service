# CLAUDE.md

## Project Overview

`service` is a CLI tool for academic service tasks (e.g., reviewing papers, tracking reviews). Built with Click and Rich.

## Setup

```bash
uv sync
```

## Running

```bash
uv run service <command>
```

## Commands

- `service check-pdf <path>` — Validate PDF submissions against conference requirements (page limits, anonymization, required sections)
- `service missing-reviews` — Find reviewers with missing reviews for your Area Chair papers on OpenReview. Requires `OPENREVIEW_USERNAME` and `OPENREVIEW_PASSWORD` env vars. Supports `--send-email <your-email>` to send SMTP reminders and `--test-email <address>` to redirect all emails to a test address.

## Project Structure

- `service/cli.py` — Click CLI entry point, all commands registered on the `main` group
- `service/pdf_checker.py` — PDF validation logic
- `service/openreview_client.py` — OpenReview API interaction (auth, venue discovery, review tracking)
- `service/email_sender.py` — SMTP email sending for review reminders
- `pyproject.toml` — Dependencies and project config

## Key Patterns

- CLI commands use Click decorators on the `main` group in `cli.py`
- Output uses `rich.console.Console` and `rich.table.Table`
- OpenReview imports are deferred (inside the command function) to avoid import errors when openreview-py isn't needed
- OpenReview API v2 (`openreview.api.OpenReviewClient`) is used — notes have `invitations` (list) not `invitation` (string)
