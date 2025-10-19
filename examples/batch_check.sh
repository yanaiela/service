#!/bin/bash

# Example shell script for batch processing PDFs

echo "PDF Submission Checker - Batch Processing Example"
echo "================================================"

# Set the paper type (short or long)
PAPER_TYPE="long"
SUBMISSIONS_DIR="./submissions"
RESULTS_DIR="./results"

# Create results directory if it doesn't exist
mkdir -p "$RESULTS_DIR"

echo "Checking PDFs in $SUBMISSIONS_DIR as $PAPER_TYPE papers..."

# Check all PDFs and save results
service-utils check-pdf "$SUBMISSIONS_DIR" \
    --type "$PAPER_TYPE" \
    --output "$RESULTS_DIR/check_results_$(date +%Y%m%d_%H%M%S).json"

echo "Results saved to $RESULTS_DIR/"

# Example: Check individual PDFs with different types
echo ""
echo "Checking individual papers with specific types..."

# Check short papers (4 pages max)
for pdf in "$SUBMISSIONS_DIR"/short_*.pdf; do
    if [ -f "$pdf" ]; then
        echo "Checking $pdf as short paper..."
        service-utils check-pdf "$pdf" --type short
    fi
done

# Check long papers (8 pages max)
for pdf in "$SUBMISSIONS_DIR"/long_*.pdf; do
    if [ -f "$pdf" ]; then
        echo "Checking $pdf as long paper..."
        service-utils check-pdf "$pdf" --type long
    fi
done

echo "Batch processing complete!"