# Holistic Database Design - Integrating Personas, Phases, Teams & Workflows

## Executive Summary

This document provides a comprehensive database architecture that unifies:
- **Existing**: ai_agents (personas with roles & artifacts)
- **Existing**: workflows, phases, checkpoints
- **New**: Intelligent workflow platform with learning & recommendations

## Current State Analysis

### What We Have

#### 1. Persona System (`ai_agents` table)
```sql
ai_agents {
  - persona_id: Unique persona identifier
  - role: Agent's role description
  - primary_role: Categorized role
  - specializations: Skills array
  - capabilities: What they can do
  - technical_skills: Technical expertise
  - soft_skills: Communication, collaboration
  - deliverable_types: Array of deliverable types
  - artifact_formats: Array of output formats
  - persona_definition: Full JSON profile
}
```

**Key Insight**: Personas already have roles AND output artifacts defined!

#### 2. Workflow System (Dual Systems)
- **Traditional Workflows** (`workflows` → `phases` → `tasks`)
- **DAG Workflows** (`dag_workflows` with JSON structure)

#### 3. Phase & Team Assignments
- `phase_team_members`: Links phases to agents/users
- `phase_templates`: Template-based phase definitions
- `checkpoint_templates`: Reusable checkpoint definitions

### What's Missing

1. **Analytics & Learning Tables**: No workflow execution tracking
2. **Confidence Scoring**: No team assignment confidence data
3. **Performance Metrics**: No agent performance history
4. **Phase Type Standards**: No standardized phase type catalog
5. **Artifact-Phase Mapping**: No explicit link between phase types and expected artifacts

---

## Holistic Database Design

### Design Principles

1. **Don't Break Existing**: Build on current schema, don't replace
2. **Link, Don't Duplicate**: Use foreign keys to existing tables
3. **Analytics Layer**: Add learning/metrics tables above existing structure
4. **Backward Compatible**: Existing workflows continue to work

---

## New Tables

### 1. Phase Type Catalog (`phase_type_catalog`)

**Purpose**: Standardize phase types across the platform

```sql
CREATE TABLE phase_type_catalog (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Core Identity
  type_key VARCHAR(100) UNIQUE NOT NULL, -- 'requirements', 'architecture', 'implementation', etc.
  display_name VARCHAR(255) NOT NULL,
  description TEXT,
  category VARCHAR(50), -- 'planning', 'development', 'quality', 'deployment'

  -- Phase Characteristics
  typical_duration_days INT DEFAULT 7,
  complexity_score FLOAT DEFAULT 5.0, -- 1-10 scale
  icon VARCHAR(50),
  color VARCHAR(20),

  -- Team Requirements
  required_skills JSONB DEFAULT '[]', -- ['frontend', 'backend', 'architecture']
  typical_team_size INT DEFAULT 2,
  requires_human_approval BOOLEAN DEFAULT false,

  -- Artifact Requirements
  expected_deliverable_types TEXT[] DEFAULT '{}', -- Links to ai_agents.deliverable_types
  expected_artifact_formats TEXT[] DEFAULT '{}', -- Links to ai_agents.artifact_formats

  -- Metadata
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_phase_type_key ON phase_type_catalog(type_key);
CREATE INDEX idx_phase_type_category ON phase_type_catalog(category);
CREATE INDEX idx_phase_type_skills ON phase_type_catalog USING GIN(required_skills);
```

**Example Data**:
```sql
INSERT INTO phase_type_catalog (type_key, display_name, category, required_skills, expected_deliverable_types) VALUES
('requirements', 'Requirements Gathering', 'planning',
 '["requirements_analysis", "stakeholder_management"]',
 '["requirements-doc", "user-stories", "acceptance-criteria"]'),

('architecture', 'System Architecture', 'planning',
 '["system_design", "architecture", "scalability"]',
 '["architecture-doc", "design-diagrams", "api-specs"]'),

('implementation', 'Implementation', 'development',
 '["coding", "software_development"]',
 '["source-code", "unit-tests", "documentation"]');
```

---

### 2. Persona Phase Expertise (`persona_phase_expertise`)

**Purpose**: Link personas to phase types with expertise levels

