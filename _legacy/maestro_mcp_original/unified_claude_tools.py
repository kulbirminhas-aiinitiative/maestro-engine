#!/usr/bin/env python3
"""
Unified Claude SDK Tools for File Generation and Document Management
Replaces separate DocumentWriterAgent and caching mechanisms
Integrated with MCP (Model Context Protocol) cache for enhanced information sharing
Now with comprehensive audit logging support
"""

import asyncio
import json
import logging
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from claude_code_sdk import tool, query, ClaudeCodeOptions

# Import MCP cache
try:
    from .mcp_cache_config import get_mcp_cache, configure_mcp_tools
    MCP_AVAILABLE = True
except ImportError as e:
    logger.debug(f"MCP cache import failed: {e}")
    MCP_AVAILABLE = False

logger = logging.getLogger(__name__)

# Global toolset instance for Claude SDK tool access
_current_toolset = None

def set_current_toolset(toolset):
    """Set the current toolset for Claude SDK tool access"""
    global _current_toolset
    _current_toolset = toolset

# Module-level tool functions that Claude SDK can access
@tool(
    name="create_code_file",
    description="Create a code file with proper syntax highlighting",
    input_schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "content": {"type": "string"},
            "language": {"type": "string"},
            "purpose": {"type": "string"}
        },
        "required": ["filename", "content"]
    }
)
def create_code_file(filename: str, content: str, language: str = "", purpose: str = "") -> str:
    """Claude tool: Create a code file with proper syntax highlighting"""
    if _current_toolset:
        return _current_toolset._create_file(filename, content, "code", {"language": language, "purpose": purpose})
    return "Error: No toolset available"

@tool(
    name="create_documentation",
    description="Create documentation files",
    input_schema={
        "type": "object", 
        "properties": {
            "filename": {"type": "string"},
            "content": {"type": "string"},
            "doc_type": {"type": "string"}
        },
        "required": ["filename", "content"]
    }
)
def create_documentation(filename: str, content: str, doc_type: str = "markdown") -> str:
    """Claude tool: Create documentation files"""
    if _current_toolset:
        return _current_toolset._create_file(filename, content, "documentation", {"doc_type": doc_type})
    return "Error: No toolset available"

@tool(
    name="create_config_file",
    description="Create configuration files",
    input_schema={
        "type": "object",
        "properties": {
            "filename": {"type": "string"},
            "config_data": {"type": "object"},
            "format": {"type": "string"}
        },
        "required": ["filename", "config_data"]
    }
)
def create_config_file(filename: str, config_data: dict, format: str = "json") -> str:
    """Claude tool: Create configuration files"""
    if _current_toolset:
        return _current_toolset._create_config_file(filename, config_data, format)
    return "Error: No toolset available"

@tool(
    name="save_persona_analysis",
    description="Save persona analysis to MCP cache",
    input_schema={
        "type": "object",
        "properties": {
            "persona_name": {"type": "string"},
            "analysis_data": {"type": "object"},
            "include_files": {"type": "boolean"}
        },
        "required": ["persona_name", "analysis_data"]
    }
)
def save_persona_analysis(persona_name: str, analysis_data: dict, include_files: bool = True) -> str:
    """Claude tool: Save persona analysis to MCP cache"""
    if _current_toolset:
        return _current_toolset._save_analysis(persona_name, analysis_data, include_files)
    return "Error: No toolset available"

@tool(
    name="get_previous_context",
    description="Get work from previous personas",
    input_schema={
        "type": "object",
        "properties": {
            "exclude_current_persona": {"type": "boolean"}
        },
        "required": []
    }
)
def get_previous_context(exclude_current_persona: bool = True) -> str:
    """Claude tool: Get work from previous personas"""
    if _current_toolset:
        return _current_toolset._get_previous_context(exclude_current_persona)
    return "Error: No toolset available"

