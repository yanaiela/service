# Service Utils

A command-line interface library for executing various utilities to help with academic service jobs such as reviewing papers.

## Features

### PDF Submission Checker

Checks PDF submissions against academic conference requirements and provides detailed validation reports.

## Validation Rules

### 1. Page Length Validation
- **Short papers**: 4 content pages maximum
- **Long papers**: 8 content pages maximum

**Important**: The following sections do NOT count towards the page limit:
- References/Bibliography sections
- Appendices and supplementary materials
- Limitations sections
- Ethical considerations sections

### 2. Required Sections
- **Limitations section**: All papers must include a section discussing limitations
- Detected patterns include:
  - "Limitations" (standalone section header)
  - "5. Limitations" (numbered section)
  - "592 Limitations" (line-numbered section)
  - Various formatting variations

### 3. Anonymization Check
- Verifies proper anonymization of submissions
- Detects email addresses, URLs, and other potentially identifying information
- Common patterns checked:
  - Email addresses (@domain.com)
  - Institution URLs
  - Author identification

### 4. Reference Validation
- Detects broken references indicated by "??" patterns
- Identifies incomplete citations that may need attention

### 5. Ethical Considerations Detection
- Detects presence of ethical considerations sections
- Shows as a warning (not an error) when found
- Patterns detected:
  - "Ethical Considerations"
  - "Ethics"
  - "EthicalConsiderations" (single word)
  - Various numbered formats

## Status Categories

The tool assigns one of the following statuses to each paper:

### ✅ PASS
- Paper meets all requirements
- Within page limits
- Has required limitations section
- No critical issues detected

### ⚠️ WARN  
- Paper meets core requirements but has warnings
- May include:
  - Broken references (REF)
  - Ethical considerations section present (ETH)
  - Minor anonymization concerns

### ❌ FAIL
- Paper fails one or more critical requirements:
  - **LEN**: Exceeds page limit
  - **LIM**: Missing limitations section
  - **ANO**: Anonymization issues

## Issue Codes

Each issue is assigned a short code for quick identification:

- **LEN**: Page length violation
- **LIM**: Missing limitations section  
- **ANO**: Anonymization problems
- **REF**: Broken references detected
- **ETH**: Ethical considerations section found

## Installation

```bash
uv sync
```

## Usage

### Basic Commands

```bash
# Check a single PDF
uv run service check-pdf path/to/paper.pdf

# Check all PDFs in a directory
uv run service check-pdf path/to/directory/

# Specify paper type (short/long)
uv run service check-pdf path/to/paper.pdf --type short
uv run service check-pdf path/to/paper.pdf --type long

# Output results as JSON
uv run service check-pdf path/to/directory/ --json
```

### Example Output

```
╭─────────────────────────────── Issues in paper.pdf ───────────────────────────────╮
│ ❌ Paper exceeds page limit for long paper                                         │
│    Found 9 content pages, limit is 8 pages                                        │
│                                                                                    │
│ ⚠️ Broken reference detected                                                        │
│    Found: '??' in context: '...as described in ??. The results show...'          │
╰────────────────────────────────────────────────────────────────────────────────────╯

                        PDF Check Summary                         
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┓
┃ File                 ┃ Type ┃ Pages ┃ Content Pages ┃ Status ┃  Issues ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━┩
│ paper.pdf            │ long │    10 │             9 │  FAIL  │ LEN,REF │
└──────────────────────┴──────┴───────┴───────────────┴────────┴─────────┘
```

### Missing Reviews Checker

Finds reviewers who haven't submitted their reviews for papers you're assigned to as Area Chair on OpenReview.

#### Setup

Set your OpenReview credentials as environment variables:

```bash
export OPENREVIEW_USERNAME="your-email@example.com"
export OPENREVIEW_PASSWORD="your-password"
```

#### Usage

```bash
# List missing reviews
service missing-reviews

# Send reminder emails to reviewers from your email
service missing-reviews --send-email you@gmail.com

# Test email sending (all emails go to your address)
service missing-reviews --send-email you@gmail.com --test-email you@gmail.com
```

The command will:
1. Authenticate with OpenReview
2. List all venues where you are an Area Chair (newest first)
3. Prompt you to select a venue
4. Display a table of reviewers with missing reviews, including paper number, title, OpenReview link, reviewer name, reviewer email, and an emergency flag if the reviewer posted an Emergency Declaration

#### Sending Reminder Emails

Use `--send-email <your-email>` to send reminder emails to reviewers who haven't submitted their reviews. Emails are sent via SMTP from your personal email address. You will be prompted for your email password (app password) at runtime.

Supported email providers (auto-detected from domain):
- Gmail (`smtp.gmail.com`)
- Outlook/Hotmail (`smtp-mail.outlook.com`)
- Yahoo (`smtp.mail.yahoo.com`)
- Other domains fall back to `smtp.<domain>:587`

For Gmail, you need to use an [App Password](https://myaccount.google.com/apppasswords) instead of your regular password.

Use `--test-email <address>` alongside `--send-email` to redirect all emails to a test address. The email content will still use the real reviewer names and paper titles, but delivery goes to the test address only.

#### Example Output

```
Logged in as: ~First_Last1

Your Area Chair venues:
  1. aclweb.org/ACL/ARR/2026/January
  2. aclweb.org/ACL/ARR/2025/October
  ...

Select a venue: 1

                                        Missing Reviews
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Paper # ┃ Paper Title         ┃ OpenReview Link                           ┃ Reviewer Name   ┃ Reviewer Email       ┃ Flag      ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│    1234 │ Example Paper Title │ https://openreview.net/forum?id=abc123XYZ │ Jane Doe        │ reviewer@example.com │ Emergency │
└─────────┴─────────────────────┴───────────────────────────────────────────┴─────────────────┴──────────────────────┴───────────┘

Total missing reviews: 1
```

## Page Counting Logic

The tool uses sophisticated logic to determine content pages:

1. **Section Detection**: Automatically identifies where main content ends and supplementary sections begin
2. **Mid-page Handling**: Properly handles cases where sections start mid-page
3. **Multiple Patterns**: Recognizes various section header formats and numbering schemes
4. **Content Classification**: Distinguishes between main content and excluded sections

## Requirements

- Python 3.8+
- pdfplumber for PDF text extraction
- PyPDF2 for PDF processing
- Rich for formatted console output
- Click for CLI interface

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Check specific files during development
uv run service check-pdf test_files/
```