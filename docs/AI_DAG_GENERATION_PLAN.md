# AI-Powered DAG Generation & Execution Plan

## Overview

System where users provide natural language requirements → AI Agent generates complete DAG workflow → Human approves → System executes.

**Key Principle:** Agent is fully responsible for ensuring DAG completeness and validity. Human only provides approval/rejection.

---

## User Journey

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 1. User Provides Requirement                                            │
│    "Build a SaaS app with authentication, billing, and admin dashboard" │
└────────────────┬────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 2. AI Agent Analyzes Requirement                                        │
│    • Extracts functional requirements                                   │
│    • Identifies technical components                                    │
│    • Determines dependencies                                            │
│    • Estimates complexity and duration                                  │
└────────────────┬────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 3. AI Agent Generates DAG Definition                                    │
│    • Creates phases (nodes)                                             │
│    • Defines dependencies (edges)                                       │
│    • Assigns task types and priorities                                  │
│    • Sets agent personas for each phase                                 │
│    • Validates DAG structure (no cycles, all deps exist)                │
└────────────────┬────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 4. AI Agent Presents DAG to User                                        │
│    • Visual DAG diagram in chat                                         │
│    • Phase breakdown with descriptions                                  │
│    • Dependency visualization                                           │
│    • Estimated timeline                                                 │
│    • "Approve" / "Modify" / "Reject" buttons                            │
└────────────────┬────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ 5. Human Approval Decision                                              │
│    • ✅ Approve → Proceed to execution                                  │
│    • ✏️  Modify → Open visual editor for adjustments                    │
│    • ❌ Reject → Agent asks for clarification/changes                   │
└────────────────┬────────────────────────────────────────────────────────┘
                 │
                 ▼ (if approved)
┌─────────────────────────────────────────────────────────────────────────┐
│ 6. System Executes DAG Workflow                                         │
│    • Stores DAG in catalog                                              │
│    • Initializes workflow execution                                     │
│    • Executes phases in topological order                               │
│    • Real-time progress updates to user                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## System Architecture

### Backend Components

#### 1. RequirementAnalyzer (`src/services/requirement_analyzer.py`)

**Responsibility:** Parse natural language requirements into structured data

```python
class RequirementAnalyzer:
    async def analyze_requirement(self, requirement: str, context: List[Dict]) -> RequirementAnalysis

    # Output:
    RequirementAnalysis:
        - functional_requirements: List[str]
        - technical_components: List[str]
        - complexity: str
        - estimated_duration: str
        - key_features: List[str]
        - tech_stack_hints: List[str]
```

#### 2. AIDAGGenerator (`src/services/ai_dag_generator.py`)

**Responsibility:** Generate complete, valid DAG from requirements using Claude AI

```python
class AIDAGGenerator:
    async def generate_dag(
        self,
        requirement_analysis: RequirementAnalysis,
        user_id: str
    ) -> GeneratedDAG

    # Process:
    # 1. Use Claude AI to generate phase breakdown
    # 2. Identify dependencies between phases
    # 3. Assign task types (research, planning, code, review, testing, deployment)
    # 4. Set priorities and agent personas
    # 5. Validate DAG structure (no cycles, all dependencies exist)
    # 6. Return complete DAG definition

    # Output:
    GeneratedDAG:
        - dag: DAG (complete workflow definition)
        - metadata: DAGMetadata
        - reasoning: str (why this structure)
        - estimated_timeline: str
        - risk_factors: List[str]
```

**AI Prompt Structure:**

```
You are a senior software architect. Given these requirements:
{requirement_analysis}

Generate a complete DAG workflow with:
1. Phase breakdown (5-10 phases)
2. Clear dependencies between phases
3. Task types for each phase
4. Estimated duration for each phase
5. Agent personas best suited for each phase

Requirements:
- No circular dependencies
- All dependencies must reference existing phases
- Include testing and deployment phases
- Consider parallel execution opportunities

Output JSON format:
{
  "phases": [
    {
      "id": "phase_1",
      "name": "Requirements Analysis",
      "description": "...",
      "task_type": "research",
      "depends_on": [],
      "priority": 10,
      "estimated_duration": "2 days",
      "agent_persona": "requirements_analyst"
    },
    ...
  ],
  "reasoning": "This structure ensures..."
}
```

