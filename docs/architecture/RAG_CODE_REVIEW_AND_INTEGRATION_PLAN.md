# RAG Code Review & Integration Plan

**Date**: 2025-10-03
**Status**: Analysis Complete
**Priority**: High (Foundation for Persona-Level RAG)

---

## Executive Summary

**Existing RAG Code**: 920 lines of well-structured RAG tools exist in `src/rag/`, but they are **NOT integrated** with the workflow engine and are **missing critical backend dependencies**.

**Key Findings**:
- ✅ **8 RAG tools** defined as Claude SDK @tool decorators (ready to use)
- ✅ **HotClaudeRAGSession** wrapper for RAG-aware Claude execution
- ✅ **First-Strike parallel query** architecture (fast MVP approach)
- ❌ **RAG backend missing** - `rag_system/` modules don't exist (import errors)
- ❌ **Execution-level design** - Current RAG is workflow-level, not persona-level
- ❌ **No integration** - `autonomous_sdlc_engine_v3_resumable.py` doesn't use RAG
- ✅ **Shared workflow confirmed** - Uses `personas.MaestroPersonasCompat` from shared SDK

**Bottom Line**: Existing RAG code provides an **excellent foundation** but needs:
1. Backend implementation (vector DB, pattern recommender)
2. Architecture shift from execution-level to persona-level
3. Split into Reader/Writer services
4. Integration with workflow engine

---

## Part 1: Existing RAG Code Analysis

### File 1: `src/rag/claude_rag_session.py` (448 lines)

**Purpose**: Hot (persistent) Claude session with RAG query capabilities

**Key Classes**:

```python
class HotClaudeRAGSession:
    """
    Hot (persistent) Claude instance with RAG awareness
    - Maintains conversation history
    - Has access to RAG query tools
    - Can generate files
    - Learns from past executions
    """
```

**What It Does**:
1. Wraps `claude_code_sdk.query()` with RAG-aware system prompts
2. Provides RAG tools to Claude during execution
3. Maintains conversation history for multi-turn interactions
4. Emphasizes "First-Strike" approach - query everything in parallel first

**System Prompt Strategy**:
```python
system_prompt = f"""
You are a Hot Claude RAG Session - a persistent AI assistant with access to historical project data.

YOUR CAPABILITIES:
1. **RAG Query Tools** - Query historical project data
2. **Assumption Logging Tool** - Track execution decisions
3. **File Generation Tools** - Create deliverables
4. **Conversation Memory** - Maintain context across interactions

SWIFT MVP WORKFLOW (PRIORITY):
1. **⚡ FIRST-STRIKE Query** - IMMEDIATELY call get_swift_mvp_plan(requirement)
   - This gives you complete context in ONE parallel query
2. **📋 Review Synthesized Plan**
3. **🔍 Log Key Assumptions** (REQUIRED for HIGH/CRITICAL impact)
4. **🚀 Execute Immediately**
5. **📊 (Optional) Deep-Dive** - Only if needed
"""
```

**Integration Points**:
- Line 20: `from rag_tools import RAG_TOOLS, get_rag_tools_description`
- Line 69: `self.all_tools = RAG_TOOLS + assumption_tools + [create_code_file, ...]`
- Line 189: Uses `generate_with_unified_tools()` for execution

**Status**: ✅ Well-designed but **not used** by workflow engine

---

### File 2: `src/rag/rag_tools.py` (472 lines)

**Purpose**: RAG tools as Claude SDK @tool decorators

**8 RAG Tools Defined**:

#### 1. `get_swift_mvp_plan` (First-Strike Tool)
```python
@tool(name="get_swift_mvp_plan", description="...")
def get_swift_mvp_plan(requirement: str) -> str:
    """First-Strike unified RAG query - Returns opinionated MVP plan immediately"""

    # Parallel execution of all critical queries
    with ThreadPoolExecutor(max_workers=4) as executor:
        similar_future = executor.submit(rag_manager.search_similar_executions, requirement, 3)
        team_future = executor.submit(recommender.recommend_team_composition, requirement)
        deliverables_future = executor.submit(recommender.recommend_deliverables_template, requirement)
        estimate_future = executor.submit(recommender.get_execution_estimate, requirement)

    # Returns synthesized MVP plan
    return json.dumps(mvp_plan, indent=2)
```

**Key Innovation**: Orchestrates 4 RAG queries in parallel, returns synthesized plan in 2-3 seconds.

#### 2. `query_similar_projects`
```python
@tool(name="query_similar_projects", description="...")
def query_similar_projects(requirement: str, top_k: int = 3) -> str:
    """Claude tool: Query RAG for similar historical projects"""
    rag_manager = get_rag_manager()
    similar_executions = rag_manager.search_similar_executions(requirement, top_k)
    # Returns: projects with similarity scores, teams used, success status
```

#### 3. `get_recommended_team`
```python
@tool(name="get_recommended_team", description="...")
def get_recommended_team(requirement: str) -> str:
    """Claude tool: Get RAG-based team recommendation"""
    recommender = PatternRecommender()
    recommendation = recommender.recommend_team_composition(requirement)
    # Returns: team members with confidence scores and evidence
```