@tool(
    name="list_artifacts",
    description="List created artifacts",
    input_schema={
        "type": "object",
        "properties": {
            "artifact_type": {"type": "string"}
        },
        "required": []
    }
)
def list_artifacts(artifact_type: str = "") -> str:
    """Claude tool: List created artifacts"""
    if _current_toolset:
        return _current_toolset._list_artifacts(artifact_type)
    return "Error: No toolset available"

class UnifiedClaudeToolset:
    """
    Single unified toolset for all file operations, document generation, and state management
    Replaces: DocumentWriterAgent, cache writers, text parsing
    Enhanced with MCP (Model Context Protocol) cache for cross-persona information sharing
    """
    
    def __init__(self, project_path: str, persona_name: str = "", session_id: str = ""):
        # Ensure project_path is always a Path object
        self.project_path = Path(project_path) if not isinstance(project_path, Path) else project_path
        self.session_state = {}
        self.generated_artifacts = {}
        self.logger = logger
        self.persona_name = persona_name
        self.session_id = session_id or str(uuid.uuid4())
        
        # Initialize MCP cache if available
        if MCP_AVAILABLE:
            self.mcp_cache = get_mcp_cache()
            self.mcp_tools = configure_mcp_tools(persona_name, self.session_id)
            logger.info(f"✅ MCP cache enabled for {persona_name} in session {self.session_id}")
        else:
            self.mcp_cache = None
            self.mcp_tools = []
            logger.warning("⚠️ MCP cache not available - falling back to local state")

    def _create_file(self, filename: str, content: str, artifact_type: str, metadata: dict = None) -> str:
        """Internal method to create files and track artifacts"""
        try:
            # Ensure project_path is a Path object (defensive programming)
            if not isinstance(self.project_path, Path):
                self.project_path = Path(self.project_path)

            file_path = self.project_path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_path.write_text(content)
            
            # Track in generated artifacts
            self.generated_artifacts.setdefault(artifact_type, []).append({
                "filename": filename,
                "path": str(file_path),
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            })
            
            self.logger.info(f"✅ Created {artifact_type} file: {filename}")
            return f"Successfully created {artifact_type} file: {filename}"
            
        except Exception as e:
            error_msg = f"Failed to create file {filename}: {str(e)}"
            self.logger.error(error_msg)
            return error_msg

    def _create_config_file(self, filename: str, config_data: dict, format: str = "json") -> str:
        """Create configuration files in various formats"""
        try:
            if format == "json":
                content = json.dumps(config_data, indent=2)
            elif format == "yaml":
                import yaml
                content = yaml.dump(config_data, default_flow_style=False)
            else:
                content = str(config_data)
            
            return self._create_file(filename, content, "configuration", {"format": format})
        except Exception as e:
            return f"Failed to create config file: {str(e)}"

    def _save_analysis(self, persona_name: str, analysis_data: dict, include_files: bool = True) -> str:
        """Save persona analysis with MCP cache integration"""
        try:
            # Save analysis data to file
            analysis_file = f"{persona_name}_analysis.json"
            analysis_content = json.dumps(analysis_data, indent=2)
            
            result = self._create_file(analysis_file, analysis_content, "analysis", {"persona": persona_name})
            
            # Store in local session state
            self.session_state[persona_name] = {
                "analysis": analysis_data,
                "timestamp": datetime.now().isoformat(),
                "files_generated": include_files
            }
            
            # Store in MCP cache for cross-persona sharing
            if self.mcp_cache:
                cache_key = self.mcp_cache.store_persona_analysis(
                    persona_name, 
                    str(analysis_data), 
                    analysis_data, 
                    self.session_id
                )
                logger.info(f"📚 Stored {persona_name} analysis in MCP cache: {cache_key}")
            
            return result
        except Exception as e:
            return f"Failed to save analysis: {str(e)}"

    def _get_previous_context(self, exclude_current_persona: bool = True) -> str:
        """Get context from previous personas in this session"""
        try:
            if not self.mcp_cache:
                return json.dumps({"error": "MCP cache not available", "previous_work": {}})
            
            exclude_persona = self.persona_name if exclude_current_persona else ""
            previous_work = self.mcp_cache.get_previous_persona_work(self.session_id, exclude_persona)
            
            return json.dumps({
                "session_id": self.session_id,
                "previous_personas_count": len(previous_work),
                "previous_work": previous_work,
                "context_available": len(previous_work) > 0
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e), "previous_work": {}})

    def _list_artifacts(self, artifact_type: str = "all") -> str:
        """List generated artifacts by type"""
        if artifact_type == "all":
            return json.dumps(self.generated_artifacts, indent=2)
        else:
            return json.dumps(self.generated_artifacts.get(artifact_type, []), indent=2)

    def get_generated_files_list(self) -> List[str]:
        """Get list of all generated file paths"""
        files = []
        for artifact_list in self.generated_artifacts.values():
            if isinstance(artifact_list, list):
                for artifact in artifact_list:
                    if isinstance(artifact, dict) and "path" in artifact:
                        files.append(artifact["path"])
                    elif isinstance(artifact, str):
                        files.append(artifact)
        return files


