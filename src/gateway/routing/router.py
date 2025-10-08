"""
Route Manager

Matches incoming requests to backend services based on path patterns.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class RouteManager:
    """
    Manages route matching and backend service resolution

    Routes are matched in order of specificity:
    1. Exact path match
    2. Prefix match (longest first)
    3. Pattern match (regex)
    """

    def __init__(self, routes: List[Dict]):
        """
        Initialize route manager

        Args:
            routes: List of route configurations from config/gateway_routes.yaml
                Each route has: path, backend, rate_limit, requires_auth, cache_ttl
        """
        self.routes = routes
        self._compile_patterns()
        logger.info(f"RouteManager initialized with {len(routes)} routes")

    def _compile_patterns(self):
        """Compile regex patterns for routes"""
        for route in self.routes:
            path = route["path"]

            # Convert path to regex pattern
            # /api/v1/accelerator/* -> /api/v1/accelerator/.*
            pattern = path.replace("*", ".*")
            if not pattern.endswith(".*"):
                pattern += ".*"

            route["_pattern"] = re.compile(f"^{pattern}$")

    def match_route(self, path: str) -> Optional[Dict]:
        """
        Find matching route for path

        Args:
            path: Request path (e.g., /api/v1/accelerator/projects)

        Returns:
            Route config dict or None if no match
        """
        # Try exact match first
        for route in self.routes:
            if route["path"] == path:
                logger.debug(f"Exact match: {path} -> {route['backend']}")
                return route

        # Try prefix match (longest first)
        matching_routes = []
        for route in self.routes:
            if path.startswith(route["path"].rstrip("/*")):
                matching_routes.append(route)

        if matching_routes:
            # Sort by path length (longest first)
            matching_routes.sort(key=lambda r: len(r["path"]), reverse=True)
            route = matching_routes[0]
            logger.debug(f"Prefix match: {path} -> {route['backend']}")
            return route

        # Try pattern match
        for route in self.routes:
            if "_pattern" in route and route["_pattern"].match(path):
                logger.debug(f"Pattern match: {path} -> {route['backend']}")
                return route

        # No match found
        logger.warning(f"No route match found for: {path}")
        return None

    def get_backend_url(self, path: str) -> Optional[str]:
        """
        Get backend URL for path

        Args:
            path: Request path

        Returns:
            Backend URL or None if no match
        """
        route = self.match_route(path)
        return route["backend"] if route else None

    def list_routes(self) -> List[Dict]:
        """List all routes (for debugging)"""
        return [
            {"path": r["path"], "backend": r["backend"], "rate_limit": r.get("rate_limit", "N/A")}
            for r in self.routes
        ]