#### 4. `get_deliverables_template`
```python
@tool(name="get_deliverables_template", description="...")
def get_deliverables_template(requirement: str) -> str:
    """Claude tool: Get recommended deliverables.json template from RAG"""
    recommender = PatternRecommender()
    template = recommender.recommend_deliverables_template(requirement)
    # Returns: reusable template with task distribution
```

#### 5-8. Additional Tools
- `analyze_historical_failures` - Find past failures to avoid mistakes
- `get_execution_estimate` - Estimate time and file count
- `get_requirement_insights` - Analyze requirement type and patterns
- `get_rag_stats` - RAG knowledge base statistics

**Tool Export**:
```python
RAG_TOOLS = [
    get_swift_mvp_plan,
    query_similar_projects,
    get_recommended_team,
    get_deliverables_template,
    analyze_historical_failures,
    get_execution_estimate,
    get_requirement_insights,
    get_rag_stats
]
```

**Critical Dependencies** (MISSING):
```python
from rag_system.vector_rag_manager import get_rag_manager
from rag_system.pattern_recommender import PatternRecommender
from rag_system.collateral_extractor import CollateralExtractor
```

**Status**: ✅ Tools are well-designed but ❌ **Backend modules missing**

---

### File 3: `autonomous_sdlc_engine_v3_resumable.py` (520 lines)

**Purpose**: Resumable SDLC workflow engine with session management

**Key Architecture**:
```python
# Line 51 - Confirms shared workflow usage
from personas import MaestroPersonasCompat as SDLCPersonas

class AutonomousSDLCEngineV3Resumable:
    """Resumable SDLC Engine with Session Management"""

    def __init__(self, selected_personas, output_dir, session_manager):
        # Load persona configurations
        self.all_personas = SDLCPersonas.get_all_personas()
        self.persona_configs = {
            pid: self.all_personas[pid]
            for pid in selected_personas
        }

    async def _execute_persona(self, persona_id, requirement, session):
        """Execute a single persona with session context"""

        # Build prompt with session context
        prompt = self._build_persona_prompt(
            persona_config,
            requirement,
            expected_deliverables,
            session_context
        )

        # Execute with Claude Code SDK (NO RAG integration)
        async for message in query(prompt=prompt, options=options):
            # Process messages...
```

**RAG Integration Status**: ❌ **NONE**
- No imports of RAG tools
- No HotClaudeRAGSession usage
- No RAG query calls
- Uses `claude_code_sdk.query()` directly without RAG wrapper

**Confirmation: Shared Workflow**: ✅ **YES**
- Line 51: `from personas import MaestroPersonasCompat as SDLCPersonas`
- Uses persona configs from shared system
- No custom orchestration - pure persona execution

---

## Part 2: Missing Backend Components

### Required Modules (NOT FOUND in codebase)

#### 1. `rag_system/vector_rag_manager.py`
**Expected Functionality**:
```python
class VectorRAGManager:
    """Vector database manager for RAG queries"""

    def __init__(self, chroma_client):
        self.chroma_client = chroma_client
        self.collections = {
            "executions": None,
            "collaterals": None,
            "patterns": None
        }

    def search_similar_executions(self, requirement: str, top_k: int = 3):
        """Search for similar historical project executions"""
        # Query ChromaDB for similar requirements
        # Return ranked results with metadata

    def get_collection_stats(self):
        """Get statistics about indexed data"""
```

**Status**: ❌ Missing - needs implementation

#### 2. `rag_system/pattern_recommender.py`
**Expected Functionality**:
```python
class PatternRecommender:
    """Recommender for teams, templates, and patterns"""

    def recommend_team_composition(self, requirement: str):
        """Recommend team based on similar successful projects"""
        # Query RAG for similar projects
        # Analyze successful team patterns
        # Return team with confidence scores

    def recommend_deliverables_template(self, requirement: str):
        """Get deliverables template from similar projects"""
        # Query RAG for similar deliverables
        # Merge and synthesize templates
        # Return reusable structure

    def get_execution_estimate(self, requirement: str):
        """Estimate time and file count"""
        # Query RAG for similar executions
        # Calculate averages
        # Return estimate with confidence
```

**Status**: ❌ Missing - needs implementation

#### 3. `rag_system/collateral_extractor.py`
**Expected Functionality**:
```python
class CollateralExtractor:
    """Extract and classify project collaterals for indexing"""

    def _classify_requirement(self, requirement: str):
        """Classify requirement type"""
        # NLP classification
        # Return: web_app, api, mobile_app, etc.
```

**Status**: ❌ Missing - needs implementation

#### 4. ChromaDB Integration
**Expected Structure**:
```python
import chromadb
from chromadb.config import Settings

chroma_client = chromadb.Client(Settings(
    persist_directory=settings.chroma_persist_dir,
    anonymized_telemetry=False
))

# Collections:
# - executions: Historical workflow executions
# - collaterals: Code files, docs, configs
# - patterns: Successful patterns and templates
```

