#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
conftest.py - Shared pytest fixtures and configuration
"""

import os
import sys
from pathlib import Path

# Add scripts directory to path for all tests
scripts_path = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(scripts_path))

# Also add skill scripts
skill_scripts_path = Path(__file__).parent.parent.parent / "skill" / "scripts"
sys.path.insert(0, str(skill_scripts_path))