async def generate_with_unified_tools(requirement: str, persona_config: dict,
                                    project_path: str, session_id: str = "",
                                    enable_audit_logging: bool = True) -> Dict[str, Any]:
    """
    Generate complete project using unified Claude SDK tools with MCP cache integration
    Replaces: DocumentWriterAgent + file parsing + caching
    Now with comprehensive audit logging for prompts and responses
    """
    try:
        persona_info = persona_config.get("persona", {})
        persona_name = persona_info.get("role", persona_info.get("name", "ai_agent"))

        # Initialize toolset with MCP cache support
        toolset = UnifiedClaudeToolset(project_path, persona_name, session_id)

        # Initialize audit logger if enabled
        audit_logger = None
        if enable_audit_logging:
            try:
                from maestro_audit_logger import MaestroAuditLogger
                audit_logger = MaestroAuditLogger(
                    session_id=session_id or "default",
                    project_path=Path(project_path),
                    full_content_logging=True
                )
                logger.info("📋 Audit logging enabled for this session")
            except ImportError:
                logger.warning("⚠️ Audit logger not available - continuing without audit logs")
                audit_logger = None
        
        # Set the global toolset instance so Claude SDK tools can access it
        set_current_toolset(toolset)
        
        # Create comprehensive prompt with all available tools including MCP context
        mcp_context_info = ""
        if toolset.mcp_cache:
            # Get previous context for this persona to build upon
            previous_context = toolset.mcp_cache.get_previous_persona_work(session_id, persona_name)
            if previous_context:
                mcp_context_info = f"""

PREVIOUS WORK CONTEXT (from MCP cache):
{json.dumps(previous_context, indent=2)}

Build upon this previous work and maintain consistency with earlier decisions.
"""
        
        # Add deployment-specific enhancements for deployment_specialist persona
        deployment_enhancement = ""
        if "deployment" in persona_name.lower():
            deployment_enhancement = """

🚀 DEPLOYMENT SPECIALIST CRITICAL INSTRUCTIONS:

You are not just approving deployment - you must EXECUTE the actual deployment with SMART PORT ALLOCATION.

MANDATORY DEPLOYMENT EXECUTION STEPS:

1. **PORT REGISTRY ALLOCATION** (REQUIRED):
   Use the Enhanced Deployment Manager to automatically allocate available ports:
   ```bash
   cd /data/maestro-v1
   python3 enhanced_deployment_manager.py plan {project_path}
   python3 enhanced_deployment_manager.py deploy {project_path}
   ```
   
   This will:
   - Automatically find available ports in the 3100+ range
   - Update docker-compose.yml with allocated ports  
   - Register ports in services_registry.json
   - Avoid port conflicts with existing services

2. **DEPLOYMENT VERIFICATION** (REQUIRED):
   ```bash
   python3 enhanced_deployment_manager.py status {project_path}
   ```

3. **ALTERNATIVE MANUAL DEPLOYMENT** (if automated fails):
   - Check available ports: `python3 port_registry_manager.py available --count 2`
   - Update docker-compose.yml with available ports
   - Execute: `docker-compose down && docker-compose up -d --build`
   - Test all service endpoints

DEPLOYMENT SUCCESS CRITERIA:
✅ Ports allocated from registry (no conflicts)
✅ Services started successfully  
✅ Application accessible via allocated URLs
✅ Health checks passing
✅ Registry updated with deployment info
✅ Access URLs documented with actual ports

CRITICAL: Always use the port registry system to avoid conflicts. Never hardcode ports 80/8000/etc.

"""
        
        prompt = f"""
You are {persona_info.get('name', 'AI Developer')}, a {persona_info.get('role', 'specialist')}.

REQUIREMENT: {requirement}

ENHANCED CONTEXT: {persona_config.get('enhanced_context', {})}
{mcp_context_info}
{deployment_enhancement}

You have access to these tools for creating complete project deliverables:

CORE FILE CREATION:
- Write: Create any type of file (code, documentation, config, etc.)
- Edit: Modify existing files
- MultiEdit: Edit multiple files at once
- Read: Read existing files to understand current state
- Bash: Execute terminal commands (CRITICAL for deployment specialists)

INSTRUCTIONS:
1. Analyze the requirement thoroughly considering any previous work
2. Create appropriate project structure and files using the Write tool
3. Generate all necessary files: source code, documentation, configuration files
4. Make architectural and design decisions appropriate to your role
5. Create complete, production-ready implementations

CRITICAL: Use the Write tool to directly create all files - do not provide explanations, just create the files.
Focus on creating a complete, working implementation that addresses the requirement.
Be comprehensive and create multiple files as needed for a complete solution.

BEGIN IMPLEMENTATION:
"""

        # Configure Claude with built-in tools that actually work
        options = ClaudeCodeOptions()
        
        # Ensure project path exists before Claude execution
        project_path_obj = Path(project_path)
        project_path_obj.mkdir(parents=True, exist_ok=True)
        
        # Use Claude SDK's built-in tools that we know work
        # Based on the test, these tools are available: Write, Read, Edit, MultiEdit, etc.
        enhanced_tools = [
            "Write",       # Create files (replaces create_code_file, create_documentation)
            "Read",        # Read files 
            "Edit",        # Edit files
            "MultiEdit",   # Edit multiple files
            "Bash",        # Run commands
            "Task"         # Task management
        ]
        
        options.allowed_tools = enhanced_tools
        options.cwd = str(project_path)
        
        logger.info(f"🔄 Generating project using Claude SDK built-in tools...")
        logger.info(f"🔧 Available tools: {enhanced_tools}")

        # Log prompt to audit if enabled
        if audit_logger:
            audit_logger.log_performance_metric("prompt_generation", 0, "milliseconds", {"persona": persona_name})

        # Execute with built-in Claude SDK tools
        execution_start = time.time()
        responses = []
        created_files = []
        full_response_text = ""

        async for message in query(prompt=prompt, options=options):
            message_str = str(message)
            responses.append(message_str)
            full_response_text += message_str
            
            # Track files created by the Write tool
            message_str = str(message)
            if "ToolUseBlock" in message_str and "Write" in message_str:
                # Extract file path from Write tool usage
                import re
                file_path_match = re.search(r"'file_path': '([^']+)'", message_str)
                if file_path_match:
                    file_path = file_path_match.group(1)
                    created_files.append(file_path)
                    logger.info(f"📁 Detected file creation: {file_path}")

                    # Emit MCP event for real-time progress tracking
                    if toolset.mcp_cache:
                        toolset.mcp_cache.store_workflow_event({
                            "type": "file_created",
                            "file_path": file_path,
                            "persona": persona_name,
                            "timestamp": datetime.now().isoformat()
                        }, toolset.session_id)
            
        # Check if any tools were actually called by examining the toolset state
        files_generated = created_files  # Use files detected from Write tool usage
        execution_duration = time.time() - execution_start

        logger.info(f"🎯 Claude execution completed")
        logger.info(f"📁 Files generated: {len(files_generated)}")

        # Log complete interaction to audit
        if audit_logger:
            audit_logger.log_claude_interaction(
                prompt=prompt,
                response=full_response_text,
                model="claude-sonnet-4",
                duration_seconds=execution_duration,
                metadata={
                    "persona": persona_name,
                    "requirement": requirement,
                    "files_generated": len(files_generated),
                    "session_id": session_id
                }
            )
            audit_logger.log_performance_metric("claude_execution", execution_duration, "seconds")

            # Log file operations
            for file_path in files_generated:
                audit_logger.log_file_operation("create", file_path, success=True)
        
        if not files_generated:
            logger.warning("⚠️ No files generated - Claude may not have used the Write tool")
            logger.info(f"📝 Claude responses: {responses[:2]}")  # Show first 2 responses for debugging
        
        # Update toolset artifacts with detected files
        for file_path in files_generated:
            if Path(file_path).exists():
                toolset.generated_artifacts.setdefault("created_files", []).append({
                    "path": file_path,
                    "created_at": datetime.now().isoformat(),
                    "method": "claude_write_tool"
                })
        
        # Cleanup expired cache entries
        if toolset.mcp_cache:
            expired_count = toolset.mcp_cache.cleanup_expired()
            if expired_count > 0:
                logger.info(f"🧹 Cleaned up {expired_count} expired MCP cache entries")

        # Finalize audit logging and get summary
        audit_summary = None
        if audit_logger:
            audit_summary = audit_logger.finalize_session()
            logger.info(f"📋 Audit logs saved to: {audit_logger.audit_path}")

        return {
            "success": True,
            "generated_files": files_generated,  # Use detected files from Write tool
            "artifacts": toolset.generated_artifacts,
            "session_state": toolset.session_state,
            "session_id": toolset.session_id,
            "mcp_cache_enabled": toolset.mcp_cache is not None,
            "method": "claude_builtin_tools",
            "file_count": len(files_generated),
            "audit_summary": audit_summary
        }
        
    except Exception as e:
        logger.error(f"Unified generation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "method": "unified_claude_tools_failed"
        }


