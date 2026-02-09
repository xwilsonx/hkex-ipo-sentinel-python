#!/bin/bash

# Activate venv
source venv/bin/activate

# Start server in background
echo "Starting server..."
nohup uvicorn pdf_processor.main:app --host 127.0.0.1 --port 8002 > server.log 2>&1 &
SERVER_PID=$!
echo "Server PID: $SERVER_PID"

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Create a dummy PDF file
echo "Fake PDF content" > test_curl_doc.pdf

# Upload PDF
echo "Uploading PDF..."
curl -v -X POST -F "file=@test_curl_doc.pdf;type=application/pdf" http://127.0.0.1:8002/api/v1/upload-pdf

# Check if directory exists
echo "Checking directory..."
if [ -d "data/test_curl_doc" ]; then
    echo "SUCCESS: Directory data/test_curl_doc created."
else
    echo "FAILURE: Directory data/test_curl_doc NOT found."
    ls -l data/
    echo "--- Server Log ---"
    cat server.log
    echo "------------------"
fi

# Clean up
kill $SERVER_PID
rm test_curl_doc.pdf
# rm server.log # Keep for debugging if needed