#### 3. DAGValidator (`src/services/dag_validator.py`)

**Responsibility:** Ensure generated DAG meets all requirements

```python
class DAGValidator:
    def validate_dag(self, dag: DAG) -> ValidationResult

    # Checks:
    # ✓ No circular dependencies (topological sort succeeds)
    # ✓ All phase dependencies exist
    # ✓ At least one starting phase (no dependencies)
    # ✓ All phases are reachable
    # ✓ Task types are valid
    # ✓ Phase names are unique
    # ✓ Has deployment/testing phases

    ValidationResult:
        - is_valid: bool
        - errors: List[str]
        - warnings: List[str]
        - suggestions: List[str]
```

#### 4. DAGPresenter (`src/services/dag_presenter.py`)

**Responsibility:** Format DAG for user presentation in chat

```python
class DAGPresenter:
    async def format_dag_for_approval(
        self,
        generated_dag: GeneratedDAG
    ) -> str

    # Output: Rich markdown with:
    # - Visual ASCII/Unicode DAG diagram
    # - Phase breakdown table
    # - Dependency tree
    # - Timeline estimate
    # - Action buttons (Approve/Modify/Reject)
```

#### 5. Enhanced Collaboration Service Integration

**File:** `/src/bff/collaboration_service.py`

```python
# New handler for DAG generation requests
async def handle_dag_generation_request(
    room_id: str,
    room: RoomState,
    user_message: str
):
    # 1. Analyze requirement
    analysis = await requirement_analyzer.analyze_requirement(
        user_message,
        room.messages
    )

    # 2. Generate DAG using AI
    generated_dag = await ai_dag_generator.generate_dag(
        analysis,
        user_id=room.user_id
    )

    # 3. Validate DAG
    validation = dag_validator.validate_dag(generated_dag.dag)
    if not validation.is_valid:
        # Agent iterates until valid
        # (retry with validation errors as feedback)
        pass

    # 4. Present to user for approval
    presentation = await dag_presenter.format_dag_for_approval(generated_dag)

    # 5. Store DAG temporarily (pending approval)
    pending_dag_id = await store_pending_dag(generated_dag, room_id)

    # 6. Send to user with approval actions
    await send_dag_approval_message(
        room_id,
        presentation,
        pending_dag_id,
        actions=['approve', 'modify', 'reject']
    )
```

### Frontend Components

#### 1. DAGApprovalCard Component

**File:** `frontend/src/components/DAGApprovalCard.tsx`

```tsx
interface DAGApprovalCardProps {
  dagId: string;
  dagDefinition: DAG;
  metadata: DAGMetadata;
  reasoning: string;
  onApprove: () => void;
  onModify: () => void;
  onReject: () => void;
}

// Features:
// - Visual DAG preview (React Flow mini-view)
// - Phase list with dependencies
// - Timeline estimate
// - Three action buttons
// - Expandable details
```

#### 2. DAGVisualEditor Component

**File:** `frontend/src/components/DAGVisualEditor.tsx`

```tsx
interface DAGVisualEditorProps {
  initialDAG: DAG;
  onSave: (modifiedDAG: DAG) => void;
  onCancel: () => void;
}

// Features:
// - Full React Flow editor
// - Add/remove phases
// - Modify dependencies (drag connections)
// - Edit phase properties (name, description, type)
// - Real-time validation
// - Save/Cancel actions
```

#### 3. Enhanced Collaboration UI

**File:** `frontend/src/components/CollaborationRoom.tsx`

```tsx
// New message type: 'dag_approval'
// Renders DAGApprovalCard in chat
// Handles approval actions via WebSocket

handleDAGApproval = async (dagId: string, action: string) => {
  switch (action) {
    case 'approve':
      await approveDAG(dagId);
      // Backend starts execution
      break;
    case 'modify':
      openDAGEditor(dagId);
      break;
    case 'reject':
      await rejectDAG(dagId, reason);
      break;
  }
}
```

---

## API Endpoints

### New Endpoints