```sql
CREATE TABLE persona_phase_expertise (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- References
  ai_agent_id VARCHAR(255) REFERENCES ai_agents(id) ON DELETE CASCADE,
  phase_type_key VARCHAR(100) REFERENCES phase_type_catalog(type_key) ON DELETE CASCADE,

  -- Expertise Assessment
  expertise_level FLOAT DEFAULT 5.0, -- 1-10 scale
  confidence_score FLOAT DEFAULT 0.75, -- 0-1 scale
  total_assignments INT DEFAULT 0,
  successful_completions INT DEFAULT 0,

  -- Performance Metrics
  avg_completion_time_seconds INT,
  avg_quality_score FLOAT,
  collaboration_score FLOAT DEFAULT 0.8, -- How well they work in teams

  -- Preferences
  prefers_parallel BOOLEAN DEFAULT false, -- Can work in parallel phases
  prefers_leadership BOOLEAN DEFAULT false, -- Prefers lead role

  -- Metadata
  last_assigned_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(ai_agent_id, phase_type_key)
);

CREATE INDEX idx_persona_phase_agent ON persona_phase_expertise(ai_agent_id);
CREATE INDEX idx_persona_phase_type ON persona_phase_expertise(phase_type_key);
CREATE INDEX idx_persona_phase_expertise ON persona_phase_expertise(expertise_level DESC);
```

---

### 3. Workflow Executions (`workflow_executions`)

**Purpose**: Track workflow performance for learning

```sql
CREATE TABLE workflow_executions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- References (flexible to support both workflow types)
  workflow_id VARCHAR(255), -- Can reference workflows.id OR dag_workflows.id
  workflow_type VARCHAR(50) DEFAULT 'dag', -- 'traditional' or 'dag'
  project_id VARCHAR(255) REFERENCES projects(id) ON DELETE SET NULL,

  -- Project Classification
  project_type VARCHAR(100), -- 'saas_platform', 'mobile_app', 'api_service'
  complexity VARCHAR(50), -- 'simple', 'medium', 'complex', 'enterprise'
  tech_stack JSONB DEFAULT '[]', -- ['react', 'nodejs', 'postgresql']

  -- Workflow Structure
  total_phases INT,
  phase_types_used TEXT[], -- ['requirements', 'architecture', 'implementation']
  execution_mode VARCHAR(50), -- 'serial', 'parallel', 'mixed'

  -- Team Composition
  team_assignments JSONB DEFAULT '{}', -- { "requirements-001": ["ai-product-manager"] }
  total_team_members INT,
  ai_agents_count INT,
  human_members_count INT,

  -- Execution Metrics
  status VARCHAR(50) DEFAULT 'in_progress', -- 'in_progress', 'completed', 'failed', 'abandoned'
  started_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  total_duration_seconds INT, -- Auto-calculated

  -- Quality Metrics
  success_score FLOAT, -- 0-100 based on quality gates
  phases_completed INT DEFAULT 0,
  phases_failed INT DEFAULT 0,
  checkpoints_passed INT DEFAULT 0,
  checkpoints_failed INT DEFAULT 0,
  avg_quality_gate_score FLOAT,

  -- User Interaction
  user_modifications JSONB DEFAULT '{}', -- Track what user changed from AI suggestions
  user_feedback JSONB DEFAULT '{}', -- { "rating": 5, "comments": "Great workflow" }
  ai_suggestions_accepted INT DEFAULT 0,
  ai_suggestions_rejected INT DEFAULT 0,

  -- Context
  conversation_context_used BOOLEAN DEFAULT false,
  generation_method VARCHAR(100), -- 'ai_generated', 'template_based', 'manual'

  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_workflow_exec_workflow ON workflow_executions(workflow_id);
CREATE INDEX idx_workflow_exec_project_type ON workflow_executions(project_type);
CREATE INDEX idx_workflow_exec_status ON workflow_executions(status);
CREATE INDEX idx_workflow_exec_success ON workflow_executions(success_score DESC);
CREATE INDEX idx_workflow_exec_tech ON workflow_executions USING GIN(tech_stack);
```

---

### 4. Phase Execution History (`phase_execution_history`)

**Purpose**: Granular phase-level performance tracking

