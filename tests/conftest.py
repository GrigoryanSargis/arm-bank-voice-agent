"""
conftest.py — shared pytest fixtures.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the src/ tree importable when running pytest from the project root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