**Status**: ❌ Missing - needs setup

---

## Part 3: Architecture Analysis

### Current RAG Design: Execution-Level

```
User Requirement
     ↓
HotClaudeRAGSession created
     ↓
First-Strike RAG Query (get_swift_mvp_plan)
     ├─ Query similar projects
     ├─ Get recommended team
     ├─ Get deliverables template
     └─ Get execution estimate
     ↓
Claude executes WITH RAG context
     ↓
Files generated
```

**Characteristics**:
- ✅ One RAG session per workflow execution
- ✅ First-Strike parallel query approach
- ✅ RAG tools available to Claude during execution
- ❌ Not integrated with persona system
- ❌ All personas share same RAG context (not domain-specific)

### User's Desired Design: Persona-Level

```
User Requirement
     ↓
Workflow Engine (autonomous_sdlc_engine_v3_resumable.py)
     ↓
For each persona:
     ├─ Persona: Frontend Developer
     │    ├─ Query RAG Reader for React templates
     │    ├─ Query RAG Reader for component patterns
     │    └─ Execute with domain-specific context
     │
     ├─ Persona: DevOps Engineer
     │    ├─ Query RAG Reader for K8s templates
     │    ├─ Query RAG Reader for CI/CD patterns
     │    └─ Execute with domain-specific context
     │
     └─ After workflow completes:
          └─ RAG Writer indexes outputs to maestro-templates
```

**Characteristics**:
- ✅ Each persona queries domain-specific templates
- ✅ RAG queries scoped to persona expertise
- ✅ Separate Reader (query) and Writer (indexing) services
- ✅ Templates stored in maestro-templates repository
- ❌ Current RAG code doesn't support this architecture

---

## Part 4: Integration Plan

### Phase 1: Backend Implementation (Foundation)

**Goal**: Implement missing RAG backend components

**Tasks**:
1. **Create `src/rag_system/` module structure**
   ```
   src/rag_system/
   ├── __init__.py
   ├── vector_rag_manager.py
   ├── pattern_recommender.py
   ├── collateral_extractor.py
   └── chroma_client.py
   ```

2. **Implement `vector_rag_manager.py`**
   - ChromaDB client initialization
   - Collection management (executions, collaterals, patterns)
   - Search similar executions with embedding similarity
   - Collection statistics

3. **Implement `pattern_recommender.py`**
   - Team composition recommendations
   - Deliverables template generation
   - Execution time/file estimates
   - Pattern analysis from historical data

4. **Implement `collateral_extractor.py`**
   - Requirement classification
   - File type detection
   - Metadata extraction

5. **Set up ChromaDB**
   - Install dependency: `pip install chromadb`
   - Configure persistent directory
   - Create collections
   - Initial indexing of sample data

**Deliverables**:
- Working RAG backend (4 modules)
- ChromaDB setup and collections
- Unit tests for each module

**Estimated Effort**: 1-2 days

---

### Phase 2: Persona-Level RAG Tools

**Goal**: Adapt existing RAG tools for persona-level architecture

**Tasks**:
1. **Create persona-scoped RAG tools** in `src/rag/persona_rag_tools.py`
   ```python
   @tool(name="query_persona_templates")
   def query_persona_templates(persona_id: str, requirement: str) -> str:
       """Query templates specific to persona domain"""

       # Get persona domain
       domain = PERSONA_DOMAINS[persona_id]
       # e.g., "frontend_developer" → "react", "vue", "tailwind"

       # Query RAG filtered by domain tags
       templates = rag_manager.search_templates(
           requirement=requirement,
           domain_tags=domain.tags,
           template_type=domain.template_types
       )

       return json.dumps(templates)

   @tool(name="query_persona_patterns")
   def query_persona_patterns(persona_id: str, task: str) -> str:
       """Query proven patterns for persona's task"""

       # Get persona patterns
       patterns = rag_manager.search_patterns(
           persona_id=persona_id,
           task=task,
           success_only=True
       )

       return json.dumps(patterns)
   ```

2. **Define persona domain mappings** in `src/rag/persona_domains.py`
   ```python
   PERSONA_DOMAINS = {
       "frontend_developer": {
           "tags": ["react", "vue", "tailwind", "typescript"],
           "template_types": ["component", "page", "hook", "utility"],
           "file_extensions": [".tsx", ".jsx", ".css", ".html"]
       },
       "backend_developer": {
           "tags": ["fastapi", "flask", "django", "express"],
           "template_types": ["api", "model", "service", "middleware"],
           "file_extensions": [".py", ".js", ".ts"]
       },
       "devops_engineer": {
           "tags": ["kubernetes", "docker", "terraform", "github-actions"],
           "template_types": ["k8s-manifest", "dockerfile", "pipeline", "iac"],
           "file_extensions": [".yaml", ".yml", ".tf", ".sh"]
       },
       # ... 8 more personas
   }
   ```

