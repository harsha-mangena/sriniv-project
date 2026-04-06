#!/bin/bash
set -e

echo "=== Market Manipulation Surveillance Platform Setup ==="
echo ""

# Check Python version
python3 --version 2>/dev/null || { echo "Python 3.11+ required"; exit 1; }

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing Python dependencies..."
cd backend
pip install -r requirements.txt

# Copy env file
cd ..
if [ ! -f "backend/.env" ]; then
    echo "Creating .env file from example..."
    cp .env.example backend/.env
fi

# Create model directory
mkdir -p backend/models

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the platform:"
echo "  Option 1 (Docker):    make docker-up"
echo "  Option 2 (Local):     source venv/bin/activate && make run"
echo ""
echo "To run tests:           make test"
echo "To train ML models:     make train"
echo ""
echo "API docs at:            http://localhost:8000/docs"
echo "Health check at:        http://localhost:8000/api/health"
