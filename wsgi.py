"""
WSGI configuration file for PythonAnywhere deployment.
This file is used by PythonAnywhere to serve the AddressMe application.
"""
import os
import sys

# Add the project directory to the Python path
path = os.path.dirname(os.path.abspath(__file__))
if path not in sys.path:
    sys.path.append(path)

# Import the application object from main.py
from main import application

# This is the object that PythonAnywhere WSGI will look for
application = application