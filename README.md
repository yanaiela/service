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
pip install -e .
```

## Usage

### Basic Commands

```bash
# Check a single PDF
service check-pdf path/to/paper.pdf

# Check all PDFs in a directory
service check-pdf path/to/directory/

# Specify paper type (short/long)
service check-pdf path/to/paper.pdf --type short
service check-pdf path/to/paper.pdf --type long

# Output results as JSON
service check-pdf path/to/directory/ --json
```

### Alternative Usage (Python Module)

```bash
# Using python -m syntax
python -m service.cli check-pdf data/

# Check specific file
python -m service.cli check-pdf data/paper.pdf --type long
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
# Install in development mode
pip install -e .

# Run tests
python -m pytest

# Check specific files during development
python -m service.cli check-pdf test_files/
```