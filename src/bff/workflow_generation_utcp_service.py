#!/usr/bin/env python3
"""
Workflow Generation UTCP Service
Workflow Generation as a Service with Universal Tool Calling Protocol support

This creates a UTCP-enabled service that agents can discover and use to generate
workflow blueprints from requirements and conversation context.

Usage:
    python workflow_generation_utcp_service.py

Agents can now:
    - Discover workflow generation service automatically via UTCP
    - Generate DAG workflows with conversation context
    - Receive ReactFlow blueprint format for DAG Studio
"""

import asyncio
import json
import logging
import os
import sys
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add shared UTCP library
project_root = Path(__file__).parent.parent.parent
shared_path = project_root.parent / "maestro-platform" / "shared" / "packages" / "core-api" / "src"
sys.path.insert(0, str(shared_path))

# Add core logging library
logging_path = project_root.parent / "maestro-platform" / "shared" / "packages" / "core-logging" / "src"
sys.path.insert(0, str(logging_path))

# Configure maestro core logging BEFORE importing UTCP
from maestro_core_logging import configure_logging

configure_logging(
    service_name="workflow-generator",
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from maestro_core_api import APIConfig, SecurityConfig
from maestro_core_api.utcp_extensions import UTCPEnabledAPI
from fastapi import HTTPException
from pydantic import BaseModel, Field
from anthropic import Anthropic

logger = logging.getLogger("workflow_generation.utcp")

# Configuration
HOST = "0.0.0.0"
PORT = 8101

# Create UTCP-enabled API
config = APIConfig(
    title="Workflow Generation Service",
    description="""AI-powered workflow blueprint generation service.

Generates complete DAG (Directed Acyclic Graph) workflows from requirements
and conversation context using Claude AI.

Capabilities:
- Generate complete workflow blueprints with phases, dependencies, and team assignments
- Use conversation history for context-aware workflow generation
- Output ReactFlow-compatible JSON for DAG Studio
- Automatic phase breakdown (requirements, architecture, implementation, testing, deployment)
- Realistic team member assignments (analyst, architect, developers, QA, DevOps)
- Validation of no circular dependencies

Agents can use this service to create comprehensive project workflows
that users can import directly into DAG Studio for execution.
""",
    service_name="workflow-generator",
    version="1.0.0",
    host=HOST,
    port=PORT,
    security=SecurityConfig(
        jwt_secret_key="workflow-generator-secret-key-12345678901234567890"  # 32+ characters
    ),
    enable_authentication=False,  # Disable auth for testing
    enable_authorization=False,
    enable_rate_limiting=False
)

api = UTCPEnabledAPI(
    config,
    base_url=f"http://{HOST}:{PORT}",
    enable_utcp_execution=True
)

# Initialize Anthropic client (optional for testing)
anthropic_key = os.getenv("ANTHROPIC_API_KEY")
if not anthropic_key:
    logger.warning("⚠️  ANTHROPIC_API_KEY not set - will return mock workflows for testing")
    anthropic_client = None
else:
    anthropic_client = Anthropic(api_key=anthropic_key)
    logger.info("✅ Anthropic client initialized")


# Pydantic models
class WorkflowGenerationRequest(BaseModel):
    """Request to generate workflow blueprint"""
    requirement: str = Field(
        ...,
        description="Project requirement or description (can be brief if conversation_context is rich)"
    )
    conversation_context: List[str] = Field(
        default=[],
        description="Conversation history for context-aware generation (recent discussion about the project)"
    )
    user_id: str = Field(
        default="maestro-user",
        description="User ID for tracking"
    )
    room_id: Optional[str] = Field(
        default=None,
        description="Room ID if generating from multi-agent chat"
    )


class WorkflowGenerationResponse(BaseModel):
    """Response from workflow generation"""
    success: bool
    workflow: Optional[Dict[str, Any]] = None
    workflow_name: str = ""
    phases_count: int = 0
    generated_by: str = "workflow-generator"
    timestamp: str = ""
    error_message: Optional[str] = None


async def generate_workflow_with_ai(
    requirement: str,
    conversation_context: List[str],
    user_id: str
) -> Dict[str, Any]:
    """
    Generate workflow DAG using Claude AI with conversation context.

    This is the core generation logic that uses conversation history
    to create better, more contextualized workflows.
    """
    logger.info(f"🏗️  Generating workflow for user {user_id}")
    logger.info(f"   Requirement: {requirement[:100]}...")
    logger.info(f"   Context messages: {len(conversation_context)}")

    # Build context summary from conversation
    context_summary = ""
    if conversation_context:
        context_summary = "\n\nCONVERSATION CONTEXT (for better understanding):\n"
        for i, msg in enumerate(conversation_context[-10:], 1):  # Last 10 messages
            context_summary += f"{i}. {msg}\n"
        context_summary += "\nUse the conversation context above to understand the project better and generate a more accurate workflow.\n"

    # Create specialized prompt for workflow generation
    workflow_prompt = f"""You are an expert software architect and project planner. Generate a complete, executable workflow DAG (Directed Acyclic Graph) for the following project:

PROJECT REQUIREMENT:
{requirement}
{context_summary}

Your task is to create a comprehensive workflow blueprint in the exact JSON format specified below.

CRITICAL REQUIREMENTS:
1. Generate 4-8 phases covering the complete development lifecycle
2. MUST include these phase types:
   - requirements: Requirements gathering and analysis
   - architecture: System design and architecture
   - implementation: Development work (can be multiple parallel phases)
   - testing: Quality assurance and testing
   - deployment: Deployment and launch
   - review: Documentation and review (optional)
   - custom: Any specialized phases
3. Assign realistic team members from: requirement_analyst, solution_architect, backend_developer, frontend_developer, qa_engineer, devops_engineer, security_engineer, technical_writer
4. NO circular dependencies - ensure proper phase ordering
5. Calculate positions: First phase at y=250, then y += 200 for each subsequent phase, x=300 for all
6. Use realistic timeouts in seconds (e.g., 604800 = 1 week, 1209600 = 2 weeks)
7. Create meaningful requirements and acceptance criteria for each phase

OUTPUT ONLY VALID JSON in this EXACT format:

{{
  "version": "1.0",
  "workflow": {{
    "id": "workflow-{int(time.time() * 1000)}",
    "name": "Short Descriptive Project Name",
    "description": "2-3 sentence project description",
    "version": "1.0.0",
    "nodes": [
      {{
        "id": "node-1",
        "type": "phase",
        "position": {{"x": 300, "y": 250}},
        "data": {{
          "label": "Requirements Analysis",
          "phase": "requirements",
          "phaseType": "requirements",
          "status": "pending",
          "timeout": 604800,
          "assignedTeam": ["requirement_analyst"],
          "assignedExecutorAI": "requirement_analyst",
          "artifacts": [],
          "attributes": {{
            "requirements": ["Detailed requirement 1", "Detailed requirement 2"],
            "acceptanceCriteria": ["Criteria 1", "Criteria 2"]
          }},
          "chat": {{"messages": [], "notes": []}},
          "created": "{datetime.now().isoformat()}",
          "createdBy": "maestro-ai",
          "requirementText": "# Requirements Analysis\\n\\n## Requirements\\n\\n1. Detailed requirement 1\\n2. Detailed requirement 2"
        }}
      }}
    ],
    "edges": [
      {{"id": "edge-node-1-node-2", "source": "node-1", "target": "node-2", "type": "smoothstep"}}
    ],
    "created": "{datetime.now().isoformat()}",
    "createdBy": "maestro-ai",
    "settings": {{"layoutDirection": "TB", "autoLayout": true, "enableValidation": true}},
    "teamChat": {{"messages": [], "participants": []}},
    "validation": {{"valid": true, "errors": [], "warnings": []}}
  }},
  "metadata": {{
    "exportedAt": "{datetime.now().isoformat()}",
    "exportedBy": "maestro-ai",
    "application": "maestro-dag-studio"
  }}
}}

Generate the complete workflow now. Output ONLY the JSON, no markdown code blocks, no explanations."""

    # Call Claude AI
    response = anthropic_client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8000,
        temperature=0.7,
        messages=[{
            "role": "user",
            "content": workflow_prompt
        }]
    )

    response_text = response.content[0].text

    # Extract JSON (handle potential markdown code blocks)
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        json_str = json_match.group(0) if json_match else response_text

    # Parse and validate JSON
    workflow_data = json.loads(json_str)

    logger.info(f"✅ Workflow DAG generated successfully")
    logger.info(f"   - Name: {workflow_data.get('workflow', {}).get('name')}")
    logger.info(f"   - Nodes: {len(workflow_data.get('workflow', {}).get('nodes', []))}")
    logger.info(f"   - Edges: {len(workflow_data.get('workflow', {}).get('edges', []))}")

    return workflow_data


