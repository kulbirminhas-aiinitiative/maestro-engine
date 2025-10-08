#!/usr/bin/env python3
"""
Enhanced Lean Ultimate Mega Team - UTCP Edition
Uses UTCP (Unified TCP) tools for distributed/networked execution
Supports both local Claude SDK tools AND remote UTCP tool endpoints
"""

import asyncio
import hashlib
import logging
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import contextlib
import sys

# HTTP client for UTCP calls
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    logging.warning("⚠️ httpx not available - UTCP features disabled")

# Enhanced dependency management
try:
    from maestro_mcp.unified_claude_tools import generate_with_unified_tools
    CLAUDE_TOOLS_AVAILABLE = True
except ImportError:
    try:
        # Fallback for when running from maestro_mcp directory
        from unified_claude_tools import generate_with_unified_tools
        CLAUDE_TOOLS_AVAILABLE = True
    except ImportError:
        CLAUDE_TOOLS_AVAILABLE = False
        logging.warning("⚠️ unified_claude_tools not available - some features disabled")

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("⚠️ ChromaDB not available - RAG features disabled")

# MCP Cache for event emission
try:
    from maestro_mcp.mcp_cache_config import get_mcp_cache
    MCP_CACHE_AVAILABLE = True
except ImportError:
    try:
        # Fallback for when running from maestro_mcp directory
        from mcp_cache_config import get_mcp_cache
        MCP_CACHE_AVAILABLE = True
    except ImportError:
        MCP_CACHE_AVAILABLE = False
        logging.warning("⚠️ MCP cache not available - event emission disabled")

logger = logging.getLogger(__name__)

@dataclass
class UTCPToolConfig:
    """Configuration for UTCP tool endpoints"""
    enabled: bool = True
    ultimate_team_url: str = "http://localhost:8001/tools/ultimate_unified_mega_team/execute_workflow"
    orchestration_gateway_url: str = "http://localhost:8002/api/orchestrate"
    quality_fabric_url: str = "http://localhost:8000/api/execute"
    template_service_url: str = "http://localhost:9600"
    timeout: int = 600
    retry_count: int = 3
    fallback_to_local: bool = True

@dataclass
class EnhancedTeamConfig:
    """Enhanced configuration with UTCP support"""
    selected_personas: Optional[List[str]] = None
    enable_rag: bool = True
    enable_mcp: bool = True
    enable_event_emission: bool = True
    enable_utcp: bool = True
    session_id: str = ""
    project_path: str = ""
    project_name: str = ""  # Custom project name (just the folder name, not full path)
    max_execution_time: int = 3600
    cache_enabled: bool = True
    async_operations: bool = True
    resource_cleanup: bool = True
    utcp_config: Optional[UTCPToolConfig] = None

    def __post_init__(self):
        if self.selected_personas is None:
            self.selected_personas = [
                "requirement_analyst",
                "solution_architect",
                "frontend_developer",
                "backend_developer",
                "devops_engineer",
                "qa_engineer",
                "security_specialist",
                "ui_ux_designer",
                "technical_writer",
                "deployment_specialist",
                "deployment_integration_tester"
            ]

        if not self.session_id:
            self.session_id = f"enhanced_lean_utcp_{int(time.time())}"

        if self.utcp_config is None:
            self.utcp_config = UTCPToolConfig()

    def validate(self) -> bool:
        """Validate configuration"""
        if not self.selected_personas:
            logging.error("❌ No team members selected")
            return False

        if len(self.selected_personas) > 20:
            logging.warning("⚠️ Large team size may impact performance")

        return True

