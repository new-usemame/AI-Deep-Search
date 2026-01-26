#!/bin/bash
# Setup script for Multi-Agent MacBook Searcher

echo "Setting up Multi-Agent MacBook Searcher..."

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "Installing Playwright browsers..."
playwright install chromium

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cat > .env << EOF
# OpenRouter API Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct

# Agent Configuration
AGENT_COUNT=12
MAX_PAGES_PER_SEARCH=50

# Search Configuration
DEFAULT_MODEL_NUMBERS=A1706,A1707,A1932
DEFAULT_SITES=ebay.com
DEFAULT_EXCLUSIONS=broken screen,bad battery,cracked,not working,damaged screen

# Browser Configuration
HEADLESS=true
EOF
    echo "Please edit .env and add your OpenRouter API key!"
else
    echo ".env file already exists"
fi

# Create data directory
mkdir -p data

echo "Setup complete!"
echo "To run the application:"
echo "  1. Edit .env and add your OPENROUTER_API_KEY"
echo "  2. Activate virtual environment: source venv/bin/activate"
echo "  3. Run: uvicorn app.main:app --reload"