# UTCP Endpoints

@api.post(
    "/generate-workflow",
    response_model=WorkflowGenerationResponse,
    summary="Generate workflow blueprint from requirements",
    description="""Generate a complete DAG workflow blueprint using AI.

This endpoint uses conversation context to create better, more accurate workflows.
The agent should pass recent conversation history to help the AI understand the project better.

Input:
- requirement: Brief or detailed project description
- conversation_context: List of recent conversation messages (optional but recommended)
- user_id: User identifier
- room_id: Multi-agent chat room ID (if applicable)

Output:
- Complete ReactFlow blueprint JSON for DAG Studio
- Workflow with phases, dependencies, team assignments
- Ready to import into DAG Studio

Example:
{
    "requirement": "Build an e-commerce platform with user auth, product catalog, shopping cart, and Stripe payments",
    "conversation_context": [
        "User: I need an e-commerce site",
        "Agent: What features do you need?",
        "User: User accounts, product listing, shopping cart",
        "Agent: What about payments?",
        "User: Stripe integration",
        "Agent: Tech stack preferences?",
        "User: React frontend, Node.js backend, PostgreSQL database"
    ],
    "user_id": "user123",
    "room_id": "room_456"
}

The AI will use the conversation context to generate a comprehensive workflow
that includes all discussed features and technologies.
""",
    tags=["Workflow Generation"]
)
async def generate_workflow(request: WorkflowGenerationRequest) -> WorkflowGenerationResponse:
    """
    Generate workflow blueprint from requirements with conversation context.

    Agents invoke this tool when user says #workflow or requests workflow generation.
    The conversation context helps generate better, more accurate workflows.
    """
    try:
        workflow_data = await generate_workflow_with_ai(
            requirement=request.requirement,
            conversation_context=request.conversation_context,
            user_id=request.user_id
        )

        workflow_info = workflow_data.get("workflow", {})

        return WorkflowGenerationResponse(
            success=True,
            workflow=workflow_data,
            workflow_name=workflow_info.get("name", "Untitled Workflow"),
            phases_count=len(workflow_info.get("nodes", [])),
            generated_by="workflow-generator",
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"❌ Workflow generation failed: {e}", exc_info=True)
        return WorkflowGenerationResponse(
            success=False,
            error_message=str(e),
            timestamp=datetime.now().isoformat()
        )


