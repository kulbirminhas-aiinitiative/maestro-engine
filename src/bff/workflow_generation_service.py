#!/usr/bin/env python3
"""
Simple Workflow Generation Service
FastAPI service for generating DAG workflows with conversation context.

Agents can call this service directly via HTTP to generate workflows.
"""

import asyncio
import json
import logging
import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Claude Agent SDK for AI-powered workflow generation
from claude_agent_sdk import ClaudeAgentOptions, query

# Import intelligent workflow modules
try:
    from api_integrator import WorkflowAPIIntegrator, AIAgent, PhaseType
    from confidence_scorer import ConfidenceScorer, rank_agents_by_confidence
    INTELLIGENT_MODE_AVAILABLE = True
    logger_init = logging.getLogger("workflow_generator")
    logger_init.info("✓ Intelligent workflow modules loaded")
except ImportError as e:
    INTELLIGENT_MODE_AVAILABLE = False
    logger_init = logging.getLogger("workflow_generator")
    logger_init.warning(f"⚠ Intelligent workflow modules not available: {e}")
    logger_init.warning("  Workflow generation will use basic mode without recommendations")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("workflow_generator")

# Create FastAPI app
app = FastAPI(
    title="Workflow Generation Service",
    description="AI-powered workflow blueprint generation from requirements and conversation context",
    version="1.0.0"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class WorkflowGenerationRequest(BaseModel):
    """Request to generate workflow blueprint"""
    requirement: str = Field(
        ...,
        description="Project requirement or description"
    )
    conversation_context: List[str] = Field(
        default=[],
        description="Conversation history for context-aware generation"
    )
    user_id: str = Field(default="maestro-user")
    room_id: Optional[str] = Field(default=None)


class WorkflowGenerationResponse(BaseModel):
    """Response from workflow generation"""
    success: bool
    workflow: Optional[Dict[str, Any]] = None
    workflow_name: str = ""
    phases_count: int = 0
    generated_by: str = "workflow-generator"
    timestamp: str = ""
    error_message: Optional[str] = None


# Load ideal workflow blueprint template
BLUEPRINT_TEMPLATE_PATH = "/home/ec2-user/projects/maestro-engine-new/workflow/IDEAL_DAG_WORKFLOW_BLUEPRINT.json"

# Backend API URL for fetching organizational data
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:3100")

def load_blueprint_template() -> Dict[str, Any]:
    """Load the ideal workflow blueprint template."""
    try:
        with open(BLUEPRINT_TEMPLATE_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load blueprint template: {e}")
        # Return minimal fallback structure
        return {"nodes": [], "edges": []}


async def fetch_organizational_data(requirement: str) -> Dict[str, Any]:
    """
    Fetch organizational data from backend APIs for intelligent workflow generation.

    This includes:
    - Available AI agents with skills and performance metrics
    - Phase type catalog
    - Learning patterns from successful workflows

    Args:
        requirement: Project requirement string

    Returns:
        Dictionary containing organizational data, or empty dict if not available
    """
    if not INTELLIGENT_MODE_AVAILABLE:
        logger.debug("Intelligent mode not available, skipping organizational data fetch")
        return {}

    try:
        logger.info("📊 Fetching organizational data from backend APIs...")

        # Initialize API integrator
        api = WorkflowAPIIntegrator(base_url=BACKEND_API_URL)

        # Check if backend is available
        is_healthy = await api.check_health()
        if not is_healthy:
            logger.warning("⚠ Backend API not available, using basic mode")
            return {}

        # Fetch data in parallel
        agents_task = api.fetch_available_agents()
        phase_types_task = api.fetch_phase_types()

        # Wait for both
        agents, phase_types = await asyncio.gather(agents_task, phase_types_task)

        logger.info(f"✓ Fetched {len(agents)} agents and {len(phase_types)} phase types")

        return {
            "agents": agents,
            "phase_types": phase_types,
            "api_available": True
        }

    except Exception as e:
        logger.warning(f"⚠ Failed to fetch organizational data: {e}")
        logger.warning("  Continuing with basic workflow generation")
        return {"api_available": False}


async def generate_team_recommendations(
    nodes: List[Dict],
    org_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate team recommendations with confidence scores for each phase.

    Args:
        nodes: List of workflow nodes (phases)
        org_data: Organizational data from backend APIs

    Returns:
        Dictionary mapping node IDs to recommendations
    """
    if not org_data.get("api_available") or not INTELLIGENT_MODE_AVAILABLE:
        return {}

    try:
        logger.info("🎯 Generating team recommendations with confidence scores...")

        agents = org_data.get("agents", [])
        phase_types = org_data.get("phase_types", [])

        if not agents or not phase_types:
            logger.warning("No agents or phase types available for recommendations")
            return {}

        # Create phase type lookup
        phase_type_map = {pt.type_key: pt for pt in phase_types}

        scorer = ConfidenceScorer()
        recommendations = {}

        for node in nodes:
            node_data = node.get("data", {})
            phase_type_key = node_data.get("phaseType", "")
            node_id = node.get("id", "")

            # Find matching phase type
            phase_type = phase_type_map.get(phase_type_key)
            if not phase_type:
                logger.debug(f"No phase type found for {phase_type_key}, skipping")
                continue

            # Rank agents by confidence for this phase
            ranked = rank_agents_by_confidence(agents, phase_type, expertise_map=None)

            if not ranked:
                continue

            # Get top 3 recommendations
            top_recommendations = []
            for agent, confidence in ranked[:3]:
                top_recommendations.append({
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "confidence_score": confidence.overall_score,
                    "confidence_level": confidence.confidence_level.value,
                    "reasoning": confidence.reasoning,
                    "strengths": confidence.strengths,
                    "concerns": confidence.concerns,
                    "breakdown": confidence.breakdown
                })

            recommendations[node_id] = {
                "primary_recommendation": top_recommendations[0] if top_recommendations else None,
                "alternatives": top_recommendations[1:] if len(top_recommendations) > 1 else [],
                "all_scored": len(ranked)
            }

        logger.info(f"✓ Generated recommendations for {len(recommendations)} phases")
        return recommendations

    except Exception as e:
        logger.error(f"Failed to generate team recommendations: {e}")
        return {}


async def generate_ai_workflow(requirement: str, conversation_context: List[str]) -> Dict[str, Any]:
    """
    Generate workflow using AI with template as reference.
    AI analyzes requirement and decides:
    - Number of phases (3-10 based on complexity)
    - Serial vs parallel execution
    - Phase types (appropriate for project type)
    - Team assignments

    Uses IDEAL_DAG_WORKFLOW_BLUEPRINT.json as quality reference.
    Enhanced with intelligent team recommendations when backend APIs are available.
    """
    workflow_id = f"workflow-{int(time.time() * 1000)}"

    # Fetch organizational data from backend (if available)
    org_data = await fetch_organizational_data(requirement)

    # Load ideal blueprint as REFERENCE (not hardcoded template)
    logger.info("📋 Loading ideal workflow blueprint as reference for AI...")
    blueprint_reference = load_blueprint_template()

    # Build conversation context summary
    context_summary = "\n".join([f"- {ctx}" for ctx in conversation_context[-5:]]) if conversation_context else "No prior context"

    # Create AI prompt with template as reference
    prompt = f"""You are an expert software architect and workflow designer. Generate a complete, executable workflow DAG (Directed Acyclic Graph) for the following project.

**PROJECT REQUIREMENT:**
{requirement}

**CONVERSATION CONTEXT:**
{context_summary}

**YOUR TASK:**
Analyze the requirement and create an optimal workflow with:

1. **Appropriate Number of Phases** (3-10 based on complexity)
   - Simple API project: 3-4 phases
   - Standard web app: 5-6 phases
   - Complex enterprise system: 7-10 phases

2. **Optimal Execution Strategy**
   - Serial: When phases depend on each other
   - Parallel: When phases can run simultaneously (e.g., frontend + backend)
   - Set "allowParallelExecution": true/false in settings

3. **Correct Phase Types** for the project (MUST use these exact values):
   - requirements, architecture, implementation, testing, deployment
   - review, custom (monitoring/planning should use 'custom')

4. **Realistic Team Assignments** from:
   - ai-product-manager, ai-architect, ai-tech-lead
   - ai-senior-developer, ai-developer-001, ai-developer-002
   - ai-qa-engineer, ai-test-automation
   - ai-devops-engineer, ai-sre
   - human-stakeholder-001, human-engineer-001, human-qa-001

**REFERENCE EXAMPLE** (Use this structure but adapt to requirement):
```json
{json.dumps(blueprint_reference, indent=2)[:3000]}...
```

**CRITICAL REQUIREMENTS:**
1. Every node MUST have all these fields:
   - id, type: "phase" (NOT "phaseNode"), position: {{x, y}}
   - data.label, data.phaseType, data.description
   - data.status: "pending" (one of: pending, running, completed, failed)
   - data.phase: same as phaseType
   - data.timeout: number in seconds (e.g., 604800 = 1 week)
   - data.assignedTeam (array), data.assignedExecutorAI (string)
   - data.chat: {{messages: [], notes: []}}
   - data.attributes (object) containing:
     - requirements (array of strings)
     - acceptanceCriteria (array of strings)
     - checkpoints (array with id, name, description, required)
     - qualityGates (array with id, name, description, threshold, weight)

2. Position nodes properly:
   - Start at x=100, y=100
   - Space vertically by 200px if serial
   - Space horizontally if parallel (x=100, x=400, x=700)

3. Create edges for dependencies:
   - {{id, source, target, type: "smoothstep", animated: false, label}}

4. NO circular dependencies

**OUTPUT FORMAT:**
Return ONLY valid JSON in this exact structure:
{{
  "nodes": [...],
  "edges": [...],
  "teamChat": {{"messages": [], "participants": []}},
  "workflowConfig": {{
    "allowParallelExecution": true/false,
    "autoAdvanceOnGatePass": false,
    "requireAllCheckpoints": true,
    "minimumQualityScore": 80
  }}
}}

Generate the workflow now. Output ONLY the JSON, no markdown, no explanations."""

    try:
        # Call Claude Code API
        logger.info("🤖 Calling Claude Code API for AI-powered workflow generation...")

        # Collect response parts from streaming API
        response_parts = []
        async for message in query(prompt=prompt, options=ClaudeAgentOptions(model="claude-sonnet-4-5-20250929")):
            if hasattr(message, "text") and message.text:
                response_parts.append(message.text)
            elif hasattr(message, "content"):
                content = message.content
                if isinstance(content, str):
                    response_parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if hasattr(block, "text"):
                            response_parts.append(block.text)

        # Extract JSON from response
        response_text = "".join(response_parts)

        # Try to parse JSON (handle potential markdown code blocks)
        json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find JSON object directly
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            json_str = json_match.group(0) if json_match else response_text

        # Parse the AI-generated workflow
        ai_generated = json.loads(json_str)

        # Generate descriptive name from requirement
        workflow_name = requirement[:80] if len(requirement) <= 80 else requirement[:77] + "..."

        # Generate team recommendations with confidence scores
        nodes = ai_generated.get("nodes", [])
        recommendations = await generate_team_recommendations(nodes, org_data)

        # Wrap in ReactFlow format
        workflow = {
            "version": "1.0",
            "workflow": {
                "id": workflow_id,
                "name": workflow_name,
                "description": f"AI-generated workflow for: {requirement}",
                "version": "1.0.0",
                "nodes": nodes,
                "edges": ai_generated.get("edges", []),
                "created": datetime.now().isoformat(),
                "createdBy": "maestro-ai",
                "settings": ai_generated.get("workflowConfig", {
                    "allowParallelExecution": False,
                    "autoAdvanceOnGatePass": False,
                    "requireAllCheckpoints": True,
                    "minimumQualityScore": 80
                }),
                "teamChat": ai_generated.get("teamChat", {"messages": [], "participants": []}),
                "validation": {"valid": True, "errors": [], "warnings": []}
            },
            "metadata": {
                "exportedAt": datetime.now().isoformat(),
                "exportedBy": "maestro-ai",
                "application": "maestro-dag-studio",
                "conversationContextUsed": len(conversation_context) > 0,
                "generatedFromTemplate": BLUEPRINT_TEMPLATE_PATH,
                "aiGenerated": True,
                "generationMethod": "claude-code-api-with-template-reference" if not org_data.get("api_available") else "claude-code-api-with-intelligent-recommendations",
                "intelligentMode": org_data.get("api_available", False),
                "recommendationsGenerated": len(recommendations) > 0
            },
            "recommendations": recommendations if recommendations else None
        }

        node_count = len(workflow["workflow"]["nodes"])
        parallel_execution = workflow["workflow"]["settings"].get("allowParallelExecution", False)

        logger.info(f"✅ AI-generated workflow with {node_count} phases")
        logger.info(f"   Execution: {'Parallel' if parallel_execution else 'Serial'}")
        logger.info(f"   Template used as reference: {BLUEPRINT_TEMPLATE_PATH}")

        if recommendations:
            logger.info(f"   🎯 Team recommendations: {len(recommendations)} phases")
            high_conf_count = sum(1 for r in recommendations.values()
                                 if r.get("primary_recommendation", {}).get("confidence_level") == "high")
            logger.info(f"      High confidence: {high_conf_count}/{len(recommendations)}")

        return workflow

    except Exception as e:
        logger.error(f"❌ AI workflow generation failed: {e}")
        logger.warning("⚠️  Falling back to template-based workflow")

        # Fallback: Use template as-is with customization
        return generate_fallback_workflow(requirement, conversation_context, blueprint_reference, workflow_id)


def generate_fallback_workflow(requirement: str, conversation_context: List[str], blueprint: Dict, workflow_id: str) -> Dict[str, Any]:
    """Fallback to template-based workflow if AI generation fails"""

    if not blueprint.get("nodes"):
        blueprint = {
            "nodes": [{
                "id": "req-001",
                "type": "phase",
                "position": {"x": 100, "y": 100},
                "data": {
                    "label": "Requirements",
                    "phaseType": "requirements",
                    "phase": "requirements",
                    "status": "pending",
                    "timeout": 604800,
                    "description": requirement,
                    "assignedTeam": ["ai-product-manager"],
                    "assignedExecutorAI": "ai-product-manager",
                    "attributes": {
                        "requirements": [requirement],
                        "acceptanceCriteria": ["Requirements documented"],
                        "checkpoints": [],
                        "qualityGates": []
                    },
                    "chat": {"messages": [], "notes": []}
                }
            }],
            "edges": []
        }

    workflow_name = requirement[:80] if len(requirement) <= 80 else requirement[:77] + "..."

    # Customize first node
    if blueprint.get("nodes") and len(blueprint["nodes"]) > 0:
        first_node = blueprint["nodes"][0]
        if "data" in first_node:
            first_node["data"]["description"] = f"Gather requirements for: {requirement}"
            first_node["data"]["requirementText"] = f"# Project Requirements\n\n{requirement}\n\n## Context\n\n" + \
                "\n".join([f"- {ctx}" for ctx in conversation_context[-5:]]) if conversation_context else ""

    return {
        "version": "1.0",
        "workflow": {
            "id": workflow_id,
            "name": workflow_name,
            "description": f"Generated workflow for: {requirement}",
            "version": "1.0.0",
            "nodes": blueprint.get("nodes", []),
            "edges": blueprint.get("edges", []),
            "created": datetime.now().isoformat(),
            "createdBy": "maestro-ai",
            "settings": blueprint.get("workflowConfig", {
                "allowParallelExecution": False,
                "autoAdvanceOnGatePass": False,
                "requireAllCheckpoints": True,
                "minimumQualityScore": 80
            }),
            "teamChat": blueprint.get("teamChat", {"messages": [], "participants": []}),
            "validation": {"valid": True, "errors": [], "warnings": []}
        },
        "metadata": {
            "exportedAt": datetime.now().isoformat(),
            "exportedBy": "maestro-ai",
            "application": "maestro-dag-studio",
            "conversationContextUsed": len(conversation_context) > 0,
            "generatedFromTemplate": BLUEPRINT_TEMPLATE_PATH,
            "fallbackMode": True
        }
    }


@app.post("/generate-workflow", response_model=WorkflowGenerationResponse)
async def generate_workflow(request: WorkflowGenerationRequest) -> WorkflowGenerationResponse:
    """
    Generate workflow blueprint from requirements with conversation context.

    This endpoint can be called by agents to create workflows.
    Uses AI to analyze requirement and decide optimal workflow structure.
    """
    logger.info(f"🏗️  Generating AI-powered workflow for: {request.requirement[:50]}...")
    logger.info(f"   Context messages: {len(request.conversation_context)}")

    try:
        # Generate workflow using AI with template as reference
        workflow_data = await generate_ai_workflow(
            requirement=request.requirement,
            conversation_context=request.conversation_context
        )

        workflow_info = workflow_data.get("workflow", {})

        logger.info(f"✅ Workflow generated: {workflow_info.get('name')}")
        logger.info(f"   Phases: {len(workflow_info.get('nodes', []))}")

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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "workflow-generator",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/capabilities")
async def get_capabilities():
    """Get service capabilities."""
    capabilities = [
        "Context-aware workflow generation",
        "Conversation history integration",
        "ReactFlow blueprint format output",
        "Automatic phase breakdown",
        "Team member assignment"
    ]

    # Add intelligent features if available
    if INTELLIGENT_MODE_AVAILABLE:
        capabilities.extend([
            "Intelligent team recommendations with confidence scores",
            "AI-powered agent selection based on skills and performance",
            "Learning from successful workflows",
            "Alternative team suggestions"
        ])

    return {
        "service": "workflow-generator",
        "version": "2.0.0",
        "capabilities": capabilities,
        "intelligent_mode": INTELLIGENT_MODE_AVAILABLE,
        "backend_api_url": BACKEND_API_URL if INTELLIGENT_MODE_AVAILABLE else None,
        "endpoint": "/generate-workflow",
        "method": "POST"
    }


if __name__ == "__main__":
    print("🚀 Starting Workflow Generation Service v2.0")
    print(f"📡 API Docs: http://0.0.0.0:8101/docs")
    print(f"🔧 Endpoint: POST http://0.0.0.0:8101/generate-workflow")
    print()

    if INTELLIGENT_MODE_AVAILABLE:
        print("✨ Intelligent Mode: ENABLED")
        print("   • AI-powered team recommendations with confidence scores")
        print("   • Agent selection based on skills and performance")
        print("   • Alternative suggestions provided")
        print(f"   • Backend API: {BACKEND_API_URL}")
    else:
        print("⚙️  Basic Mode: No intelligent recommendations")
        print("   • Standard workflow generation available")
        print("   • Enable intelligent mode by ensuring api_integrator.py is available")

    print()
    print("📞 Agents can call this service to generate workflows!")
    print()

    uvicorn.run(app, host="0.0.0.0", port=8101, log_level="info")