3. **Modify existing RAG tools** to accept persona_id parameter
   - Add persona filtering to all query functions
   - Scope results to persona domain
   - Maintain backward compatibility

**Deliverables**:
- Persona-scoped RAG tools
- Domain mapping configuration
- Updated RAG tools with persona awareness

**Estimated Effort**: 1 day

---

### Phase 3: RAG Reader Service

**Goal**: Create FastAPI service for fast template queries

**Tasks**:
1. **Create `src/services/rag_reader_service.py`**
   ```python
   from fastapi import FastAPI, HTTPException
   from pydantic import BaseModel

   app = FastAPI(title="RAG Reader Service", version="1.0.0")

   class TemplateQueryRequest(BaseModel):
       persona_id: str
       requirement: str
       top_k: int = 5

   class TemplateQueryResponse(BaseModel):
       templates: List[Dict[str, Any]]
       similarity_scores: List[float]
       cache_hit: bool

   @app.post("/query/templates")
   async def query_templates(request: TemplateQueryRequest) -> TemplateQueryResponse:
       """Query templates for persona"""

       # Check cache first (Redis)
       cache_key = f"rag:templates:{request.persona_id}:{hash(request.requirement)}"
       cached = await redis_cache.get(cache_key)

       if cached:
           return TemplateQueryResponse(**cached, cache_hit=True)

       # Query vector DB
       templates = rag_manager.search_templates(
           requirement=request.requirement,
           persona_id=request.persona_id,
           top_k=request.top_k
       )

       # Cache result
       await redis_cache.set(cache_key, templates, ttl=3600)

       return TemplateQueryResponse(
           templates=templates,
           similarity_scores=[t['similarity'] for t in templates],
           cache_hit=False
       )

   @app.get("/health")
   async def health():
       return {"status": "healthy", "service": "rag-reader"}
   ```

2. **Add caching layer** (Redis)
   - Cache template queries (1 hour TTL)
   - Cache pattern queries (30 min TTL)
   - Invalidate on template updates

3. **Create startup script** - `scripts/start_rag_reader.sh`
   ```bash
   #!/bin/bash
   cd /home/ec2-user/projects/maestro-engine
   python3.11 src/services/rag_reader_service.py
   ```

4. **Add to configuration** - Update `.env`
   ```bash
   # RAG Reader Service
   RAG_READER_URL=http://localhost:9801
   RAG_READER_PORT=9801
   RAG_READER_CACHE_TTL=3600
   ```

**Deliverables**:
- RAG Reader Service (FastAPI)
- Redis caching layer
- Health endpoints
- Service startup script

**Estimated Effort**: 1 day

---

### Phase 4: RAG Writer Service

**Goal**: Create FastAPI service for async indexing

**Tasks**:
1. **Create `src/services/rag_writer_service.py`**
   ```python
   from fastapi import FastAPI, BackgroundTasks
   from celery import Celery

   app = FastAPI(title="RAG Writer Service", version="1.0.0")
   celery = Celery('rag_writer', broker='redis://localhost:6379/2')

   class IndexRequest(BaseModel):
       session_id: str
       project_dir: str
       requirement: str
       personas_executed: List[str]
       quality_score: Optional[float] = None

   @celery.task
   def index_project_async(session_id: str, project_dir: str, ...):
       """Async task to index completed project"""

       # 1. Quality Gate Check
       if quality_score and quality_score < 0.8:
           logger.warning(f"Quality score too low: {quality_score}")
           return {"status": "rejected", "reason": "low_quality"}

       # 2. Extract collaterals from project_dir
       collaterals = collateral_extractor.extract_from_directory(project_dir)

       # 3. Index execution metadata
       rag_manager.index_execution(
           session_id=session_id,
           requirement=requirement,
           personas=personas_executed,
           collaterals=collaterals,
           quality_score=quality_score
       )

       # 4. Index individual files as templates
       for collateral in collaterals:
           rag_manager.index_template(
               content=collateral.content,
               metadata={
                   "persona": collateral.persona,
                   "file_type": collateral.file_type,
                   "tags": collateral.tags,
                   "quality_score": quality_score
               }
           )

       # 5. Commit to maestro-templates repository
       if settings.enable_git_storage:
           git_sync.commit_templates(session_id, collaterals)

       return {"status": "indexed", "collaterals_count": len(collaterals)}

   @app.post("/index")
   async def index_project(request: IndexRequest, background_tasks: BackgroundTasks):
       """Index completed project (async)"""

       task = index_project_async.delay(
           session_id=request.session_id,
           project_dir=request.project_dir,
           requirement=request.requirement,
           personas_executed=request.personas_executed,
           quality_score=request.quality_score
       )

       return {"task_id": task.id, "status": "queued"}

   @app.get("/status/{task_id}")
   async def get_task_status(task_id: str):
       """Check indexing task status"""
       task = celery.AsyncResult(task_id)
       return {"task_id": task_id, "status": task.status, "result": task.result}
   ```

2. **Set up Celery worker**
   ```bash
   celery -A src.services.rag_writer_service worker --loglevel=info
   ```

