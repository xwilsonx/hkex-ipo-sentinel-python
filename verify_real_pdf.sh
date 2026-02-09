#!/bin/bash

# Activate venv
source venv/bin/activate

# Start server in background
echo "Starting server..."
# Using port 8003 to avoid conflict
nohup uvicorn pdf_processor.main:app --host 127.0.0.1 --port 8003 > server_real.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Define real PDF path
PDF_PATH="data/pdf/sehk26020600999.pdf"
PDF_FILENAME="sehk26020600999.pdf"
DOC_ID="sehk26020600999"

if [ ! -f "$PDF_PATH" ]; then
    echo "ERROR: Test file $PDF_PATH not found!"
    kill $SERVER_PID
    exit 1
fi

echo "Using PDF: $PDF_PATH"

# Upload PDF
echo "Uploading PDF..."
curl -v -X POST -F "file=@$PDF_PATH;type=application/pdf" http://127.0.0.1:8003/api/v1/upload-pdf

# Check if directory exists
echo "Checking directory..."
EXPECTED_DIR="data/$DOC_ID"

if [ -d "$EXPECTED_DIR" ]; then
    echo "SUCCESS: Directory $EXPECTED_DIR created."
    echo "Listing contents of $EXPECTED_DIR:"
    ls -l "$EXPECTED_DIR"
else
    echo "FAILURE: Directory $EXPECTED_DIR NOT found."
    echo "Listing data directory:"
    ls -l data/
    echo "--- Server Log ---"
    cat server_real.log
    echo "------------------"
fi

# Clean up server
kill $SERVER_PID
# rm server_real.log
