#!/usr/bin/env python3
"""
Start MAESTRO Unified BFF Service
Provides Chat + Preview endpoints with WebSocket support
"""

import argparse
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn


def start_bff_service(host: str = "0.0.0.0", port: int = 4001, reload: bool = False):
    """
    Start the MAESTRO Unified BFF Service

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 4001)
        reload: Enable auto-reload for development (default: False)
    """
    uvicorn.run("bff.main:app", host=host, port=port, reload=reload, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start MAESTRO Unified BFF Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=4001, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    args = parser.parse_args()

    print("=" * 80)
    print("🚀 MAESTRO Unified BFF Service")
    print("=" * 80)
    print(f"Starting on {args.host}:{args.port}")
    print(f"Docs: http://localhost:{args.port}/docs")
    print(f"WebSocket: ws://localhost:{args.port}/ws/{{session_id}}")
    print("=" * 80)

    start_bff_service(host=args.host, port=args.port, reload=args.reload)