3. **Create Git sync module** - `src/rag_system/git_sync.py`
   ```python
   class GitSync:
       """Sync indexed templates to maestro-templates repository"""

       def __init__(self, repo_path: str):
           self.repo_path = Path(repo_path)
           self.repo = git.Repo(repo_path)

       def commit_templates(self, session_id: str, collaterals: List[Collateral]):
           """Commit templates to Git repository"""

           # Organize by persona and type
           for collateral in collaterals:
               dest_path = self.repo_path / collateral.persona / collateral.file_type
               dest_path.mkdir(parents=True, exist_ok=True)

               # Write file
               file_path = dest_path / f"{session_id}_{collateral.filename}"
               file_path.write_text(collateral.content)

           # Git commit
           self.repo.index.add('*')
           self.repo.index.commit(f"Add templates from session {session_id}")
           self.repo.remotes.origin.push()
   ```

4. **Add to configuration** - Update `.env`
   ```bash
   # RAG Writer Service
   RAG_WRITER_URL=http://localhost:9802
   RAG_WRITER_PORT=9802
   RAG_QUALITY_THRESHOLD=0.8
   RAG_GIT_STORAGE=true
   RAG_TEMPLATES_REPO=/home/ec2-user/projects/maestro-templates
   ```

**Deliverables**:
- RAG Writer Service (FastAPI + Celery)
- Async indexing tasks
- Quality gate validation
- Git sync to maestro-templates
- Task status tracking

**Estimated Effort**: 2 days

---

### Phase 5: Workflow Engine Integration

**Goal**: Integrate RAG Reader into persona execution flow

**Tasks**:
1. **Modify `autonomous_sdlc_engine_v3_resumable.py`**
   ```python
   async def _execute_persona(
       self,
       persona_id: str,
       requirement: str,
       session: SDLCSession
   ) -> PersonaExecutionContext:
       """Execute a single persona with RAG context"""

       persona_context = PersonaExecutionContext(...)

       try:
           persona_config = self.persona_configs[persona_id]

           # NEW: Query RAG Reader for persona-specific templates
           if settings.rag_reader_enabled:
               rag_context = await self._query_rag_for_persona(
                   persona_id,
                   requirement
               )
           else:
               rag_context = None

           # Build prompt with RAG context
           prompt = self._build_persona_prompt_with_rag(
               persona_config,
               requirement,
               session_context,
               rag_context  # NEW
           )

           # Execute with Claude Code SDK
           async for message in query(prompt=prompt, options=options):
               # ... existing code

       except Exception as e:
           # ... existing error handling

   async def _query_rag_for_persona(
       self,
       persona_id: str,
       requirement: str
   ) -> Dict[str, Any]:
       """Query RAG Reader service for persona context"""

       import aiohttp

       async with aiohttp.ClientSession() as session:
           async with session.post(
               f"{settings.rag_reader_url}/query/templates",
               json={
                   "persona_id": persona_id,
                   "requirement": requirement,
                   "top_k": 5
               }
           ) as resp:
               if resp.status == 200:
                   return await resp.json()
               else:
                   logger.warning(f"RAG query failed: {resp.status}")
                   return {"templates": [], "cache_hit": False}

   def _build_persona_prompt_with_rag(
       self,
       persona_config: Dict[str, Any],
       requirement: str,
       session_context: str,
       rag_context: Optional[Dict[str, Any]]
   ) -> str:
       """Build prompt with RAG templates"""

       persona_name = persona_config["name"]

       prompt = f"""You are the {persona_name} for this project.

   SESSION CONTEXT (work already done):
   {session_context}
   """

       # NEW: Add RAG templates if available
       if rag_context and rag_context.get("templates"):
           prompt += f"""

   PROVEN TEMPLATES FROM SIMILAR PROJECTS (use these as inspiration):
   """
           for i, template in enumerate(rag_context["templates"][:3], 1):
               prompt += f"""
   Template {i} (similarity: {template['similarity']:.1%}):
   - Type: {template['type']}
   - Tags: {', '.join(template['tags'])}
   - Description: {template['description']}
   - Content preview: {template['content'][:200]}...
   """

       prompt += f"""

   Your task is to build on the existing work and create your deliverables.
   {" Use the proven templates above as inspiration but adapt to this specific requirement." if rag_context else ""}

   ... (rest of prompt)
   """

       return prompt
   ```