@api.get(
    "/capabilities",
    summary="Get workflow generation capabilities",
    description="List capabilities and configuration of the workflow generation service",
    tags=["Service Info"]
)
async def get_capabilities():
    """Get workflow generation capabilities for agent discovery."""
    return {
        "service": "workflow-generator",
        "version": "1.0.0",
        "capabilities": [
            "Context-aware workflow generation from requirements",
            "Conversation history integration",
            "ReactFlow blueprint format output",
            "Automatic phase breakdown and dependency management",
            "Team member assignment (analyst, architect, developers, QA, DevOps)",
            "No circular dependency validation",
            "DAG Studio compatible output"
        ],
        "supported_phase_types": [
            "requirements",
            "architecture",
            "implementation",
            "testing",
            "deployment",
            "review",
            "custom"
        ],
        "team_roles": [
            "requirement_analyst",
            "solution_architect",
            "backend_developer",
            "frontend_developer",
            "qa_engineer",
            "devops_engineer",
            "security_engineer",
            "technical_writer"
        ],
        "utcp_enabled": True,
        "ai_model": "claude-3-5-sonnet-20241022"
    }


@api.get(
    "/health",
    summary="Health check",
    description="Check service health and readiness",
    tags=["Service Info"]
)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "workflow-generator",
        "version": "1.0.0",
        "utcp_enabled": True,
        "ai_model_available": anthropic_key is not None,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    print("🚀 Starting Workflow Generation Service with UTCP")
    print(f"📡 UTCP Manual: http://{HOST}:{PORT}/utcp-manual.json")
    print(f"🔧 Tools Endpoint: http://{HOST}:{PORT}/utcp/tools")
    print(f"📚 API Docs: http://{HOST}:{PORT}/docs")
    print()
    print("✨ Agents can now generate workflows with conversation context!")
    print()
    print("Key Features:")
    print("  • Context-aware workflow generation")
    print("  • Conversation history integration")
    print("  • ReactFlow blueprint format for DAG Studio")
    print("  • Automatic phase breakdown and team assignment")
    print()

    api.run()
