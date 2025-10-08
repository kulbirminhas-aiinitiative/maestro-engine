-- MAESTRO Enterprise Template Repository Schema
-- Version: 1.0
-- Purpose: Core metadata storage for enterprise template management

-- =============================================================================
-- CORE TEMPLATE METADATA
-- =============================================================================

CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    language VARCHAR(50) NOT NULL,
    framework VARCHAR(100),
    version VARCHAR(20) NOT NULL DEFAULT '1.0.0',
    quality_score DECIMAL(5,2) CHECK (quality_score >= 0 AND quality_score <= 100),
    complexity_level VARCHAR(20) CHECK (complexity_level IN ('simple', 'intermediate', 'advanced', 'expert')),
    usage_count INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0 CHECK (success_rate >= 0 AND success_rate <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NOT NULL,
    tags TEXT[],
    description TEXT NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    vector_id VARCHAR(255), -- ChromaDB vector reference
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'approved', 'deprecated')),

    -- Multi-dimensional classification
    domain VARCHAR(100), -- auth, e-commerce, dashboard, api, ml, devops, etc.
    pattern VARCHAR(100), -- mvc, repository, factory, observer, singleton, etc.

    -- Quality dimensions
    security_score INTEGER DEFAULT 0 CHECK (security_score >= 0 AND security_score <= 100),
    performance_score INTEGER DEFAULT 0 CHECK (performance_score >= 0 AND performance_score <= 100),
    maintainability_score INTEGER DEFAULT 0 CHECK (maintainability_score >= 0 AND maintainability_score <= 100),
    test_coverage DECIMAL(5,2) DEFAULT 0 CHECK (test_coverage >= 0 AND test_coverage <= 100),

    -- Usage dimensions
    popularity VARCHAR(10) DEFAULT 'cold' CHECK (popularity IN ('hot', 'warm', 'cold')),
    maturity VARCHAR(20) DEFAULT 'experimental' CHECK (maturity IN ('experimental', 'stable', 'mature', 'legacy')),

    -- Metadata
    organization VARCHAR(100),
    project_context TEXT,
    approval_status VARCHAR(20) DEFAULT 'draft' CHECK (approval_status IN ('draft', 'review', 'approved', 'deprecated')),
    approved_by VARCHAR(100),
    approved_at TIMESTAMP,

    -- Storage tier management
    storage_tier INTEGER DEFAULT 2 CHECK (storage_tier IN (1, 2, 3)), -- 1=hot, 2=warm, 3=cold
    last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_frequency DECIMAL(8,2) DEFAULT 0,

    -- Constraints
    UNIQUE(name, version, organization),
    CHECK (quality_score IS NOT NULL OR status = 'draft')
);

-- =============================================================================
-- TEMPLATE VERSIONS & HISTORY
-- =============================================================================

CREATE TABLE template_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changes_summary TEXT,
    quality_metrics JSONB,
    file_size_bytes INTEGER,
    lines_of_code INTEGER,

    -- Version comparison data
    diff_summary TEXT,
    breaking_changes BOOLEAN DEFAULT FALSE,
    migration_guide TEXT,

    UNIQUE(template_id, version)
);

-- =============================================================================
-- USAGE ANALYTICS & TRACKING
-- =============================================================================

CREATE TABLE template_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    project_type VARCHAR(100),
    success BOOLEAN,
    feedback_score INTEGER CHECK (feedback_score >= 1 AND feedback_score <= 5),
    modifications_made TEXT,

    -- Context information
    user_id VARCHAR(100),
    organization VARCHAR(100),
    development_stage VARCHAR(50), -- prototype, development, staging, production
    team_size INTEGER,
    project_complexity VARCHAR(20),

    -- Performance metrics
    generation_time_ms INTEGER,
    compilation_success BOOLEAN,
    runtime_errors INTEGER DEFAULT 0,

    -- Usage outcome
    template_modified BOOLEAN DEFAULT FALSE,
    modification_type VARCHAR(50), -- configuration, logic, structure, styling
    satisfaction_score INTEGER CHECK (satisfaction_score >= 1 AND satisfaction_score <= 10)
);

-- =============================================================================
-- TEMPLATE RELATIONSHIPS & DEPENDENCIES
-- =============================================================================

CREATE TABLE template_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    child_template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    dependency_type VARCHAR(50) NOT NULL, -- requires, extends, implements, imports
    is_optional BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(parent_template_id, child_template_id, dependency_type)
);

CREATE TABLE template_similarities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_a_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    template_b_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    similarity_score DECIMAL(5,4) CHECK (similarity_score >= 0 AND similarity_score <= 1),
    similarity_type VARCHAR(50) NOT NULL, -- semantic, syntactic, structural, functional
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(template_a_id, template_b_id, similarity_type),
    CHECK (template_a_id != template_b_id)
);

-- =============================================================================
-- QUALITY ANALYSIS & METRICS
-- =============================================================================