2. **Add RAG Writer call after workflow completion**
   ```python
   async def execute(
       self,
       requirement: str,
       session_id: Optional[str] = None,
       resume_session_id: Optional[str] = None
   ) -> Dict[str, Any]:
       """Execute SDLC workflow with session persistence"""

       # ... existing execution code

       # NEW: Index to RAG Writer after successful completion
       if result["success"] and settings.rag_writer_enabled:
           await self._index_to_rag_writer(
               session=session,
               requirement=requirement,
               project_dir=self.output_dir
           )

       return result

   async def _index_to_rag_writer(
       self,
       session: SDLCSession,
       requirement: str,
       project_dir: Path
   ):
       """Index completed project to RAG Writer"""

       import aiohttp

       async with aiohttp.ClientSession() as http_session:
           async with http_session.post(
               f"{settings.rag_writer_url}/index",
               json={
                   "session_id": session.session_id,
                   "project_dir": str(project_dir),
                   "requirement": requirement,
                   "personas_executed": session.completed_personas,
                   "quality_score": None  # TODO: Add quality scoring
               }
           ) as resp:
               if resp.status == 200:
                   data = await resp.json()
                   logger.info(f"✅ RAG indexing queued: task_id={data['task_id']}")
               else:
                   logger.warning(f"❌ RAG indexing failed: {resp.status}")
   ```

3. **Update configuration** - Add to `src/config/settings.py`
   ```python
   class Settings(BaseSettings):
       # ... existing settings

       # RAG Integration
       rag_reader_enabled: bool = Field(default=False)
       rag_reader_url: str = Field(default="http://localhost:9801")
       rag_writer_enabled: bool = Field(default=False)
       rag_writer_url: str = Field(default="http://localhost:9802")
       rag_quality_threshold: float = Field(default=0.8)
   ```

**Deliverables**:
- Modified workflow engine with RAG integration
- Persona-level RAG queries before execution
- Post-workflow RAG indexing
- Configuration updates

**Estimated Effort**: 1 day

---

### Phase 6: maestro-templates Repository

**Goal**: Create template library structure

**Tasks**:
1. **Initialize repository**
   ```bash
   mkdir -p /home/ec2-user/projects/maestro-templates
   cd /home/ec2-user/projects/maestro-templates
   git init
   ```

2. **Create directory structure**
   ```
   maestro-templates/
   ├── README.md
   ├── frontend_developer/
   │   ├── components/
   │   ├── pages/
   │   ├── hooks/
   │   └── utilities/
   ├── backend_developer/
   │   ├── apis/
   │   ├── models/
   │   ├── services/
   │   └── middleware/
   ├── devops_engineer/
   │   ├── kubernetes/
   │   ├── docker/
   │   ├── pipelines/
   │   └── terraform/
   ├── database_administrator/
   │   ├── schemas/
   │   ├── migrations/
   │   └── queries/
   ├── qa_engineer/
   │   ├── test-plans/
   │   ├── test-cases/
   │   └── automation/
   ├── security_specialist/
   │   ├── audits/
   │   ├── policies/
   │   └── scan-configs/
   └── ... (5 more personas)
   ```

3. **Create metadata system**
   ```yaml
   # Each template has metadata.yaml
   template_id: "react_component_auth_form"
   persona: "frontend_developer"
   type: "component"
   tags: ["react", "typescript", "authentication", "form"]
   quality_score: 0.95
   success_count: 12
   usage_count: 15
   created_at: "2025-10-03T10:00:00Z"
   last_used: "2025-10-03T14:30:00Z"
   source_session: "blog_project_v1"
   ```

4. **Seed with initial templates**
   - Copy 20-30 high-quality templates from existing projects
   - Add metadata files
   - Commit to repository

**Deliverables**:
- maestro-templates repository
- Directory structure
- Metadata system
- Initial template seed data

**Estimated Effort**: 0.5 day

---

## Part 5: What Can Be Leveraged

### From Existing RAG Code

**✅ Leverage As-Is**:
1. **@tool decorator pattern** - Perfect for Claude SDK integration
2. **First-Strike parallel query strategy** - Adapt for persona-level
3. **Tool schema definitions** - Reuse JSON schemas
4. **System prompt building approach** - Adapt for persona-specific prompts
5. **Tool description formatting** - Excellent documentation structure

**🔄 Adapt and Modify**:
1. **RAG_TOOLS list** - Add persona_id parameter to all functions
2. **get_swift_mvp_plan** - Create persona-specific version
3. **HotClaudeRAGSession** - Extract system prompt building logic
4. **Assumption logging** - Integrate with persona execution

**❌ Cannot Use Directly**:
1. **HotClaudeRAGSession class** - Too execution-level focused
2. **Tool execution flow** - Doesn't fit persona architecture
3. **Session management** - Already have SessionManager

### Code Reuse Examples

#### Example 1: Adapt First-Strike for Personas
**Original**:
```python
@tool(name="get_swift_mvp_plan")
def get_swift_mvp_plan(requirement: str) -> str:
    # Queries everything for entire workflow
```

**Adapted**:
```python
@tool(name="get_persona_context")
def get_persona_context(persona_id: str, requirement: str) -> str:
    """Get domain-specific context for persona"""

    # Parallel queries scoped to persona domain
    with ThreadPoolExecutor(max_workers=3) as executor:
        templates_future = executor.submit(
            rag_manager.search_templates,
            requirement, persona_id
        )
        patterns_future = executor.submit(
            rag_manager.search_patterns,
            persona_id, requirement
        )
        examples_future = executor.submit(
            rag_manager.search_examples,
            persona_id, requirement
        )

    return json.dumps({
        "templates": templates_future.result(),
        "patterns": patterns_future.result(),
        "examples": examples_future.result()
    })
```

