#!/usr/bin/env python
"""
Direct launcher for gtaa CLI.
Works without pip install — just run: python run.py <command>

Examples:
    python run.py demo --sample 1
    python run.py auth gcp-login --key-file sa.json --project my-project
    python run.py analyze --start-date 2025-03-01 --end-date 2025-03-07
"""
import sys
import os

# Force Python to use the local gtaa/ package from this directory
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Remove any stale gtaa entries from sys.modules
for key in list(sys.modules.keys()):
    if key == "gtaa" or key.startswith("gtaa."):
        del sys.modules[key]

from gtaa.cli.main import cli

if __name__ == "__main__":
    cli()