CREATE TABLE template_quality_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    analyzer_version VARCHAR(20) NOT NULL,

    -- Static analysis results
    pylint_score DECIMAL(4,2),
    eslint_errors INTEGER DEFAULT 0,
    eslint_warnings INTEGER DEFAULT 0,
    security_issues INTEGER DEFAULT 0,
    vulnerability_count INTEGER DEFAULT 0,

    -- Code metrics
    cyclomatic_complexity DECIMAL(6,2),
    lines_of_code INTEGER,
    comment_coverage DECIMAL(5,2),
    duplicate_code_percentage DECIMAL(5,2),

    -- Analysis results
    issues_found JSONB, -- Detailed issues in JSON format
    recommendations JSONB, -- AI-generated improvement suggestions
    compliance_score DECIMAL(5,2),

    -- Performance indicators
    estimated_runtime_performance VARCHAR(20),
    memory_efficiency_score INTEGER CHECK (memory_efficiency_score >= 0 AND memory_efficiency_score <= 100),
    scalability_rating VARCHAR(20)
);

-- =============================================================================
-- SEARCH & DISCOVERY
-- =============================================================================

CREATE TABLE template_search_index (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    search_vector TSVECTOR,
    keywords TEXT[],
    concepts TEXT[],

    -- Full-text search fields
    searchable_content TEXT,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Semantic search integration
    embedding_model VARCHAR(100),
    embedding_dimension INTEGER,
    last_embedded_at TIMESTAMP
);

-- =============================================================================
-- ENTERPRISE GOVERNANCE
-- =============================================================================

CREATE TABLE template_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    reviewer_id VARCHAR(100) NOT NULL,
    review_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approval_status VARCHAR(20) NOT NULL CHECK (approval_status IN ('pending', 'approved', 'rejected', 'revision_required')),
    comments TEXT,
    checklist_items JSONB, -- Review checklist results

    -- Review criteria
    code_quality_approved BOOLEAN DEFAULT FALSE,
    security_approved BOOLEAN DEFAULT FALSE,
    documentation_approved BOOLEAN DEFAULT FALSE,
    testing_approved BOOLEAN DEFAULT FALSE,
    compliance_approved BOOLEAN DEFAULT FALSE
);

CREATE TABLE template_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id UUID NOT NULL REFERENCES templates(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL, -- create, update, delete, approve, deprecate, access
    actor_id VARCHAR(100) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details JSONB,
    ip_address INET,
    user_agent TEXT,

    -- Change tracking
    field_changes JSONB, -- What fields were modified
    old_values JSONB,
    new_values JSONB
);

-- =============================================================================
-- PERFORMANCE OPTIMIZATION
-- =============================================================================

-- Indexes for performance
CREATE INDEX idx_templates_category ON templates(category);
CREATE INDEX idx_templates_language ON templates(language);
CREATE INDEX idx_templates_framework ON templates(framework);
CREATE INDEX idx_templates_quality_score ON templates(quality_score DESC);
CREATE INDEX idx_templates_popularity ON templates(popularity, usage_count DESC);
CREATE INDEX idx_templates_status ON templates(status);
CREATE INDEX idx_templates_organization ON templates(organization);
CREATE INDEX idx_templates_storage_tier ON templates(storage_tier, last_accessed_at DESC);
CREATE INDEX idx_templates_tags ON templates USING GIN(tags);

CREATE INDEX idx_template_usage_template_id ON template_usage(template_id);
CREATE INDEX idx_template_usage_used_at ON template_usage(used_at DESC);
CREATE INDEX idx_template_usage_success ON template_usage(success, satisfaction_score DESC);

CREATE INDEX idx_template_search_vector ON template_search_index USING GIN(search_vector);
CREATE INDEX idx_template_search_keywords ON template_search_index USING GIN(keywords);

-- =============================================================================
-- TRIGGERS FOR AUTOMATION
-- =============================================================================

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_templates_updated_at BEFORE UPDATE ON templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Auto-update access tracking
CREATE OR REPLACE FUNCTION update_template_access()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE templates
    SET last_accessed_at = CURRENT_TIMESTAMP,
        access_frequency = access_frequency + 1
    WHERE id = NEW.template_id;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER track_template_access AFTER INSERT ON template_usage
    FOR EACH ROW EXECUTE FUNCTION update_template_access();

-- =============================================================================
-- INITIAL DATA & CONFIGURATION
-- =============================================================================

-- Insert default categories
INSERT INTO templates (name, category, language, description, file_path, created_by, status) VALUES
('Sample Template', 'system', 'sql', 'Initial system template for schema validation', '/system/schema.sql', 'system', 'approved');

COMMENT ON TABLE templates IS 'Core template metadata with enterprise-grade classification and quality tracking';
COMMENT ON TABLE template_versions IS 'Complete version history with change tracking and quality metrics';
COMMENT ON TABLE template_usage IS 'Detailed usage analytics for optimization and recommendation engine';
COMMENT ON TABLE template_quality_analysis IS 'Automated quality analysis results from multiple tools';
COMMENT ON TABLE template_audit_log IS 'Complete audit trail for security and compliance';