#### Example 2: Reuse Tool Schema Pattern
**Original**:
```python
@tool(
    name="query_similar_projects",
    description="Search for similar historical projects",
    input_schema={
        "type": "object",
        "properties": {
            "requirement": {"type": "string", "description": "..."},
            "top_k": {"type": "integer", "default": 3}
        },
        "required": ["requirement"]
    }
)
```

**Reused**:
```python
@tool(
    name="query_persona_templates",
    description="Search for templates specific to persona domain",
    input_schema={
        "type": "object",
        "properties": {
            "persona_id": {"type": "string", "description": "Persona ID"},
            "requirement": {"type": "string", "description": "..."},
            "top_k": {"type": "integer", "default": 5}
        },
        "required": ["persona_id", "requirement"]
    }
)
```

---

## Part 6: Migration Roadmap

### Summary Timeline

| Phase | Tasks | Effort | Status |
|-------|-------|--------|--------|
| **Phase 1** | Backend Implementation | 1-2 days | 🔲 Not Started |
| **Phase 2** | Persona-Level RAG Tools | 1 day | 🔲 Not Started |
| **Phase 3** | RAG Reader Service | 1 day | 🔲 Not Started |
| **Phase 4** | RAG Writer Service | 2 days | 🔲 Not Started |
| **Phase 5** | Workflow Integration | 1 day | 🔲 Not Started |
| **Phase 6** | maestro-templates Repo | 0.5 day | 🔲 Not Started |
| **Total** | | **6.5-7.5 days** | |

### Critical Dependencies

```
Phase 1 (Backend) ───┐
                     ├──> Phase 2 (Persona Tools) ───┐
                     │                                ├──> Phase 5 (Integration)
Phase 3 (Reader) ────┤                                │
                     ├──> Phase 4 (Writer) ──────────┘
Phase 6 (Templates) ─┘
```

**Parallel Work Possible**:
- Phase 3 + Phase 4 (Reader and Writer can be built in parallel)
- Phase 6 (Templates repo) can start anytime

**Sequential Dependencies**:
- Phase 1 must complete before Phase 2
- Phase 2 + Phase 3 + Phase 4 must complete before Phase 5

### Recommended Order

**Week 1**:
- Days 1-2: Phase 1 (Backend Implementation)
- Day 3: Phase 2 (Persona-Level RAG Tools)
- Days 4-5: Phase 3 + Phase 6 (Reader Service + Templates Repo in parallel)

**Week 2**:
- Days 1-2: Phase 4 (Writer Service)
- Day 3: Phase 5 (Workflow Integration)
- Days 4-5: Testing, documentation, refinement

---

## Part 7: Testing Strategy

### Unit Tests

**Backend Components** (`tests/test_rag_system/`):
```python
def test_vector_rag_manager_search():
    """Test RAG search functionality"""
    rag_manager = VectorRAGManager(mock_chroma_client)
    results = rag_manager.search_similar_executions("Build a blog", top_k=3)
    assert len(results) <= 3
    assert all('similarity' in r for r in results)

def test_pattern_recommender_team():
    """Test team recommendation"""
    recommender = PatternRecommender()
    team = recommender.recommend_team_composition("Build API")
    assert 'recommended_team' in team
    assert len(team['recommended_team']) > 0
```

**RAG Tools** (`tests/test_rag/`):
```python
def test_persona_rag_tools():
    """Test persona-scoped RAG tools"""
    result = query_persona_templates("frontend_developer", "Create login form")
    templates = json.loads(result)
    assert 'templates' in templates
    # Verify templates are frontend-specific
    assert all('react' in t['tags'] or 'vue' in t['tags'] for t in templates['templates'])
```

### Integration Tests

**RAG Reader Service** (`tests/test_services/`):
```python
async def test_rag_reader_query():
    """Test RAG Reader API"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:9801/query/templates",
            json={
                "persona_id": "frontend_developer",
                "requirement": "Build login form",
                "top_k": 5
            }
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            assert 'templates' in data
            assert len(data['templates']) <= 5
```

**Workflow Integration** (`tests/test_integration/`):
```python
async def test_persona_execution_with_rag():
    """Test persona execution with RAG context"""
    engine = AutonomousSDLCEngineV3Resumable(
        selected_personas=["frontend_developer"],
        output_dir="/tmp/test_rag_integration"
    )

    result = await engine.execute(
        requirement="Build a login form with React",
        session_id="test_rag_001"
    )

    assert result["success"]
    assert len(result["files"]) > 0
    # Verify RAG context was used (check logs or prompt)
```

### End-to-End Tests

**Full Workflow** (`tests/test_e2e/`):
```python
async def test_full_workflow_with_rag():
    """Test complete workflow: Query → Execute → Index"""

    # 1. Start RAG services
    # 2. Execute workflow with 3 personas
    # 3. Verify RAG queries were made
    # 4. Verify files created
    # 5. Verify RAG Writer indexed results
    # 6. Query RAG Reader for newly indexed templates
    # 7. Verify new templates are returned
```