**POST /api/v1/dag/generate**
```json
Request:
{
  "user_id": "user_123",
  "requirement": "Build a SaaS app with...",
  "conversation_context": [...]
}

Response:
{
  "pending_dag_id": "pending_abc123",
  "dag": { ... },
  "metadata": { ... },
  "reasoning": "This workflow structure...",
  "estimated_timeline": "8-12 weeks",
  "validation": {
    "is_valid": true,
    "warnings": []
  }
}
```

**POST /api/v1/dag/approve**
```json
Request:
{
  "pending_dag_id": "pending_abc123",
  "user_id": "user_123"
}

Response:
{
  "dag_id": "dag_abc123",
  "workflow_id": "workflow_xyz789",
  "status": "execution_started",
  "message": "DAG approved and execution started"
}
```

**POST /api/v1/dag/modify**
```json
Request:
{
  "pending_dag_id": "pending_abc123",
  "modified_dag": { ... },
  "user_id": "user_123"
}

Response:
{
  "pending_dag_id": "pending_abc124",
  "validation": {
    "is_valid": true,
    "errors": []
  }
}
```

**POST /api/v1/dag/reject**
```json
Request:
{
  "pending_dag_id": "pending_abc123",
  "user_id": "user_123",
  "reason": "Too complex, need simpler approach"
}

Response:
{
  "status": "rejected",
  "message": "Agent will generate alternative"
}
```

---

## Agent Responsibilities

### The Agent MUST Ensure:

1. **Complete Phase Coverage**
   - Requirements gathering phase
   - Design/architecture phase
   - Implementation phase(s)
   - Testing phase
   - Deployment phase
   - Documentation phase (if needed)

2. **Valid Dependencies**
   - No circular dependencies
   - All dependencies reference existing phases
   - Logical dependency order

3. **Parallel Opportunities**
   - Identify phases that can run in parallel
   - Frontend/backend can be parallel after architecture
   - Multiple microservices can be parallel

4. **Appropriate Task Types**
   - research: Requirements, investigation
   - planning: Architecture, design
   - code: Implementation, development
   - review: Code review, security audit
   - testing: Unit tests, integration tests, E2E
   - deployment: CI/CD, infrastructure

5. **Agent Persona Assignment**
   - Requirements Analyst for requirements phases
   - Solutions Architect for architecture
   - Backend Developer for backend implementation
   - Frontend Developer for frontend work
   - QA Engineer for testing
   - DevOps Engineer for deployment

6. **Realistic Estimates**
   - Phase durations based on complexity
   - Overall timeline calculation
   - Risk factor identification

7. **Self-Validation**
   - Run validation before presenting to user
   - If invalid, regenerate until valid
   - Never present invalid DAG to user

---

## Human Responsibilities

### The Human ONLY:

1. **Reviews the proposed workflow**
   - Looks at phase breakdown
   - Checks if it matches their mental model

2. **Makes approval decision**
   - ✅ Approve: "Yes, this looks good, proceed"
   - ✏️  Modify: "Let me adjust some phases" (visual editor)
   - ❌ Reject: "No, try a different approach"

3. **NO validation burden**
   - Human doesn't check for circular dependencies
   - Human doesn't verify all phases are covered
   - Human doesn't validate technical correctness
   - **Agent handles ALL validation**

---

## Execution Flow After Approval

```python
# When user approves DAG:

async def execute_approved_dag(dag_id: str, user_id: str):
    # 1. Move from pending to active catalog
    dag = await move_pending_to_active(dag_id)

    # 2. Create workflow execution instance
    workflow_id = await create_workflow_execution(
        dag_id=dag_id,
        user_id=user_id,
        execution_mode='phased'  # Default to phased for human oversight
    )

    # 3. Initialize phase tracking
    await initialize_phase_tracking(workflow_id, dag)

    # 4. Start execution (first phase)
    first_phase = dag.get_starting_phases()[0]
    await execute_phase(workflow_id, first_phase.name)

    # 5. Send real-time updates to user
    await send_execution_started_notification(user_id, workflow_id, dag)
```

---

## Implementation Tasks

### Phase 1: Backend AI DAG Generation (Tasks 1-8)

1. ✅ Create `RequirementAnalyzer` class
2. ✅ Create `AIDAGGenerator` with Claude AI integration
3. ✅ Implement DAG generation prompt engineering
4. ✅ Create `DAGValidator` with comprehensive checks
5. ✅ Create `DAGPresenter` for chat formatting
6. ✅ Add pending DAG storage (Redis with TTL)
7. ✅ Integrate with `collaboration_service.py`
8. ✅ Create new API endpoints (generate, approve, modify, reject)

