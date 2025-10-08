"""
MAESTRO Backend Execution Engine

A clean, production-ready backend execution engine for MAESTRO,
focusing on MCP/UTCP orchestration, RAG, and template integration.
"""

import sys
from pathlib import Path

# Add shared libraries to path
shared_libs = Path("/home/ec2-user/projects/shared/packages")
if shared_libs.exists():
    sys.path.insert(0, str(shared_libs / "core-api" / "src"))
    sys.path.insert(0, str(shared_libs / "core-logging" / "src"))
    sys.path.insert(0, str(shared_libs / "core-config" / "src"))

__version__ = "1.0.0"
