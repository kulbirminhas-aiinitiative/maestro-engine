"""
MAESTRO API Gateway

Part of ADR-003: API Gateway Pattern

Single entry point for all client requests to MAESTRO platform services.

Features:
- Centralized authentication (JWT validation)
- Rate limiting (per client/endpoint)
- CORS handling
- Circuit breaker integration (ADR-006)
- Request/response logging
- Response caching
- Dynamic routing to backend services
- WebSocket proxying

Usage:
    # Start gateway on port 8080
    uvicorn src.gateway.main:app --port 8080 --host 0.0.0.0
"""

__version__ = "1.0.0"
