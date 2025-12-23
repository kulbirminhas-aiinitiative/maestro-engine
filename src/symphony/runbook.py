"""
Symphony Demo Runbook and Preflight Checks

EPIC: MD-3902 - Maestro Symphony Demo
Story: MD-3913 - Create Demo Runbook with Preflight Checks

Provides:
- Comprehensive preflight checks for demo readiness
- Environment validation
- Single "Start Demo" script
- Demo checkpoints and timing guide
"""

import asyncio
import os
import time
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging
import json
import httpx

from symphony.offline_fallback import (
    get_fallback_manager,
    check_teams_health,
    check_llm_health,
    FallbackMode,
)
from symphony.metrics import get_metrics_collector, TraceContext
from symphony.personas import get_all_personas, get_ai_personas

logger = logging.getLogger(__name__)


# =============================================================================
# Preflight Check Definitions
# =============================================================================

class CheckStatus(str, Enum):
    """Status of a preflight check"""
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class PreflightCheckResult:
    """Result of a single preflight check"""
    name: str
    status: CheckStatus
    message: str
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PreflightReport:
    """Complete preflight check report"""
    timestamp: datetime
    overall_status: CheckStatus
    checks: List[PreflightCheckResult]
    total_duration_ms: float
    recommendations: List[str]
    ready_for_demo: bool


# =============================================================================
# Environment Configuration
# =============================================================================

REQUIRED_ENV_VARS = {
    "AZURE_TENANT_ID": "Microsoft Azure tenant ID for Teams integration",
    "AZURE_CLIENT_ID": "Azure app client ID",
    "AZURE_CLIENT_SECRET": "Azure app client secret",
    "ANTHROPIC_API_KEY": "Claude API key for AI responses",
}

OPTIONAL_ENV_VARS = {
    "TEAMS_CHANNEL_ID": "Target Teams channel for demo",
    "SYMPHONY_BACKEND_URL": "Backend URL (default: http://localhost:8000)",
    "SYMPHONY_WS_URL": "WebSocket URL (default: ws://localhost:8000/symphony/ws)",
    "REDIS_URL": "Redis URL for conversation history",
    "LOG_LEVEL": "Logging level (default: INFO)",
}

DEFAULT_URLS = {
    "backend": "http://localhost:8000",
    "websocket": "ws://localhost:8000/symphony/ws",
    "frontend": "http://localhost:5173",
}


# =============================================================================
# Preflight Check Functions
# =============================================================================

async def check_environment_vars() -> PreflightCheckResult:
    """Check required environment variables are set"""
    start = time.perf_counter()
    missing = []
    present = []

    for var, description in REQUIRED_ENV_VARS.items():
        if os.environ.get(var):
            present.append(var)
        else:
            missing.append(var)

    duration = (time.perf_counter() - start) * 1000

    if missing:
        return PreflightCheckResult(
            name="Environment Variables",
            status=CheckStatus.FAIL,
            message=f"Missing required env vars: {', '.join(missing)}",
            duration_ms=duration,
            details={"missing": missing, "present": present},
        )

    return PreflightCheckResult(
        name="Environment Variables",
        status=CheckStatus.PASS,
        message=f"All {len(REQUIRED_ENV_VARS)} required env vars present",
        duration_ms=duration,
        details={"present": present},
    )


