"""
WSGI configuration for PythonAnywhere deployment
"""
import os
import sys

# Make the project importable regardless of platform (Render/PythonAnywhere/local).
# Use the directory containing this file as the project root.
project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import the Flask app
from app import app as application

# For PythonAnywhere, we use 'application' not 'app'
# Debug mode should be False for production
application.debug = False