@tool(
    name="create_project_structure",
    description="Create directory structure for a project",
    input_schema={
        "type": "object",
        "properties": {
            "structure": {
                "type": "object",
                "description": "Nested directory structure as dict"
            }
        },
        "required": ["structure"]
    }
)
def create_project_structure(structure: dict) -> str:
    """Claude tool: Create project directory structure"""
    if _current_toolset:
        try:
            def create_dirs(base_path: Path, struct: dict):
                for key, value in struct.items():
                    dir_path = base_path / key
                    dir_path.mkdir(parents=True, exist_ok=True)
                    if isinstance(value, dict):
                        create_dirs(dir_path, value)

            create_dirs(_current_toolset.project_path, structure)
            return json.dumps({"success": True, "directories": list(structure.keys())})
        except Exception as e:
            return json.dumps({"error": str(e), "success": False})
    return json.dumps({"error": "No toolset available", "success": False})


if __name__ == "__main__":
    # Test unified approach
    async def test_unified_generation():
        test_config = {
            "persona": {
                "name": "Full Stack Developer",
                "role": "senior developer"
            }
        }

        result = await generate_with_unified_tools(
            "Create a task management web application with React frontend and Node.js backend",
            test_config,
            "/tmp/unified_test_project"
        )

        print(f"Unified generation result: {result}")

    asyncio.run(test_unified_generation())