async def check_backend_health(url: str = None) -> PreflightCheckResult:
    """Check backend API is healthy"""
    start = time.perf_counter()
    url = url or os.environ.get("SYMPHONY_BACKEND_URL", DEFAULT_URLS["backend"])

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/symphony/health")
            duration = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                return PreflightCheckResult(
                    name="Backend Health",
                    status=CheckStatus.PASS,
                    message=f"Backend healthy - {data.get('activeSessions', 0)} active sessions",
                    duration_ms=duration,
                    details=data,
                )
            else:
                return PreflightCheckResult(
                    name="Backend Health",
                    status=CheckStatus.FAIL,
                    message=f"Backend returned status {response.status_code}",
                    duration_ms=duration,
                )

    except httpx.ConnectError:
        duration = (time.perf_counter() - start) * 1000
        return PreflightCheckResult(
            name="Backend Health",
            status=CheckStatus.FAIL,
            message=f"Cannot connect to backend at {url}",
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        return PreflightCheckResult(
            name="Backend Health",
            status=CheckStatus.FAIL,
            message=f"Backend check failed: {str(e)}",
            duration_ms=duration,
        )


async def check_websocket_connectivity(url: str = None) -> PreflightCheckResult:
    """Check WebSocket endpoint is accessible"""
    start = time.perf_counter()
    url = url or os.environ.get("SYMPHONY_WS_URL", DEFAULT_URLS["websocket"])

    # Extract host and port from ws:// URL
    try:
        import re
        match = re.match(r'wss?://([^:/]+)(?::(\d+))?', url)
        if match:
            host = match.group(1)
            port = int(match.group(2)) if match.group(2) else (443 if url.startswith('wss') else 80)

            # Try TCP connection to verify port is open
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            result = sock.connect_ex((host, port))
            sock.close()

            duration = (time.perf_counter() - start) * 1000

            if result == 0:
                return PreflightCheckResult(
                    name="WebSocket Connectivity",
                    status=CheckStatus.PASS,
                    message=f"WebSocket port {port} accessible on {host}",
                    duration_ms=duration,
                    details={"host": host, "port": port},
                )
            else:
                return PreflightCheckResult(
                    name="WebSocket Connectivity",
                    status=CheckStatus.FAIL,
                    message=f"Cannot connect to WebSocket at {host}:{port}",
                    duration_ms=duration,
                )

    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        return PreflightCheckResult(
            name="WebSocket Connectivity",
            status=CheckStatus.FAIL,
            message=f"WebSocket check failed: {str(e)}",
            duration_ms=duration,
        )

    duration = (time.perf_counter() - start) * 1000
    return PreflightCheckResult(
        name="WebSocket Connectivity",
        status=CheckStatus.SKIP,
        message="Could not parse WebSocket URL",
        duration_ms=duration,
    )


async def check_teams_api() -> PreflightCheckResult:
    """Check MS Teams Graph API connectivity"""
    start = time.perf_counter()

    # Check if Teams credentials are configured
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")

    if not all([tenant_id, client_id, client_secret]):
        duration = (time.perf_counter() - start) * 1000
        return PreflightCheckResult(
            name="Teams API",
            status=CheckStatus.WARN,
            message="Teams credentials not configured - using offline mode",
            duration_ms=duration,
        )

    # Perform actual health check
    is_healthy = await check_teams_health(timeout_seconds=5.0)
    duration = (time.perf_counter() - start) * 1000

    if is_healthy:
        return PreflightCheckResult(
            name="Teams API",
            status=CheckStatus.PASS,
            message="MS Teams Graph API accessible",
            duration_ms=duration,
        )
    else:
        return PreflightCheckResult(
            name="Teams API",
            status=CheckStatus.WARN,
            message="Teams API not responding - offline mode recommended",
            duration_ms=duration,
        )


async def check_llm_api() -> PreflightCheckResult:
    """Check Claude/LLM API connectivity"""
    start = time.perf_counter()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        duration = (time.perf_counter() - start) * 1000
        return PreflightCheckResult(
            name="LLM API",
            status=CheckStatus.FAIL,
            message="ANTHROPIC_API_KEY not set",
            duration_ms=duration,
        )

    is_healthy = await check_llm_health(timeout_seconds=5.0)
    duration = (time.perf_counter() - start) * 1000

    if is_healthy:
        return PreflightCheckResult(
            name="LLM API",
            status=CheckStatus.PASS,
            message="Claude API accessible",
            duration_ms=duration,
        )
    else:
        return PreflightCheckResult(
            name="LLM API",
            status=CheckStatus.WARN,
            message="LLM API check inconclusive - verify manually",
            duration_ms=duration,
        )


async def check_persona_registry() -> PreflightCheckResult:
    """Check persona definitions are loaded"""
    start = time.perf_counter()

    try:
        all_personas = get_all_personas()
        ai_personas = get_ai_personas()
        duration = (time.perf_counter() - start) * 1000

        expected_ai = ["sarah_pm", "marcus_arch", "alex_dev", "priya_qa"]
        missing = [p for p in expected_ai if p not in [persona.id for persona in ai_personas]]

        if missing:
            return PreflightCheckResult(
                name="Persona Registry",
                status=CheckStatus.FAIL,
                message=f"Missing personas: {', '.join(missing)}",
                duration_ms=duration,
                details={"missing": missing},
            )

        return PreflightCheckResult(
            name="Persona Registry",
            status=CheckStatus.PASS,
            message=f"All {len(ai_personas)} AI personas loaded",
            duration_ms=duration,
            details={
                "total_personas": len(all_personas),
                "ai_personas": len(ai_personas),
                "persona_ids": [p.id for p in ai_personas],
            },
        )

    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        return PreflightCheckResult(
            name="Persona Registry",
            status=CheckStatus.FAIL,
            message=f"Failed to load personas: {str(e)}",
            duration_ms=duration,
        )


async def check_offline_scenarios() -> PreflightCheckResult:
    """Check offline fallback scenarios are available"""
    start = time.perf_counter()

    try:
        fallback_mgr = get_fallback_manager()
        scenarios = fallback_mgr.list_scenarios()
        duration = (time.perf_counter() - start) * 1000

        if not scenarios:
            return PreflightCheckResult(
                name="Offline Scenarios",
                status=CheckStatus.FAIL,
                message="No offline scenarios available",
                duration_ms=duration,
            )

        return PreflightCheckResult(
            name="Offline Scenarios",
            status=CheckStatus.PASS,
            message=f"{len(scenarios)} offline scenarios ready",
            duration_ms=duration,
            details={"scenarios": scenarios},
        )

    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        return PreflightCheckResult(
            name="Offline Scenarios",
            status=CheckStatus.FAIL,
            message=f"Failed to check scenarios: {str(e)}",
            duration_ms=duration,
        )


async def check_metrics_system() -> PreflightCheckResult:
    """Check metrics collection system is operational"""
    start = time.perf_counter()

    try:
        collector = get_metrics_collector()
        # Test recording a metric
        collector.increment("preflight_check", 1)
        count = collector.get_counter("preflight_check")
        duration = (time.perf_counter() - start) * 1000

        if count > 0:
            return PreflightCheckResult(
                name="Metrics System",
                status=CheckStatus.PASS,
                message="Metrics collection operational",
                duration_ms=duration,
            )
        else:
            return PreflightCheckResult(
                name="Metrics System",
                status=CheckStatus.WARN,
                message="Metrics recording may not be working",
                duration_ms=duration,
            )

    except Exception as e:
        duration = (time.perf_counter() - start) * 1000
        return PreflightCheckResult(
            name="Metrics System",
            status=CheckStatus.FAIL,
            message=f"Metrics system error: {str(e)}",
            duration_ms=duration,
        )


# =============================================================================
# Preflight Runner
# =============================================================================

async def run_all_preflight_checks(
    skip_external: bool = False,
) -> PreflightReport:
    """
    Run all preflight checks and generate a report.

    Args:
        skip_external: Skip checks that require external services (Teams, LLM)
    """
    start = time.perf_counter()
    checks = []
    recommendations = []

    # Run checks
    checks.append(await check_environment_vars())
    checks.append(await check_persona_registry())
    checks.append(await check_offline_scenarios())
    checks.append(await check_metrics_system())

    if not skip_external:
        checks.append(await check_backend_health())
        checks.append(await check_websocket_connectivity())
        checks.append(await check_teams_api())
        checks.append(await check_llm_api())

    total_duration = (time.perf_counter() - start) * 1000

    # Determine overall status
    fail_count = sum(1 for c in checks if c.status == CheckStatus.FAIL)
    warn_count = sum(1 for c in checks if c.status == CheckStatus.WARN)

    if fail_count > 0:
        overall_status = CheckStatus.FAIL
    elif warn_count > 0:
        overall_status = CheckStatus.WARN
    else:
        overall_status = CheckStatus.PASS

    # Generate recommendations
    for check in checks:
        if check.status == CheckStatus.FAIL:
            if "Environment" in check.name:
                recommendations.append(
                    f"Set missing environment variables: {check.details.get('missing', [])}"
                )
            elif "Backend" in check.name:
                recommendations.append(
                    "Start the Symphony backend: cd maestro-engine && python -m uvicorn src.main:app"
                )
            elif "Teams" in check.name:
                recommendations.append(
                    "Use offline mode if Teams API is unavailable"
                )
            elif "LLM" in check.name:
                recommendations.append(
                    "Verify ANTHROPIC_API_KEY is valid and has credits"
                )
        elif check.status == CheckStatus.WARN:
            if "Teams" in check.name:
                recommendations.append(
                    "Consider running demo in offline mode for reliability"
                )

    # Determine if ready for demo
    ready_for_demo = overall_status != CheckStatus.FAIL
    if fail_count == 0 and warn_count > 0:
        recommendations.append(
            "Demo can proceed with warnings - offline mode recommended"
        )

    return PreflightReport(
        timestamp=datetime.utcnow(),
        overall_status=overall_status,
        checks=checks,
        total_duration_ms=total_duration,
        recommendations=recommendations,
        ready_for_demo=ready_for_demo,
    )


def format_preflight_report(report: PreflightReport) -> str:
    """Format preflight report for console output"""
    lines = []
    lines.append("=" * 60)
    lines.append("SYMPHONY DEMO PREFLIGHT CHECK")
    lines.append("=" * 60)
    lines.append(f"Timestamp: {report.timestamp.isoformat()}")
    lines.append(f"Duration: {report.total_duration_ms:.0f}ms")
    lines.append("")

    # Status indicators
    status_icons = {
        CheckStatus.PASS: "[PASS]",
        CheckStatus.WARN: "[WARN]",
        CheckStatus.FAIL: "[FAIL]",
        CheckStatus.SKIP: "[SKIP]",
    }

    for check in report.checks:
        icon = status_icons[check.status]
        lines.append(f"  {icon} {check.name}")
        lines.append(f"         {check.message}")

    lines.append("")
    lines.append("-" * 60)

    # Overall status
    overall_icon = status_icons[report.overall_status]
    lines.append(f"OVERALL: {overall_icon}")
    lines.append(f"READY FOR DEMO: {'YES' if report.ready_for_demo else 'NO'}")

    # Recommendations
    if report.recommendations:
        lines.append("")
        lines.append("RECOMMENDATIONS:")
        for rec in report.recommendations:
            lines.append(f"  - {rec}")

    lines.append("=" * 60)
    return "\n".join(lines)


# =============================================================================
# Demo Runbook
# =============================================================================

@dataclass
class DemoCheckpoint:
    """A checkpoint in the demo timeline"""
    time_offset: timedelta
    name: str
    description: str
    actions: List[str]
    success_criteria: str


DEMO_RUNBOOK = [
    DemoCheckpoint(
        time_offset=timedelta(minutes=-30),
        name="Pre-Demo Setup",
        description="30 minutes before demo",
        actions=[
            "Run preflight checks: python -m symphony.runbook preflight",
            "Verify Teams channel is accessible",
            "Test WebSocket connection",
            "Clear previous demo artifacts",
            "Reset metrics: POST /symphony/metrics/reset",
        ],
        success_criteria="All preflight checks pass or acceptable warnings",
    ),
    DemoCheckpoint(
        time_offset=timedelta(minutes=-15),
        name="Technical Rehearsal",
        description="15 minutes before demo",
        actions=[
            "Open Symphony Dashboard in browser",
            "Verify split-view layout loads correctly",
            "Test reveal animation with dry run",
            "If using offline mode, start playback and verify",
            "Check audio/video if presenting remotely",
        ],
        success_criteria="Dashboard displays correctly, animations work",
    ),
    DemoCheckpoint(
        time_offset=timedelta(minutes=-5),
        name="Final Preparation",
        description="5 minutes before demo",
        actions=[
            "Create new Symphony session",
            "Position browser window for audience",
            "Mute notifications on all devices",
            "Have backup plan ready (offline scenario)",
            "Take a deep breath",
        ],
        success_criteria="Session created, environment ready",
    ),
    DemoCheckpoint(
        time_offset=timedelta(minutes=0),
        name="Demo Start",
        description="Demo begins",
        actions=[
            "Open with greeting and context",
            "Introduce the 'team' casually",
            "Begin conversation naturally",
        ],
        success_criteria="Audience engaged, conversation starts",
    ),
    DemoCheckpoint(
        time_offset=timedelta(minutes=2),
        name="Act 1: Team Discussion",
        description="AI personas engage in discussion",
        actions=[
            "Monitor typing indicators appearing",
            "Verify responses have natural timing",
            "Guide conversation if needed with human input",
            "Watch for artifact generation in preview panel",
        ],
        success_criteria="Multiple personas responding, artifacts appearing",
    ),
    DemoCheckpoint(
        time_offset=timedelta(minutes=5),
        name="Act 2: Artifact Generation",
        description="Show real-time artifact streaming",
        actions=[
            "Draw attention to Stories tab",
            "Show Architecture diagram forming",
            "Highlight Code preview",
            "Point out Test scenarios",
        ],
        success_criteria="4+ artifacts visible across tabs",
    ),
    DemoCheckpoint(
        time_offset=timedelta(minutes=7),
        name="Act 3: Kickstart Workflow",
        description="Execute full SDLC workflow",
        actions=[
            "Click 'Execute Workflow' button",
            "Narrate progress through phases",
            "Point out real-time updates",
            "Build anticipation for reveal",
        ],
        success_criteria="Workflow progresses through all phases",
    ),
    DemoCheckpoint(
        time_offset=timedelta(minutes=9),
        name="Act 4: The Reveal",
        description="Dramatic AI reveal moment",
        actions=[
            "Pause for effect",
            "Click 'Reveal' button",
            "Let confetti animation play",
            "Allow audience to react",
            "Explain which participants were AI",
        ],
        success_criteria="Audience surprise/engagement, clear reveal",
    ),
    DemoCheckpoint(
        time_offset=timedelta(minutes=10),
        name="Demo Conclusion",
        description="Wrap up and Q&A",
        actions=[
            "Summarize what was demonstrated",
            "Highlight key takeaways",
            "Open for questions",
            "Share resources/links if applicable",
        ],
        success_criteria="Clear conclusion, questions addressed",
    ),
]


def get_demo_runbook() -> List[Dict[str, Any]]:
    """Get demo runbook as serializable list"""
    return [
        {
            "time_offset_minutes": int(cp.time_offset.total_seconds() / 60),
            "name": cp.name,
            "description": cp.description,
            "actions": cp.actions,
            "success_criteria": cp.success_criteria,
        }
        for cp in DEMO_RUNBOOK
    ]


def format_demo_runbook() -> str:
    """Format demo runbook for console output"""
    lines = []
    lines.append("=" * 70)
    lines.append("SYMPHONY DEMO RUNBOOK")
    lines.append("=" * 70)
    lines.append("")

    for checkpoint in DEMO_RUNBOOK:
        offset_min = int(checkpoint.time_offset.total_seconds() / 60)
        if offset_min < 0:
            time_str = f"T{offset_min}min"
        elif offset_min == 0:
            time_str = "T=0 (START)"
        else:
            time_str = f"T+{offset_min}min"

        lines.append(f"[{time_str}] {checkpoint.name}")
        lines.append(f"  {checkpoint.description}")
        lines.append("")
        lines.append("  Actions:")
        for action in checkpoint.actions:
            lines.append(f"    - {action}")
        lines.append("")
        lines.append(f"  Success: {checkpoint.success_criteria}")
        lines.append("-" * 70)

    return "\n".join(lines)


# =============================================================================
# Quick Start Helper
# =============================================================================

async def quick_start_demo(
    offline_mode: bool = False,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Quick start a demo session with all necessary setup.

    Args:
        offline_mode: Whether to start in offline fallback mode
        session_id: Optional session ID (auto-generated if not provided)

    Returns:
        Dict with session info and URLs
    """
    import uuid

    # Generate session ID if needed
    if not session_id:
        session_id = f"symphony_{uuid.uuid4().hex[:12]}"

    # Create trace context
    trace_ctx = TraceContext.new(session_id=session_id)

    # Get fallback manager
    fallback_mgr = get_fallback_manager()

    # Switch to offline mode if requested
    if offline_mode:
        from symphony.offline_fallback import FallbackReason
        fallback_mgr.switch_to_offline(FallbackReason.MANUAL)

    # Reset metrics for fresh demo
    collector = get_metrics_collector()
    collector.reset()

    # Log demo start event
    collector.log_event(
        "demo_started",
        {
            "session_id": session_id,
            "offline_mode": offline_mode,
        },
        trace_ctx=trace_ctx,
    )

    backend_url = os.environ.get("SYMPHONY_BACKEND_URL", DEFAULT_URLS["backend"])
    frontend_url = os.environ.get("SYMPHONY_FRONTEND_URL", DEFAULT_URLS["frontend"])

    return {
        "session_id": session_id,
        "trace_id": trace_ctx.trace_id,
        "mode": "offline" if offline_mode else "live",
        "urls": {
            "dashboard": f"{frontend_url}/symphony?session={session_id}",
            "websocket": f"{backend_url.replace('http', 'ws')}/symphony/ws/{session_id}",
            "api": f"{backend_url}/symphony",
        },
        "fallback_status": fallback_mgr.get_status(),
        "started_at": datetime.utcnow().isoformat(),
    }


# =============================================================================
# CLI Entry Point
# =============================================================================

async def main():
    """CLI entry point for runbook commands"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m symphony.runbook <command>")
        print("")
        print("Commands:")
        print("  preflight    Run preflight checks")
        print("  runbook      Show demo runbook")
        print("  start        Quick start a demo session")
        print("  start-offline  Start in offline mode")
        return

    command = sys.argv[1]

    if command == "preflight":
        report = await run_all_preflight_checks()
        print(format_preflight_report(report))

    elif command == "runbook":
        print(format_demo_runbook())

    elif command == "start":
        result = await quick_start_demo(offline_mode=False)
        print(json.dumps(result, indent=2))

    elif command == "start-offline":
        result = await quick_start_demo(offline_mode=True)
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    asyncio.run(main())
