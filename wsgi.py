"""
WSGI configuration for PythonAnywhere deployment
"""
import os
import sys

# Add your project directory to the Python path
project_home = os.path.expanduser('~/edumind')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Set working directory
os.chdir(project_home)

# Import the Flask app
from app import app as application

# For PythonAnywhere, we use 'application' not 'app'
# Debug mode should be False for production
application.debug = False