class UTCPClient:
    """Client for calling UTCP tool endpoints"""

    def __init__(self, config: UTCPToolConfig):
        self.config = config
        self.client = None
        if HTTPX_AVAILABLE:
            self.client = httpx.AsyncClient(timeout=config.timeout)

    async def call_tool(self, tool_name: str, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Call a UTCP tool endpoint with retry logic"""
        if not self.client:
            return {"success": False, "error": "HTTPX not available"}

        last_error = None
        for attempt in range(self.config.retry_count):
            try:
                logger.info(f"🔗 Calling UTCP tool: {tool_name} (attempt {attempt + 1}/{self.config.retry_count})")
                response = await self.client.post(url, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ UTCP tool {tool_name} responded successfully")
                    return result
                else:
                    last_error = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"⚠️ UTCP tool {tool_name} returned {response.status_code}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"⚠️ UTCP tool {tool_name} error (attempt {attempt + 1}): {e}")
                if attempt < self.config.retry_count - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return {"success": False, "error": f"UTCP tool {tool_name} failed after {self.config.retry_count} attempts: {last_error}"}

    async def health_check(self, url: str) -> bool:
        """Check if a UTCP service is healthy"""
        if not self.client:
            return False

        try:
            # Try /health endpoint first
            health_url = url.rsplit('/', 1)[0] + '/health'
            response = await self.client.get(health_url, timeout=5)
            return response.status_code == 200
        except:
            return False

    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()

class EnhancedMCPContext:
    """Enhanced MCP context with better error handling and caching"""

    def __init__(self, session_id: str, cache_dir: Optional[Path] = None, ttl_seconds: int = 3600):
        self.session_id = session_id
        self.mcp_dir = cache_dir or Path("/tmp/mcp_shared_context")
        self.mcp_dir.mkdir(parents=True, exist_ok=True)

        self._context_cache = {}
        self._cache_lock = threading.Lock()
        self.ttl_seconds = ttl_seconds

    async def save_context(self, context: Dict[str, Any]) -> bool:
        try:
            context_file = self.mcp_dir / f"{self.session_id}.json"
            with open(context_file, 'w') as f:
                json.dump(context, f, indent=2)

            with self._cache_lock:
                self._context_cache[self.session_id] = {
                    "data": context,
                    "cached_at": time.time()
                }

            return True
        except Exception as e:
            logging.error(f"MCP context save failed: {e}")
            return False

    def clear_cache(self):
        with self._cache_lock:
            self._context_cache.clear()

class EnhancedRAGEngine:
    """Enhanced RAG with async initialization"""

    def __init__(self, collection_name: str = "enhanced_maestro_history"):
        self.collection_name = collection_name
        self.client = None
        self.collection = None
        self._initialized = False

    async def _initialize(self) -> bool:
        if not CHROMADB_AVAILABLE or self._initialized:
            return self._initialized

        try:
            self.client = chromadb.Client(Settings(anonymized_telemetry=False))
            self.collection = self.client.get_or_create_collection(self.collection_name)
            self._initialized = True
            return True
        except Exception as e:
            logging.error(f"RAG initialization failed: {e}")
            return False

    async def store_execution(self, session_id: str, requirement: str, result: Dict[str, Any]):
        if not await self._initialize():
            return

        try:
            doc_id = f"{session_id}_{int(time.time())}"
            self.collection.add(
                documents=[json.dumps(result)],
                metadatas=[{"session_id": session_id, "requirement": requirement[:200]}],
                ids=[doc_id]
            )
        except Exception as e:
            logging.error(f"RAG store failed: {e}")

    async def close(self):
        self.client = None
        self.collection = None
        self._initialized = False

class EnhancedLeanTeamUTCP:
    """Lean team with UTCP tool support for distributed execution"""

    def __init__(self, config: EnhancedTeamConfig = None, requirement: str = ""):
        self.config = config or EnhancedTeamConfig()
        self.start_time = time.time()
        self.session_id = self.config.session_id

        # Determine project name
        if self.config.project_path:
            # Full path provided - use as-is
            self.project_path = Path(self.config.project_path)
        else:
            # Extract project name from requirement or use config.project_name
            project_name = self.config.project_name
            if not project_name and requirement:
                # Auto-generate from requirement: extract meaningful words
                import re
                words = re.findall(r'\b[a-zA-Z]+\b', requirement.lower())
                # Skip common words
                skip_words = {'create', 'build', 'make', 'develop', 'a', 'an', 'the', 'like', 'for', 'with', 'and', 'or'}
                meaningful_words = [w for w in words if w not in skip_words][:3]
                project_name = "-".join(meaningful_words) if meaningful_words else "project"
            elif not project_name:
                project_name = f"utcp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Standard deployment path + project name
            self.project_path = Path(f"/home/ec2-user/projects/deployment/{project_name}")

        self.project_path.mkdir(parents=True, exist_ok=True)

        self.team_members = self.config.selected_personas
        self._cleanup_scheduled = False
        self._execution_timeout = self.config.max_execution_time

        # Initialize UTCP client
        self.utcp_client = UTCPClient(self.config.utcp_config) if self.config.enable_utcp and HTTPX_AVAILABLE else None

        # Initialize components with error handling
        self.mcp_cache = self._initialize_mcp_cache()
        self.mcp_context = self._initialize_mcp_context()
        self.rag_engine = self._initialize_rag_engine()

        # Caching
        self._prompt_cache = {} if self.config.cache_enabled else None
        self._context_cache = {} if self.config.cache_enabled else None

        # RAG template matching
        self._matched_templates = []

        self._log_initialization()

    def _initialize_mcp_cache(self) -> Optional[Any]:
        """Initialize MCP cache for event emission"""
        if not self.config.enable_event_emission or not MCP_CACHE_AVAILABLE:
            return None

        try:
            return get_mcp_cache()
        except Exception as e:
            logging.warning(f"⚠️ MCP cache initialization failed: {e}")
            return None

    def _initialize_mcp_context(self) -> Optional[EnhancedMCPContext]:
        """Initialize MCP context with fallback"""
        if not self.config.enable_mcp:
            return None

        try:
            return EnhancedMCPContext(self.session_id)
        except Exception as e:
            logging.warning(f"⚠️ MCP context initialization failed: {e}")
            return None

    def _initialize_rag_engine(self) -> Optional[EnhancedRAGEngine]:
        """Initialize RAG engine with fallback"""
        if not self.config.enable_rag or not CHROMADB_AVAILABLE:
            return None

        try:
            return EnhancedRAGEngine()
        except Exception as e:
            logging.warning(f"⚠️ RAG engine initialization failed: {e}")
            return None

    def _emit_event(self, event: Dict[str, Any]):
        """Emit event to MCP cache for external observation"""
        if not self.mcp_cache:
            return

        try:
            event["session_id"] = self.session_id
            event["timestamp"] = datetime.now().isoformat()
            self.mcp_cache.store_workflow_event(event, self.session_id)
        except Exception as e:
            logging.error(f"Event emission failed: {e}")

    def _log_initialization(self):
        """Log initialization with MCP event"""
        logging.info("🚀 ENHANCED LEAN TEAM (UTCP) INITIALIZED")
        logging.info(f"👥 Team: {len(self.team_members)} members")
        logging.info(f"📁 Path: {self.project_path}")
        logging.info(f"🔍 Session: {self.session_id}")
        logging.info(f"🔗 UTCP: {'Enabled' if self.utcp_client else 'Disabled'}")

        self._emit_event({
            "type": "team_initialization",
            "team_members": self.team_members,
            "team_size": len(self.team_members),
            "project_path": str(self.project_path),
            "features": {
                "mcp_cache": self.mcp_cache is not None,
                "mcp_context": self.mcp_context is not None,
                "rag": self.rag_engine is not None,
                "utcp": self.utcp_client is not None,
                "caching": self.config.cache_enabled
            }
        })

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def cleanup(self):
        """Cleanup resources"""
        if self._cleanup_scheduled:
            return

        self._cleanup_scheduled = True

        if self.utcp_client:
            await self.utcp_client.close()

        if self.rag_engine:
            await self.rag_engine.close()

        if self.mcp_context:
            self.mcp_context.clear_cache()

        self._emit_event({
            "type": "cleanup_complete",
            "duration": time.time() - self.start_time
        })

    async def execute_enhanced_workflow(self, requirement: str) -> Dict[str, Any]:
        """Execute enhanced workflow with UTCP tool support"""

        start_time = time.time()

        self._emit_event({
            "type": "workflow_start",
            "requirement": requirement
        })

        result = {
            "success": False,
            "requirement": requirement,
            "session_id": self.session_id,
            "start_time": start_time,
            "team_members": self.team_members,
            "files_generated": [],
            "total_execution_time": 0,
            "execution_method": "unknown"
        }

        try:
            # Execute workflow with timeout
            workflow_result = await asyncio.wait_for(
                self._execute_workflow_async(requirement, result),
                timeout=self._execution_timeout
            )

            result.update(workflow_result)
            result["total_execution_time"] = time.time() - start_time

            self._emit_event({
                "type": "workflow_complete",
                "success": result["success"],
                "execution_time": result["total_execution_time"],
                "execution_method": result.get("execution_method", "unknown"),
                "file_count": len(result.get("files_generated", []))
            })

            # Post-completion quality validation with Quality-Fabric
            if result["success"]:
                await self._run_quality_validation(result)

                # Publish as Git-based template (if credentials provided)
                await self._publish_git_template(result)

        except asyncio.TimeoutError:
            error_msg = f"Workflow timeout after {self._execution_timeout}s"
            result["error"] = error_msg
            self._emit_event({
                "type": "execution_error",
                "error_type": "timeout",
                "error": error_msg
            })

        except Exception as e:
            error_msg = f"Workflow exception: {str(e)}"
            result["error"] = error_msg
            self._emit_event({
                "type": "execution_error",
                "error_type": "exception",
                "error": error_msg
            })

        return result

    async def _execute_workflow_async(self, requirement: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Async workflow execution with UTCP fallback"""

        # Try UTCP first if enabled
        if self.utcp_client and self.config.enable_utcp:
            utcp_result = await self._execute_with_utcp(requirement)
            if utcp_result.get("success"):
                result.update(utcp_result)
                result["execution_method"] = "utcp"
                return result
            elif not self.config.utcp_config.fallback_to_local:
                result["error"] = utcp_result.get("error", "UTCP execution failed")
                result["execution_method"] = "utcp_failed"
                return result
            else:
                logging.info("⚠️ UTCP failed, falling back to local execution")

        # Fallback to local Claude tools
        if CLAUDE_TOOLS_AVAILABLE:
            execution_result = await self._execute_with_unified_tools(requirement)
            result.update(execution_result)
            result["execution_method"] = "local_claude_tools"
        else:
            result["error"] = "No execution method available"
            result["execution_method"] = "none"

        return result

    async def _execute_with_utcp(self, requirement: str) -> Dict[str, Any]:
        """Execute using UTCP tool endpoints"""

        try:
            # Check health of UTCP service
            is_healthy = await self.utcp_client.health_check(
                self.config.utcp_config.ultimate_team_url
            )

            if not is_healthy:
                logging.warning("⚠️ UTCP service health check failed")
                return {"success": False, "error": "UTCP service unhealthy"}

            # Build payload for UTCP call
            payload = {
                "requirement": requirement,
                "selected_personas": self.team_members,
                "enable_rag": self.config.enable_rag,
                "enable_mcp": self.config.enable_mcp,
                "session_id": self.session_id,
                "project_path": str(self.project_path)
            }

            self._emit_event({
                "type": "utcp_call_start",
                "tool": "ultimate_unified_mega_team",
                "payload_size": len(json.dumps(payload))
            })

            # Call UTCP tool
            result = await self.utcp_client.call_tool(
                "ultimate_unified_mega_team",
                self.config.utcp_config.ultimate_team_url,
                payload
            )

            if result.get("success"):
                files = result.get("generated_files", [])

                for file_path in files:
                    self._emit_event({
                        "type": "file_created",
                        "file_path": str(file_path),
                        "file_name": Path(file_path).name,
                        "via": "utcp"
                    })

                self._emit_event({
                    "type": "utcp_call_complete",
                    "tool": "ultimate_unified_mega_team",
                    "file_count": len(files)
                })

                return {
                    "success": True,
                    "files_generated": files,
                    "artifacts": result.get("artifacts", {})
                }
            else:
                self._emit_event({
                    "type": "utcp_call_error",
                    "error": result.get("error", "Unknown")
                })
                return result

        except Exception as e:
            self._emit_event({
                "type": "utcp_call_exception",
                "error": str(e)
            })
            return {
                "success": False,
                "error": f"UTCP execution exception: {str(e)}"
            }

    async def _execute_with_unified_tools(self, requirement: str) -> Dict[str, Any]:
        """Execute using local unified claude tools (fallback)"""

        try:
            # Build persona config
            persona_config = {
                "selected_personas": self.team_members,
                "session_id": self.session_id
            }

            # Get prompt (with caching and RAG enhancement)
            prompt = await self._create_enhanced_prompt(requirement)

            self._emit_event({
                "type": "tool_execution_start",
                "tool": "unified_claude_tools",
                "prompt_length": len(prompt)
            })

            # Execute
            result = await generate_with_unified_tools(
                requirement=prompt,
                persona_config=persona_config,
                project_path=str(self.project_path),
                session_id=self.session_id,
                enable_audit_logging=False  # Handled externally
            )

            if result.get("success"):
                files = result.get("generated_files", [])

                for file_path in files:
                    self._emit_event({
                        "type": "file_created",
                        "file_path": str(file_path),
                        "file_name": Path(file_path).name,
                        "via": "local"
                    })

                return {
                    "success": True,
                    "files_generated": files,
                    "artifacts": result.get("artifacts", {})
                }
            else:
                self._emit_event({
                    "type": "tool_execution_error",
                    "error": result.get("error", "Unknown")
                })
                return {
                    "success": False,
                    "error": result.get("error", "Tool execution failed")
                }

        except Exception as e:
            self._emit_event({
                "type": "tool_execution_exception",
                "error": str(e)
            })
            return {
                "success": False,
                "error": f"Tool execution exception: {str(e)}"
            }

    async def _run_quality_validation(self, result: Dict[str, Any]):
        """Run quality validation via UTCP or local"""
        try:
            # Try UTCP Quality-Fabric first
            if self.utcp_client and self.config.enable_utcp:
                quality_result = await self._run_utcp_quality_validation(result)
                if quality_result:
                    result["quality_validation"] = quality_result
                    result["quality_validation_method"] = "utcp"
                    return

            # Fallback to local Quality-Fabric
            from quality_fabric_client import validate_with_quality_fabric

            self._emit_event({
                "type": "quality_validation_started",
                "method": "local",
                "workflow_session": result.get("session_id", "unknown")
            })

            quality_result = await validate_with_quality_fabric(result)

            if quality_result:
                result["quality_validation"] = {
                    "execution_id": quality_result.execution_id,
                    "quality_score": quality_result.quality_score,
                    "security_score": quality_result.security_score,
                    "performance_score": quality_result.performance_score,
                    "maintainability_score": quality_result.maintainability_score,
                    "test_coverage": quality_result.test_coverage,
                    "test_results": {
                        "total": quality_result.total_tests,
                        "passed": quality_result.passed_tests,
                        "failed": quality_result.failed_tests,
                        "errors": quality_result.error_tests
                    },
                    "duration": quality_result.duration,
                    "recommendations": quality_result.recommendations,
                    "issues": quality_result.issues
                }
                result["quality_validation_method"] = "local"

                self._emit_event({
                    "type": "quality_validation_complete",
                    "method": "local",
                    "quality_score": quality_result.quality_score,
                    "test_pass_rate": (quality_result.passed_tests / max(quality_result.total_tests, 1)) * 100
                })

                # Template extraction
                await self._extract_templates(quality_result, result)

            else:
                result["quality_validation"] = None
                self._emit_event({
                    "type": "quality_validation_skipped",
                    "reason": "Quality-Fabric service unavailable"
                })

        except Exception as qf_error:
            result["quality_validation_error"] = str(qf_error)
            self._emit_event({
                "type": "quality_validation_error",
                "error": str(qf_error)
            })

    async def _run_utcp_quality_validation(self, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Run quality validation via UTCP"""
        try:
            is_healthy = await self.utcp_client.health_check(
                self.config.utcp_config.quality_fabric_url
            )

            if not is_healthy:
                return None

            payload = {
                "project_path": str(self.project_path),
                "session_id": self.session_id,
                "files": result.get("files_generated", [])
            }

            self._emit_event({
                "type": "quality_validation_started",
                "method": "utcp",
                "workflow_session": result.get("session_id", "unknown")
            })

            quality_result = await self.utcp_client.call_tool(
                "quality_fabric",
                self.config.utcp_config.quality_fabric_url,
                payload
            )

            if quality_result.get("success"):
                self._emit_event({
                    "type": "quality_validation_complete",
                    "method": "utcp",
                    "quality_score": quality_result.get("quality_score", 0)
                })
                return quality_result

            return None

        except Exception as e:
            logging.warning(f"⚠️ UTCP quality validation failed: {e}")
            return None

    async def _extract_templates(self, quality_result, result: Dict[str, Any]):
        """Extract templates from high-quality code"""
        try:
            from templates.quality_fabric_template_bridge import create_templates_from_quality_validation

            self._emit_event({
                "type": "template_extraction_started",
                "quality_score": quality_result.quality_score
            })

            template_result = await create_templates_from_quality_validation(
                quality_result,
                result
            )

            result["template_extraction"] = template_result

            if template_result["templates_created"] > 0:
                self._emit_event({
                    "type": "template_extraction_complete",
                    "templates_created": template_result["templates_created"],
                    "template_ids": template_result["template_ids"]
                })
            else:
                self._emit_event({
                    "type": "template_extraction_skipped",
                    "reason": "Quality threshold not met or no extractable patterns"
                })

        except Exception as template_error:
            result["template_extraction_error"] = str(template_error)
            self._emit_event({
                "type": "template_extraction_error",
                "error": str(template_error)
            })

    async def _publish_git_template(self, result: Dict[str, Any]):
        """Publish generated project as Git-based template"""
        import os

        # Check if Git publishing is enabled via environment variables
        github_token = os.getenv("GITHUB_TOKEN", "")
        admin_key = os.getenv("MAESTRO_ADMIN_KEY", "")

        if not github_token or not admin_key:
            logging.debug("⏭️ Git template publishing skipped (missing GITHUB_TOKEN or MAESTRO_ADMIN_KEY)")
            return

        try:
            # Import git template publisher
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from git_template_publisher import GitTemplatePublisher, GitConfig, TemplateRegistrationConfig

            self._emit_event({
                "type": "git_template_publishing_started",
                "project_path": str(self.project_path)
            })

            # Configure Git publishing
            git_config = GitConfig(
                git_provider="github",
                github_token=github_token,
                github_org=os.getenv("GITHUB_ORG", ""),
                make_private=True
            )

            template_config = TemplateRegistrationConfig(
                registry_url=os.getenv("MAESTRO_TEMPLATE_REGISTRY_URL", "http://localhost:9600"),
                admin_api_key=admin_key,
                organization="maestro-generated"
            )

            # Publish project
            async with GitTemplatePublisher(git_config, template_config) as publisher:
                publish_result = await publisher.publish_project(self.project_path)

                if publish_result["success"]:
                    result["git_template_published"] = True
                    result["git_url"] = publish_result["git_url"]
                    result["template_id"] = publish_result["template_id"]

                    self._emit_event({
                        "type": "git_template_published",
                        "git_url": publish_result["git_url"],
                        "template_id": publish_result["template_id"]
                    })

                    logging.info(f"✅ Template published: {publish_result['template_id']}")
                    logging.info(f"   Git URL: {publish_result['git_url']}")
                else:
                    result["git_template_error"] = publish_result.get("error", "Unknown error")
                    self._emit_event({
                        "type": "git_template_publish_failed",
                        "error": publish_result.get("error", "Unknown error")
                    })
                    logging.warning(f"⚠️ Template publishing failed: {publish_result.get('error')}")

        except Exception as e:
            result["git_template_error"] = str(e)
            self._emit_event({
                "type": "git_template_publish_exception",
                "error": str(e)
            })
            logging.warning(f"⚠️ Failed to publish Git template: {e}")

    async def _create_enhanced_prompt(self, requirement: str) -> str:
        """Create enhanced prompt with template context from RAG"""

        # Check cache
        if self._prompt_cache is not None:
            cache_key = hashlib.md5(requirement.encode()).hexdigest()
            if cache_key in self._prompt_cache:
                return self._prompt_cache[cache_key]

        # Try to enhance with RAG templates
        enhanced_requirement = requirement

        if self.config.enable_rag:
            try:
                try:
                    from maestro_mcp.template_rag_integration import TemplateRAGEngine
                except ImportError:
                    from template_rag_integration import TemplateRAGEngine

                async with TemplateRAGEngine(
                    template_registry_url=self.config.utcp_config.template_service_url if self.config.utcp_config else "http://localhost:9600"
                ) as rag:
                    # Search for relevant templates
                    templates = await rag.search_templates(requirement)

                    if templates:
                        # Enhance prompt with template context
                        enhanced_requirement = rag.enhance_prompt_with_templates(requirement, templates)

                        # Store template matches for later use
                        self._matched_templates = templates

                        logging.info(f"✅ Enhanced prompt with {len(templates)} template(s)")
                    else:
                        logging.info("  No relevant templates found for RAG enhancement")

            except Exception as e:
                logging.warning(f"⚠️ RAG enhancement failed: {e} - continuing without templates")

        prompt = f"""You are part of a {len(self.team_members)}-member AI development team.

Team Members: {', '.join(self.team_members)}

{enhanced_requirement}

Generate a complete, production-ready implementation with all necessary files, documentation, and deployment configs.
"""

        # Cache prompt
        if self._prompt_cache is not None:
            self._prompt_cache[cache_key] = prompt

        return prompt


async def execute_enhanced_lean_workflow_utcp(requirement: str, config: EnhancedTeamConfig = None) -> Dict[str, Any]:
    """Execute enhanced lean workflow with UTCP support and automatic cleanup"""

    async with EnhancedLeanTeamUTCP(config, requirement) as team:
        return await team.execute_enhanced_workflow(requirement)


async def main():
    """Main entry point"""
    import sys

    if len(sys.argv) > 1:
        requirement = " ".join(sys.argv[1:])
    else:
        try:
            requirement = input("Enter requirement: ").strip()
        except EOFError:
            requirement = ""

    if not requirement:
        requirement = "Create a modern todo list web application"

    print(f"📋 Requirement: {requirement}")
    print("🔗 Using UTCP-enabled workflow")

    # Configure with UTCP enabled
    config = EnhancedTeamConfig(enable_utcp=True)

    result = await execute_enhanced_lean_workflow_utcp(requirement, config)

    print(f"\n✅ Success: {result['success']}")
    print(f"🔧 Method: {result.get('execution_method', 'unknown')}")
    print(f"📁 Files: {len(result.get('files_generated', []))}")
    print(f"⏱️  Time: {result.get('total_execution_time', 0):.2f}s")

    if result.get("quality_validation"):
        qv = result["quality_validation"]
        print(f"\n📊 Quality Score: {qv.get('quality_score', 'N/A')}")
        print(f"🔒 Security Score: {qv.get('security_score', 'N/A')}")
        print(f"✅ Test Coverage: {qv.get('test_coverage', 'N/A')}%")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main())