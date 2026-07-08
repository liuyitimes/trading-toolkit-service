# -*- coding: utf-8 -*-
"""Test configuration and fixtures."""

import sys
from unittest.mock import MagicMock

# Mock akshare before any imports
mock_akshare = MagicMock()
sys.modules['akshare'] = mock_akshare

# Mock pandas if not available
try:
    import pandas
except ImportError:
    sys.modules['pandas'] = MagicMock()