```sql
CREATE TABLE phase_execution_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- References
  workflow_execution_id UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
  phase_id VARCHAR(255), -- From workflows or dag node id
  phase_type_key VARCHAR(100) REFERENCES phase_type_catalog(type_key),

  -- Team Assignment
  assigned_agents JSONB DEFAULT '[]', -- [{"agent_id": "ai-product-manager", "role": "lead"}]
  assigned_humans JSONB DEFAULT '[]',
  lead_agent_id VARCHAR(255) REFERENCES ai_agents(id),

  -- Execution
  status VARCHAR(50) DEFAULT 'pending',
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  duration_seconds INT,

  -- Quality
  quality_score FLOAT, -- 0-100
  checkpoints_total INT DEFAULT 0,
  checkpoints_passed INT DEFAULT 0,
  quality_gates_total INT DEFAULT 0,
  quality_gates_passed INT DEFAULT 0,

  -- Artifacts
  artifacts_produced JSONB DEFAULT '[]', -- [{"type": "requirements-doc", "url": "..."}]
  artifacts_count INT DEFAULT 0,

  -- Issues
  issues_encountered JSONB DEFAULT '[]', -- [{"type": "technical", "description": "..."}]
  retry_count INT DEFAULT 0,

  -- Metadata
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_phase_exec_workflow ON phase_execution_history(workflow_execution_id);
CREATE INDEX idx_phase_exec_type ON phase_execution_history(phase_type_key);
CREATE INDEX idx_phase_exec_agent ON phase_execution_history(lead_agent_id);
CREATE INDEX idx_phase_exec_status ON phase_execution_history(status);
```

---

### 5. Team Assignment Recommendations (`team_assignment_recommendations`)

**Purpose**: AI-generated team suggestions with confidence scores

```sql
CREATE TABLE team_assignment_recommendations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Context
  workflow_execution_id UUID REFERENCES workflow_executions(id) ON DELETE CASCADE,
  phase_id VARCHAR(255),
  phase_type_key VARCHAR(100) REFERENCES phase_type_catalog(type_key),
  project_type VARCHAR(100),

  -- Recommendation
  recommended_agent_id VARCHAR(255) REFERENCES ai_agents(id),
  recommended_role VARCHAR(100), -- 'lead', 'contributor', 'reviewer'

  -- Confidence Scoring
  confidence_score FLOAT NOT NULL, -- 0-1 scale
  confidence_level VARCHAR(20), -- 'high' (>0.9), 'medium' (0.75-0.9), 'low' (<0.75)

  -- Confidence Breakdown
  skill_match_score FLOAT, -- 0-1
  historical_success_rate FLOAT, -- 0-1
  collaboration_score FLOAT, -- 0-1
  availability_score FLOAT, -- 0-1

  -- Reasoning
  reasoning TEXT, -- AI explanation for recommendation
  strengths TEXT[], -- ["Strong React experience", "High success rate"]
  concerns TEXT[], -- ["Limited experience with PostgreSQL"]

  -- Alternatives
  alternative_agents JSONB DEFAULT '[]', -- [{"agent_id": "...", "confidence": 0.75}]

  -- User Response
  accepted BOOLEAN,
  user_chosen_agent_id VARCHAR(255), -- If user selected different agent
  user_feedback TEXT,

  -- Metadata
  generated_by VARCHAR(100) DEFAULT 'ai_enhancer', -- 'ai_enhancer', 'learning_engine'
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_team_rec_workflow ON team_assignment_recommendations(workflow_execution_id);
CREATE INDEX idx_team_rec_agent ON team_assignment_recommendations(recommended_agent_id);
CREATE INDEX idx_team_rec_confidence ON team_assignment_recommendations(confidence_score DESC);
CREATE INDEX idx_team_rec_accepted ON team_assignment_recommendations(accepted);
```

---

### 6. Workflow Learning Patterns (`workflow_learning_patterns`)

**Purpose**: Extract and store successful patterns for recommendations

