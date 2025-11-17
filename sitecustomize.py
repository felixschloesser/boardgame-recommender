"""
Test harness shim to ensure pytest does not auto-load external plugins that
are unavailable in this environment (notably hypothesis' pytest plugin).
"""

from __future__ import annotations

import os

# Prevent pytest from auto-loading third-party plugins that expect the real
# hypothesis package, since we ship a lightweight local drop-in instead.
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