---

## Part 8: Recommendations

### Immediate Next Steps (TODAY)

1. **Start with Phase 1: Backend Implementation**
   - Create `src/rag_system/` module structure
   - Implement `vector_rag_manager.py` with ChromaDB
   - Add ChromaDB to requirements: `pip install chromadb`
   - Write unit tests for backend components

2. **Set up ChromaDB**
   - Configure persistent directory: `/tmp/maestro_rag_db`
   - Create collections: executions, collaterals, patterns
   - Seed with sample data (5-10 mock projects)

3. **Validate Existing RAG Tools**
   - Fix import errors in `rag_tools.py`
   - Test each tool function with mock backend
   - Verify @tool decorators work with Claude SDK

### Medium-Term (THIS WEEK)

1. **Implement Persona-Level RAG Tools** (Phase 2)
   - Create persona domain mappings
   - Build persona-scoped query functions
   - Integrate with existing RAG tools

2. **Build RAG Reader Service** (Phase 3)
   - FastAPI service on port 9801
   - Redis caching layer
   - Health endpoints and monitoring

3. **Initialize maestro-templates Repository** (Phase 6)
   - Create directory structure
   - Add metadata system
   - Seed with 20-30 templates

### Long-Term (NEXT WEEK)

1. **Build RAG Writer Service** (Phase 4)
   - FastAPI + Celery on port 9802
   - Async indexing pipeline
   - Git sync to maestro-templates

2. **Integrate with Workflow Engine** (Phase 5)
   - Modify `autonomous_sdlc_engine_v3_resumable.py`
   - Add RAG queries to persona execution
   - Add post-workflow indexing

3. **Testing and Refinement**
   - End-to-end workflow tests
   - Performance optimization
   - Documentation updates

### What NOT to Do

❌ **Don't rebuild HotClaudeRAGSession** - It's execution-level, we need persona-level
❌ **Don't use RAG for workflow orchestration** - Keep orchestration simple
❌ **Don't make RAG blocking** - Persona should execute even if RAG fails
❌ **Don't over-engineer** - Start simple, add features incrementally

### Success Criteria

**Phase 1 Complete When**:
- ✅ RAG backend modules implemented and tested
- ✅ ChromaDB set up with sample data
- ✅ Existing RAG tools work with new backend

**Phase 2 Complete When**:
- ✅ Persona domain mappings defined
- ✅ Persona-scoped RAG tools implemented
- ✅ Tools return domain-specific results

**Phase 3 Complete When**:
- ✅ RAG Reader service running on port 9801
- ✅ Template queries return results in <200ms (cached)
- ✅ Health endpoint returns 200

**Phase 4 Complete When**:
- ✅ RAG Writer service running on port 9802
- ✅ Async indexing tasks execute successfully
- ✅ Templates committed to maestro-templates repo

**Phase 5 Complete When**:
- ✅ Personas query RAG Reader before execution
- ✅ RAG context included in persona prompts
- ✅ Completed workflows indexed by RAG Writer
- ✅ End-to-end workflow test passes

**Final Success**:
- ✅ Frontend Developer queries React templates
- ✅ DevOps Engineer queries K8s templates
- ✅ Completed projects automatically indexed
- ✅ Templates reused in future projects
- ✅ System learns and improves over time

---

## Conclusion

**Existing RAG Code Assessment**: ⭐⭐⭐⭐ (4/5 stars)
- Well-designed tool architecture
- Excellent First-Strike parallel query approach
- Good documentation and system prompts
- Missing backend implementation
- Wrong architecture level (execution vs persona)

**Leverage Strategy**: 🔄 **Adapt, Don't Rebuild**
- Reuse tool decorator patterns
- Adapt query functions for persona scope
- Keep First-Strike parallel approach
- Add persona domain filtering
- Build missing backend components

**Integration Complexity**: 🟡 **Medium**
- Backend implementation: Moderate effort
- Service architecture: Standard FastAPI + Celery
- Workflow integration: Clean injection points exist
- Testing: Comprehensive but straightforward

**Estimated Timeline**: 📅 **6.5-7.5 days**
- Can be parallelized to ~4-5 calendar days with 2 developers

**Risk Level**: 🟢 **Low**
- Existing code provides proven patterns
- Backend components are standard (ChromaDB, FastAPI, Celery)
- Workflow integration is non-invasive
- Can be developed incrementally

**Recommendation**: ✅ **PROCEED WITH INTEGRATION**
1. Start with Phase 1 (Backend) immediately
2. Validate with Phase 2 (Persona Tools)
3. Build services in parallel (Phases 3-4)
4. Integrate carefully (Phase 5)
5. Test thoroughly before production

---

**Next Action**: Begin Phase 1 - Backend Implementation

**Created**: 2025-10-03
**Author**: RAG Integration Analysis
**Status**: Ready for Implementation
