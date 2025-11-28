#!/usr/bin/env python3
"""
AI DAG Generation API Routes

REST API endpoints for AI-powered DAG generation and approval workflow.
"""

import logging
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

from services.requirement_analyzer import RequirementAnalyzer
from services.ai_dag_generator import AIDAGGenerator
from services.dag_validator import DAGValidator
from services.dag_presenter import DAGPresenter
from services.pending_dag_storage import PendingDAGStorage
from services.dag_catalog import DAGCatalogService
from utils.redis_manager import RedisManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-dag", tags=["AI DAG Generation"])

# Initialize services
requirement_analyzer = RequirementAnalyzer()
ai_dag_generator = AIDAGGenerator()
dag_validator = DAGValidator()
dag_presenter = DAGPresenter()
pending_storage = PendingDAGStorage()
dag_catalog = DAGCatalogService(redis_manager=RedisManager())


# Request/Response Models

class GenerateDAGRequest(BaseModel):
    """Request to generate DAG from requirement"""
    user_id: str = Field(..., description="User ID")
    room_id: str = Field(..., description="Collaboration room ID")
    requirement: str = Field(..., description="Natural language project requirement")
    conversation_context: Optional[List[Dict]] = Field(None, description="Recent conversation messages")


class GenerateDAGResponse(BaseModel):
    """Response with generated DAG pending approval"""
    pending_dag_id: str
    dag: Dict[str, Any]
    metadata: Dict[str, Any]
    reasoning: str
    estimated_timeline: str
    parallel_opportunities: List[str]
    risk_factors: List[str]
    validation_passed: bool
    presentation: Dict[str, Any]


class ApproveDAGRequest(BaseModel):
    """Request to approve pending DAG"""
    pending_dag_id: str = Field(..., description="Pending DAG ID")
    user_id: str = Field(..., description="User ID")


class ApproveDAGResponse(BaseModel):
    """Response after DAG approval"""
    dag_id: str
    workflow_id: Optional[str] = None
    status: str
    message: str


class ModifyDAGRequest(BaseModel):
    """Request to modify pending DAG"""
    pending_dag_id: str = Field(..., description="Pending DAG ID")
    user_id: str = Field(..., description="User ID")
    modified_dag: Dict[str, Any] = Field(..., description="Modified DAG data")


class ModifyDAGResponse(BaseModel):
    """Response after DAG modification"""
    pending_dag_id: str
    validation: Dict[str, Any]
    message: str


class RejectDAGRequest(BaseModel):
    """Request to reject pending DAG"""
    pending_dag_id: str = Field(..., description="Pending DAG ID")
    user_id: str = Field(..., description="User ID")
    reason: Optional[str] = Field(None, description="Rejection reason")


class RejectDAGResponse(BaseModel):
    """Response after DAG rejection"""
    status: str
    message: str


# API Endpoints

@router.post("/generate", response_model=GenerateDAGResponse)
async def generate_dag(request: GenerateDAGRequest):
    """
    Generate a complete DAG workflow from natural language requirement.

    This endpoint:
    1. Analyzes the requirement
    2. Generates a complete DAG using AI
    3. Validates the structure
    4. Stores it as pending approval
    5. Returns formatted presentation

    The agent handles ALL validation - human just approves/rejects.
    """
    try:
        logger.info(f"Generating DAG for user {request.user_id}, room {request.room_id}")

        # Step 1: Analyze requirement
        logger.info("Step 1: Analyzing requirement...")
        analysis = await requirement_analyzer.analyze_requirement(
            request.requirement,
            request.conversation_context
        )

        logger.info(f"Analysis complete: complexity={analysis.complexity}, "
                   f"components={len(analysis.technical_components)}")

        # Step 2: Generate DAG using AI
        logger.info("Step 2: Generating DAG with AI...")
        generated_dag = await ai_dag_generator.generate_dag(
            analysis,
            user_id=request.user_id,
            max_retries=3
        )

        logger.info(f"DAG generated: {generated_dag.dag.name}, "
                   f"phases={len(generated_dag.dag.nodes)}, "
                   f"valid={generated_dag.validation_passed}")

        # Step 3: Store as pending
        logger.info("Step 3: Storing pending DAG...")
        pending_dag_id = await pending_storage.store_pending_dag(
            generated_dag,
            user_id=request.user_id,
            room_id=request.room_id
        )

        logger.info(f"Stored as pending: {pending_dag_id}")

        # Step 4: Format for presentation
        logger.info("Step 4: Formatting presentation...")
        presentation = await dag_presenter.format_dag_for_approval(
            generated_dag,
            pending_dag_id
        )

        logger.info("✅ DAG generation complete")

        # Build response
        return GenerateDAGResponse(
            pending_dag_id=pending_dag_id,
            dag=presentation['dag'],
            metadata=generated_dag.metadata,
            reasoning=generated_dag.reasoning,
            estimated_timeline=generated_dag.estimated_timeline,
            parallel_opportunities=generated_dag.parallel_opportunities,
            risk_factors=generated_dag.risk_factors,
            validation_passed=generated_dag.validation_passed,
            presentation=presentation
        )

    except Exception as e:
        logger.error(f"Error generating DAG: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate DAG: {str(e)}")