### Phase 2: Frontend Components (Tasks 9-13)

9. ✅ Create `DAGApprovalCard` component
10. ✅ Create `DAGVisualEditor` with React Flow
11. ✅ Add approval action handlers to CollaborationRoom
12. ✅ Create DAG visualization utilities
13. ✅ Add WebSocket message handlers for DAG messages

### Phase 3: Integration & Testing (Tasks 14-16)

14. ✅ Integration testing: Requirement → DAG generation
15. ✅ Testing: DAG approval → Execution flow
16. ✅ E2E testing: Full user journey

---

## Example Scenario

### User Input:
```
"I need to build a real-time chat application with:
- User authentication (email/Google)
- Private and group chats
- File sharing
- Message reactions
- Online status indicators
- Mobile app (iOS/Android)
Deploy on AWS"
```

### Agent Generated DAG:

```
Phase 1: Requirements & Architecture [research]
  ├─ Analyze functional requirements
  ├─ Define system architecture
  └─ Create technical specifications

Phase 2: Database & Backend API [planning, code]
  ├─ Design database schema
  ├─ Set up PostgreSQL + Redis
  ├─ Build REST API with WebSocket support
  └─ Depends on: [Phase 1]

Phase 3: Authentication Service [code]
  ├─ Implement JWT auth
  ├─ Integrate Google OAuth
  └─ Depends on: [Phase 2]

Phase 4: Real-time Chat Backend [code]
  ├─ WebSocket server implementation
  ├─ Message persistence
  ├─ File upload handling
  └─ Depends on: [Phase 2, Phase 3]

Phase 5: Mobile App Development [code] ⟨PARALLEL⟩
  ├─ iOS app (React Native)
  ├─ Android app (React Native)
  ├─ Real-time message sync
  └─ Depends on: [Phase 4]

Phase 6: Web Dashboard [code] ⟨PARALLEL with Phase 5⟩
  ├─ Admin dashboard
  ├─ User management
  └─ Depends on: [Phase 4]

Phase 7: Integration Testing [testing]
  ├─ API integration tests
  ├─ E2E tests
  ├─ Load testing
  └─ Depends on: [Phase 5, Phase 6]

Phase 8: AWS Deployment [deployment]
  ├─ ECS/EKS setup
  ├─ RDS configuration
  ├─ CloudFront CDN
  ├─ CI/CD pipeline
  └─ Depends on: [Phase 7]

Estimated Timeline: 10-14 weeks
Parallel Opportunities: Phase 5 & 6 can run simultaneously
```

### Agent Presentation:

```markdown
🎯 **Generated Workflow: Real-time Chat Application**

I've analyzed your requirements and created an 8-phase workflow:

**Phase Breakdown:**
1. Requirements & Architecture (2 weeks)
2. Database & Backend API (2 weeks)
3. Authentication Service (1 week)
4. Real-time Chat Backend (2 weeks)
5. Mobile App Development (3 weeks) ⟨Can run in parallel with Phase 6⟩
6. Web Dashboard (2 weeks) ⟨Can run in parallel with Phase 5⟩
7. Integration Testing (1 week)
8. AWS Deployment (1 week)

**Timeline:** 10-14 weeks
**Parallel Execution:** Yes (Phases 5 & 6)

**Key Features Covered:**
✓ User authentication (email + Google OAuth)
✓ Real-time messaging (WebSocket)
✓ File sharing
✓ Message reactions
✓ Online status
✓ Mobile apps (iOS/Android)
✓ AWS deployment

**Would you like to proceed with this workflow?**

[✅ Approve & Start] [✏️ Modify in Editor] [❌ Reject & Revise]
```

---

## Success Criteria

✅ User provides requirement in natural language
✅ Agent generates complete, valid DAG automatically
✅ Agent validates DAG before presenting
✅ User sees visual DAG representation
✅ User can approve with one click
✅ System executes approved DAG
✅ Real-time progress updates
✅ Agent handles ALL validation (human just approves)

---

**Document Version:** 1.0
**Date:** October 16, 2025
**Status:** Ready for Implementation
