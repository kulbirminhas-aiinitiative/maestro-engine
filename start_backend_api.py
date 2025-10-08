#!/usr/bin/env python3
"""
MAESTRO Backend API Startup Script
Starts the backend API server that exposes _utcp workflow
"""

import argparse
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from api.main import start_server


def main():
    parser = argparse.ArgumentParser(description="Start MAESTRO Backend API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    print("=" * 80)
    print("🚀 Starting MAESTRO Backend API")
    print("=" * 80)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Reload: {args.reload}")
    print("=" * 80)
    print(f"📚 API Docs: http://localhost:{args.port}/docs")
    print(f"🔧 Health Check: http://localhost:{args.port}/health")
    print(f"📊 Workflow Stats: http://localhost:{args.port}/api/workflow/stats")
    print(f"🔄 Execute Workflow: POST http://localhost:{args.port}/api/workflow/execute")
    print("=" * 80)

    start_server(host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