```sql
CREATE TABLE workflow_learning_patterns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Pattern Classification
  pattern_type VARCHAR(50) NOT NULL, -- 'phase_sequence', 'team_composition', 'checkpoint_effectiveness'
  project_type VARCHAR(100) NOT NULL, -- 'saas_platform', 'mobile_app'
  complexity VARCHAR(50), -- 'simple', 'medium', 'complex'

  -- Pattern Data
  pattern_name VARCHAR(255) NOT NULL,
  pattern_description TEXT,
  pattern_data JSONB NOT NULL, -- Flexible structure based on pattern_type

  -- Statistical Validity
  confidence_score FLOAT NOT NULL, -- 0-1 based on sample size and consistency
  sample_size INT NOT NULL, -- Number of workflows this pattern is based on
  success_rate FLOAT NOT NULL, -- 0-1 success rate of this pattern

  -- Performance Impact
  avg_duration_seconds INT,
  avg_success_score FLOAT, -- 0-100
  improvement_vs_baseline FLOAT, -- Percentage improvement

  -- Recommendations
  recommended_for TEXT[], -- ["multi_tenant_saas", "payment_integration"]
  not_recommended_for TEXT[],

  -- Pattern Examples
  example_workflow_ids TEXT[], -- Reference to successful workflows

  -- Metadata
  is_active BOOLEAN DEFAULT true,
  last_validated_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_learning_pattern_type ON workflow_learning_patterns(pattern_type);
CREATE INDEX idx_learning_project_type ON workflow_learning_patterns(project_type);
CREATE INDEX idx_learning_confidence ON workflow_learning_patterns(confidence_score DESC);
CREATE INDEX idx_learning_active ON workflow_learning_patterns(is_active);
```

**Example Pattern**:
```json
{
  "pattern_type": "team_composition",
  "project_type": "saas_platform",
  "pattern_data": {
    "phases": {
      "requirements": ["ai-product-manager"],
      "architecture": ["ai-architect", "ai-security-specialist"],
      "implementation": ["ai-senior-developer", "ai-developer-001", "ai-developer-002"]
    },
    "insight": "Adding security specialist early reduces production issues by 35%"
  },
  "confidence_score": 0.89,
  "sample_size": 15
}
```

---

## Updated Existing Tables

### Enhance `phases` table

```sql
-- Add new columns to existing phases table
ALTER TABLE phases ADD COLUMN phase_type_key VARCHAR(100) REFERENCES phase_type_catalog(type_key);
ALTER TABLE phases ADD COLUMN quality_score FLOAT;
ALTER TABLE phases ADD COLUMN confidence_score FLOAT;
ALTER TABLE phases ADD COLUMN ai_recommended BOOLEAN DEFAULT false;

CREATE INDEX idx_phases_type_key ON phases(phase_type_key);
```

### Enhance `phase_team_members` table

```sql
-- Add confidence and recommendation tracking
ALTER TABLE phase_team_members ADD COLUMN assignment_confidence FLOAT;
ALTER TABLE phase_team_members ADD COLUMN ai_recommended BOOLEAN DEFAULT false;
ALTER TABLE phase_team_members ADD COLUMN recommendation_id UUID REFERENCES team_assignment_recommendations(id);

CREATE INDEX idx_phase_team_recommendation ON phase_team_members(recommendation_id);
```

### Enhance `ai_agents` table

