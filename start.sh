#!/bin/bash

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start the application
echo "Starting PDF Processor API..."
uvicorn pdf_processor.main:app --reload