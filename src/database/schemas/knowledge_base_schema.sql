-- ============================================================================
-- MAESTRO Knowledge Base Schema
-- Stores technical components, workflow templates, and DAG generation data
-- ============================================================================

-- Technical Components Table
-- Stores reusable technical components for DAG generation
CREATE TABLE IF NOT EXISTS technical_components (
    component_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    complexity VARCHAR(20) NOT NULL CHECK (complexity IN ('low', 'medium', 'high')),
    estimated_duration VARCHAR(50),
    typical_phases JSONB NOT NULL DEFAULT '[]',
    tech_options JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_component_name UNIQUE (name)
);

-- Component Dependencies Table
-- Tracks dependencies between technical components
CREATE TABLE IF NOT EXISTS component_dependencies (
    id SERIAL PRIMARY KEY,
    component_id VARCHAR(50) NOT NULL REFERENCES technical_components(component_id) ON DELETE CASCADE,
    depends_on_component_id VARCHAR(50) NOT NULL REFERENCES technical_components(component_id) ON DELETE CASCADE,
    dependency_type VARCHAR(20) DEFAULT 'requires' CHECK (dependency_type IN ('requires', 'recommends', 'conflicts')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_dependency UNIQUE (component_id, depends_on_component_id)
);

-- Workflow Templates Table
-- Stores predefined workflow templates
CREATE TABLE IF NOT EXISTS workflow_templates (
    template_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    complexity VARCHAR(20) NOT NULL CHECK (complexity IN ('simple', 'medium', 'complex', 'enterprise')),
    typical_duration VARCHAR(50),
    required_phases JSONB NOT NULL DEFAULT '[]',
    parallel_opportunities JSONB NOT NULL DEFAULT '[]',
    use_cases JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_template_name UNIQUE (name)
);

-- Template Components Junction Table
-- Maps which components are typically used in each template
CREATE TABLE IF NOT EXISTS template_components (
    id SERIAL PRIMARY KEY,
    template_id VARCHAR(50) NOT NULL REFERENCES workflow_templates(template_id) ON DELETE CASCADE,
    component_id VARCHAR(50) NOT NULL REFERENCES technical_components(component_id) ON DELETE CASCADE,
    is_required BOOLEAN DEFAULT TRUE,
    execution_order INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_template_component UNIQUE (template_id, component_id)
);

-- Tech Stacks Table
-- Stores technology stack combinations
CREATE TABLE IF NOT EXISTS tech_stacks (
    stack_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    frontend_tech JSONB DEFAULT '[]',
    backend_tech JSONB DEFAULT '[]',
    database_tech JSONB DEFAULT '[]',
    deployment_tech JSONB DEFAULT '[]',
    use_case TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_stack_name UNIQUE (name)
);

-- Agent Persona Mappings Table
-- Maps knowledge base persona roles to actual AI agent persona IDs
CREATE TABLE IF NOT EXISTS agent_persona_mappings (
    mapping_id SERIAL PRIMARY KEY,
    knowledge_base_role VARCHAR(50) NOT NULL,
    agent_persona_id VARCHAR(50) NOT NULL,
    display_name VARCHAR(100),
    best_for JSONB DEFAULT '[]',
    skills JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_kb_role UNIQUE (knowledge_base_role)
);

-- Best Practices Table
-- Stores best practices and guidelines for DAG generation
CREATE TABLE IF NOT EXISTS best_practices (
    practice_id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    rule_name VARCHAR(100) NOT NULL,
    rule_description TEXT NOT NULL,
    rule_data JSONB NOT NULL DEFAULT '{}',
    priority INT DEFAULT 5 CHECK (priority BETWEEN 1 AND 10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_practice UNIQUE (category, rule_name)
);

-- Validation Rules Table
-- Stores DAG validation rules
CREATE TABLE IF NOT EXISTS validation_rules (
    rule_id SERIAL PRIMARY KEY,
    rule_name VARCHAR(100) NOT NULL UNIQUE,
    rule_description TEXT NOT NULL,
    rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN ('structure', 'content', 'dependency', 'complexity')),
    rule_config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    severity VARCHAR(20) DEFAULT 'error' CHECK (severity IN ('error', 'warning', 'info')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_component_complexity ON technical_components(complexity);
CREATE INDEX IF NOT EXISTS idx_template_complexity ON workflow_templates(complexity);
CREATE INDEX IF NOT EXISTS idx_component_dependencies ON component_dependencies(component_id, depends_on_component_id);
CREATE INDEX IF NOT EXISTS idx_template_components ON template_components(template_id, component_id);
CREATE INDEX IF NOT EXISTS idx_persona_mappings ON agent_persona_mappings(agent_persona_id);
CREATE INDEX IF NOT EXISTS idx_best_practices_category ON best_practices(category);
CREATE INDEX IF NOT EXISTS idx_validation_rules_active ON validation_rules(is_active);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_technical_components_updated_at BEFORE UPDATE ON technical_components
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workflow_templates_updated_at BEFORE UPDATE ON workflow_templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tech_stacks_updated_at BEFORE UPDATE ON tech_stacks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agent_persona_mappings_updated_at BEFORE UPDATE ON agent_persona_mappings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_best_practices_updated_at BEFORE UPDATE ON best_practices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_validation_rules_updated_at BEFORE UPDATE ON validation_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE technical_components IS 'Technical components available for DAG generation';
COMMENT ON TABLE component_dependencies IS 'Dependencies between technical components';
COMMENT ON TABLE workflow_templates IS 'Predefined workflow templates for common use cases';
COMMENT ON TABLE template_components IS 'Components typically used in each template';
COMMENT ON TABLE tech_stacks IS 'Technology stack combinations';
COMMENT ON TABLE agent_persona_mappings IS 'Maps knowledge base roles to AI agent personas';
COMMENT ON TABLE best_practices IS 'Best practices and guidelines for DAG generation';
COMMENT ON TABLE validation_rules IS 'DAG validation rules and configuration';