@router.post("/approve", response_model=ApproveDAGResponse)
async def approve_dag(request: ApproveDAGRequest):
    """
    Approve a pending DAG and move it to active catalog.

    This endpoint:
    1. Retrieves the pending DAG
    2. Marks it as approved
    3. Stores it in the main DAG catalog
    4. Optionally starts workflow execution
    5. Returns the active DAG ID
    """
    try:
        logger.info(f"Approving DAG {request.pending_dag_id} for user {request.user_id}")

        # Step 1: Get pending DAG
        pending_dag_data = await pending_storage.get_pending_dag(request.pending_dag_id)

        if not pending_dag_data:
            raise HTTPException(status_code=404, detail="Pending DAG not found or expired")

        # Verify user owns this DAG
        if pending_dag_data.get('user_id') != request.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to approve this DAG")

        # Step 2: Mark as approved
        approved_data = await pending_storage.approve_pending_dag(request.pending_dag_id)

        # Step 3: Store in catalog
        from workflow.dag import WorkflowBuilder, TaskType

        # Reconstruct DAG from stored data
        dag_data = approved_data['dag']
        builder = WorkflowBuilder(
            workflow_id=dag_data['dag_id'],
            name=dag_data['name'],
            description=dag_data['description']
        )

        # Add all nodes
        for node_id, node_data in dag_data['nodes'].items():
            task_type_map = {
                'research': TaskType.RESEARCH,
                'planning': TaskType.PLANNING,
                'code': TaskType.CODE,
                'review': TaskType.REVIEW,
                'testing': TaskType.TESTING,
                'deployment': TaskType.DEPLOYMENT
            }

            builder.add_task(
                task_id=node_id,
                name=node_data['name'],
                description=node_data['description'],
                task_type=task_type_map.get(node_data['task_type'], TaskType.CODE),
                depends_on=node_data.get('depends_on', []),
                priority=node_data.get('priority', 5),
                estimated_duration=node_data.get('estimated_duration'),
                agent_persona=node_data.get('agent_persona')
            )

        dag = builder.build()

        # Store in catalog
        dag_id = await dag_catalog.store_dag(
            dag=dag,
            metadata=approved_data['metadata'],
            user_id=request.user_id
        )

        logger.info(f"✅ DAG approved and stored: {dag_id}")

        # TODO: Optionally start workflow execution here
        # workflow_id = await start_workflow_execution(dag_id, request.user_id)

        return ApproveDAGResponse(
            dag_id=dag_id,
            workflow_id=None,  # Will be set when execution starts
            status="approved",
            message=f"DAG '{dag.name}' has been approved and is ready for execution"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving DAG: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to approve DAG: {str(e)}")


@router.post("/modify", response_model=ModifyDAGResponse)
async def modify_dag(request: ModifyDAGRequest):
    """
    Modify a pending DAG and re-validate.

    This endpoint:
    1. Retrieves the pending DAG
    2. Applies user modifications
    3. Re-validates the structure
    4. Updates the pending DAG
    5. Returns validation results
    """
    try:
        logger.info(f"Modifying DAG {request.pending_dag_id} for user {request.user_id}")

        # Step 1: Get pending DAG
        pending_dag_data = await pending_storage.get_pending_dag(request.pending_dag_id)

        if not pending_dag_data:
            raise HTTPException(status_code=404, detail="Pending DAG not found or expired")

        # Verify user owns this DAG
        if pending_dag_data.get('user_id') != request.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this DAG")

        # Step 2: Validate modified DAG
        # Reconstruct DAG for validation
        from workflow.dag import WorkflowBuilder, TaskType

        dag_data = request.modified_dag
        builder = WorkflowBuilder(
            workflow_id=dag_data['dag_id'],
            name=dag_data['name'],
            description=dag_data.get('description', '')
        )

        task_type_map = {
            'research': TaskType.RESEARCH,
            'planning': TaskType.PLANNING,
            'code': TaskType.CODE,
            'review': TaskType.REVIEW,
            'testing': TaskType.TESTING,
            'deployment': TaskType.DEPLOYMENT
        }

        for node_id, node_data in dag_data['nodes'].items():
            builder.add_task(
                task_id=node_id,
                name=node_data['name'],
                description=node_data.get('description', ''),
                task_type=task_type_map.get(node_data['task_type'], TaskType.CODE),
                depends_on=node_data.get('depends_on', []),
                priority=node_data.get('priority', 5)
            )

        dag = builder.build()

        # Validate
        validation_result = dag_validator.validate_dag(dag)

        # Step 3: Update pending DAG
        await pending_storage.update_pending_dag(
            request.pending_dag_id,
            request.modified_dag
        )

        logger.info(f"✅ DAG modified, validation={'passed' if validation_result.is_valid else 'failed'}")

        return ModifyDAGResponse(
            pending_dag_id=request.pending_dag_id,
            validation={
                'is_valid': validation_result.is_valid,
                'errors': validation_result.errors,
                'warnings': validation_result.warnings,
                'suggestions': validation_result.suggestions
            },
            message="DAG has been updated" + (" and is valid" if validation_result.is_valid else " but has validation errors")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error modifying DAG: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to modify DAG: {str(e)}")


@router.post("/reject", response_model=RejectDAGResponse)
async def reject_dag(request: RejectDAGRequest):
    """
    Reject a pending DAG.

    This endpoint:
    1. Retrieves the pending DAG
    2. Marks it as rejected
    3. Stores rejection reason
    4. Cleans up pending storage
    """
    try:
        logger.info(f"Rejecting DAG {request.pending_dag_id} for user {request.user_id}")

        # Step 1: Get pending DAG
        pending_dag_data = await pending_storage.get_pending_dag(request.pending_dag_id)

        if not pending_dag_data:
            raise HTTPException(status_code=404, detail="Pending DAG not found or expired")

        # Verify user owns this DAG
        if pending_dag_data.get('user_id') != request.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to reject this DAG")

        # Step 2: Mark as rejected
        await pending_storage.reject_pending_dag(
            request.pending_dag_id,
            reason=request.reason
        )

        logger.info(f"✅ DAG rejected: {request.pending_dag_id}")

        return RejectDAGResponse(
            status="rejected",
            message=f"DAG has been rejected. Reason: {request.reason or 'Not specified'}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting DAG: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reject DAG: {str(e)}")


@router.get("/pending/{pending_dag_id}")
async def get_pending_dag(pending_dag_id: str, user_id: str):
    """Get details of a pending DAG"""
    try:
        pending_dag_data = await pending_storage.get_pending_dag(pending_dag_id)

        if not pending_dag_data:
            raise HTTPException(status_code=404, detail="Pending DAG not found or expired")

        # Verify user owns this DAG
        if pending_dag_data.get('user_id') != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this DAG")

        return pending_dag_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending DAG: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get pending DAG: {str(e)}")


@router.get("/pending/user/{user_id}")
async def get_user_pending_dags(user_id: str):
    """Get all pending DAGs for a user"""
    try:
        pending_ids = await pending_storage.get_user_pending_dags(user_id)

        # Get details for each
        pending_dags = []
        for pending_id in pending_ids:
            dag_data = await pending_storage.get_pending_dag(pending_id)
            if dag_data:
                pending_dags.append({
                    'pending_id': pending_id,
                    'name': dag_data.get('dag', {}).get('name', 'Unknown'),
                    'status': dag_data.get('status', 'pending'),
                    'created_at': dag_data.get('created_at')
                })

        return {
            'user_id': user_id,
            'pending_dags': pending_dags,
            'count': len(pending_dags)
        }

    except Exception as e:
        logger.error(f"Error getting user pending DAGs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get user pending DAGs: {str(e)}")