```sql
-- Add performance summary (calculated periodically)
ALTER TABLE ai_agents ADD COLUMN total_assignments INT DEFAULT 0;
ALTER TABLE ai_agents ADD COLUMN successful_completions INT DEFAULT 0;
ALTER TABLE ai_agents ADD COLUMN avg_quality_score FLOAT;
ALTER TABLE ai_agents ADD COLUMN collaboration_rating FLOAT DEFAULT 0.8;

CREATE INDEX idx_ai_agents_performance ON ai_agents(successful_completions DESC, avg_quality_score DESC);
```

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     PERSONA & ROLE SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ai_agents (Personas)                                            │
│  ├─ persona_id, role, primary_role                              │
│  ├─ specializations, capabilities                               │
│  ├─ technical_skills, soft_skills                               │
│  ├─ deliverable_types, artifact_formats                         │
│  └─ persona_definition                                           │
│                  │                                               │
│                  ├──────────────┐                                │
│                  │              │                                │
│                  ▼              ▼                                │
│    persona_phase_expertise   phase_type_catalog                 │
│    (Persona ↔ Phase Type)    (Standard Phase Types)            │
│    ├─ expertise_level         ├─ type_key                       │
│    ├─ confidence_score        ├─ required_skills                │
│    ├─ total_assignments       ├─ expected_deliverable_types     │
│    └─ performance_metrics     └─ typical_team_size              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                  WORKFLOW EXECUTION SYSTEM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  workflow_executions (Learning & Analytics)                      │
│  ├─ workflow_id (links to workflows OR dag_workflows)           │
│  ├─ project_type, tech_stack, complexity                        │
│  ├─ team_assignments, execution metrics                         │
│  ├─ success_score, user_modifications                           │
│  └─ ai_suggestions_accepted/rejected                            │
│                  │                                               │
│                  ├───────────────┬─────────────────┐            │
│                  ▼               ▼                 ▼             │
│    phase_execution_history  workflows      dag_workflows        │
│    (Phase Performance)      (Traditional)  (ReactFlow DAG)      │
│    ├─ phase_type_key        ├─ phases      ├─ workflowData     │
│    ├─ assigned_agents       └─ tasks       └─ (JSON)           │
│    ├─ quality_score                                             │
│    └─ artifacts_produced                                        │
│                  │                                               │
│                  ▼                                               │
│    team_assignment_recommendations                              │
│    (AI Suggestions with Confidence)                             │
│    ├─ recommended_agent_id                                      │
│    ├─ confidence_score (breakdown)                              │
│    ├─ reasoning, strengths, concerns                            │
│    ├─ alternative_agents                                        │
│    └─ user acceptance tracking                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LEARNING ENGINE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  workflow_learning_patterns                                      │
│  ├─ pattern_type (phase_sequence, team_composition)             │
│  ├─ project_type, complexity                                    │
│  ├─ pattern_data (flexible JSONB)                               │
│  ├─ confidence_score, sample_size                               │
│  ├─ success_rate, improvement_vs_baseline                       │
│  └─ example_workflow_ids                                        │
│                                                                  │
│  Feeds back into team_assignment_recommendations                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: From Persona to Workflow Assignment

### 1. Persona Definition (Existing)
```sql
SELECT
  id, name, role, primary_role,
  specializations, capabilities,
  technical_skills, soft_skills,
  deliverable_types, artifact_formats
FROM ai_agents
WHERE status = 'active';
```

### 2. Phase Type ↔ Persona Expertise (New)
```sql
-- Which personas are best for a requirements phase?
SELECT
  a.id, a.name, a.primary_role,
  ppe.expertise_level,
  ppe.confidence_score,
  ppe.total_assignments,
  ppe.successful_completions
FROM persona_phase_expertise ppe
JOIN ai_agents a ON ppe.ai_agent_id = a.id
WHERE ppe.phase_type_key = 'requirements'
ORDER BY ppe.expertise_level DESC, ppe.confidence_score DESC;
```

### 3. AI-Powered Team Recommendation (New)
```sql
-- Generate recommendation for a phase
INSERT INTO team_assignment_recommendations (
  workflow_execution_id,
  phase_type_key,
  recommended_agent_id,
  confidence_score,
  skill_match_score,
  historical_success_rate,
  reasoning
) VALUES (
  'workflow-exec-123',
  'requirements',
  'ai-product-manager',
  0.92,
  0.95,
  0.88,
  'High skill match: requirements analysis (0.95). Historical success rate: 88% across 15 assignments.'
);
```

### 4. Track Execution (New)
```sql
-- Record phase execution
INSERT INTO phase_execution_history (
  workflow_execution_id,
  phase_id,
  phase_type_key,
  lead_agent_id,
  assigned_agents,
  status,
  quality_score
) VALUES (
  'workflow-exec-123',
  'requirements-001',
  'requirements',
  'ai-product-manager',
  '[{"agent_id": "ai-product-manager", "role": "lead"}]',
  'completed',
  92.5
);
```

### 5. Learn from Success (New)
```sql
-- Extract patterns from successful workflows
INSERT INTO workflow_learning_patterns (
  pattern_type,
  project_type,
  pattern_data,
  confidence_score,
  sample_size,
  success_rate
)
SELECT
  'team_composition' as pattern_type,
  'saas_platform' as project_type,
  jsonb_build_object(
    'phases', jsonb_agg(peh.phase_type_key),
    'teams', jsonb_agg(peh.assigned_agents)
  ) as pattern_data,
  0.89 as confidence_score,
  COUNT(*) as sample_size,
  AVG(we.success_score) / 100.0 as success_rate
FROM workflow_executions we
JOIN phase_execution_history peh ON peh.workflow_execution_id = we.id
WHERE we.project_type = 'saas_platform'
  AND we.success_score >= 85
GROUP BY we.project_type
HAVING COUNT(*) >= 5; -- Minimum sample size
```

