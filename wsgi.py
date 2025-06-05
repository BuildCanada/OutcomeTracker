#!/usr/bin/env python3
"""
WSGI Entry Point for Promise Tracker Pipeline

Production-ready entry point for Gunicorn to serve the Flask application.
"""

import os
import sys
import logging
from pathlib import Path

# Add the application directory to Python path
app_dir = Path(__file__).parent
sys.path.insert(0, str(app_dir))

# Setup logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)

# Avoid circular import by importing at module level
from pipeline.orchestrator import create_app, PipelineOrchestrator

# Create the application instance
orchestrator = PipelineOrchestrator()
application = create_app(orchestrator)

# For Gunicorn
app = application

if __name__ == "__main__":
    # For local development
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 