---

## Migration Strategy

### Phase 1: Add New Tables (Non-Breaking)
```sql
-- Execute all CREATE TABLE statements
-- No impact on existing functionality
```

### Phase 2: Populate Phase Type Catalog
```sql
-- Seed standard phase types
-- Link to existing phase_templates where applicable
```

### Phase 3: Backfill Persona Expertise
```sql
-- Analyze existing ai_agents
-- Create persona_phase_expertise entries based on:
--   - technical_skills matching phase requirements
--   - specializations alignment
--   - Initial confidence scores based on skill match
```

### Phase 4: Enhance Existing Tables
```sql
-- ALTER TABLE statements
-- Add new columns to phases, phase_team_members, ai_agents
```

### Phase 5: Start Tracking
```sql
-- Workflow generation service creates workflow_executions records
-- Phase completions create phase_execution_history records
-- AI enhancer creates team_assignment_recommendations
```

### Phase 6: Enable Learning
```sql
-- Background job analyzes completed workflows
-- Extracts patterns and creates workflow_learning_patterns
-- Recommendations use patterns for improved suggestions
```

---

## API Integration Points

### 1. Fetch Available Agents (Enhanced)
```http
GET /api/ai-agents?phase_type=requirements

Response:
{
  "agents": [
    {
      "id": "ai-product-manager",
      "name": "AI Product Manager",
      "role": "Product Management",
      "deliverable_types": ["requirements-doc", "user-stories"],
      "expertise": {
        "phase_type": "requirements",
        "level": 9.2,
        "confidence": 0.92,
        "total_assignments": 45,
        "success_rate": 0.88
      }
    }
  ]
}
```

### 2. Get Team Recommendations (New)
```http
POST /api/recommendations/teams
{
  "phase_type": "requirements",
  "project_type": "saas_platform",
  "tech_stack": ["react", "nodejs"],
  "workflow_execution_id": "exec-123"
}

Response:
{
  "recommendations": [
    {
      "agent_id": "ai-product-manager",
      "agent_name": "AI Product Manager",
      "role": "lead",
      "confidence": 0.92,
      "confidence_level": "high",
      "reasoning": "Strong match: requirements analysis skills (0.95), 88% historical success rate",
      "strengths": ["High expertise in requirements", "Strong collaboration score"],
      "concerns": [],
      "alternatives": [
        {"agent_id": "ai-business-analyst", "confidence": 0.85}
      ]
    }
  ]
}
```

### 3. Track Workflow Execution (New)
```http
POST /api/workflow-executions
{
  "workflow_id": "dag-wf-123",
  "workflow_type": "dag",
  "project_type": "saas_platform",
  "tech_stack": ["react", "nodejs"],
  "phase_types_used": ["requirements", "architecture"],
  "team_assignments": {...}
}
```

---

## Benefits of This Design

### ✅ Unified System
- Single source of truth for personas (ai_agents)
- Links personas → phases → workflows seamlessly
- No duplication of persona or artifact data

### ✅ Learning-Enabled
- Tracks every workflow execution
- Learns successful patterns
- Improves recommendations over time

### ✅ Transparent AI
- Confidence scores with breakdowns
- Reasoning explanations
- Alternative suggestions
- Tracks user acceptance vs rejection

### ✅ Backward Compatible
- Existing workflows continue to work
- New tables don't break existing functionality
- Gradual migration path

### ✅ Analytics-Ready
- Rich performance metrics
- Team effectiveness tracking
- Pattern identification
- Data-driven improvements

---

## Next Steps

1. **Review & Approve Schema**: Validate this design meets all requirements
2. **Create Migration Scripts**: Write SQL migrations for Phase 1-6
3. **Update Workflow Generation Service**: Integrate with new tables
4. **Build Analytics APIs**: Implement recommendation endpoints
5. **Create Learning Jobs**: Background jobs for pattern extraction
6. **Frontend Updates**: Display confidence scores and alternatives

---

**Last Updated**: 2025-10-20
**Version**: 1.0
**Status**: Ready for Review
