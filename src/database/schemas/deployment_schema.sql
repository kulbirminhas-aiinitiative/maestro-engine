-- ============================================================================
-- Deployment Management Schema
-- Epic: MD-1790 [Platform] Unified Deployment Management GUI
-- ============================================================================
--
-- This schema supports the deployment management dashboard with:
-- - Multi-environment tracking (Beta, Demo, Production)
-- - Deployment history with full audit trail
-- - GitHub Actions integration for CI/CD
-- - Health monitoring with trending data
-- - Rollback capability
--
-- ============================================================================

-- Enable UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- ENVIRONMENTS TABLE
-- Tracks deployment target environments
-- ============================================================================
CREATE TABLE IF NOT EXISTS deployment_environments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) UNIQUE NOT NULL,           -- beta, demo, production
    display_name VARCHAR(100) NOT NULL,         -- "Beta Environment", "Production"
    description TEXT,

    -- GitHub Actions integration
    github_environment VARCHAR(50),              -- GitHub environment name
    github_workflow_id VARCHAR(100),             -- deploy.yml or custom workflow
    github_repository VARCHAR(200),              -- owner/repo

    -- Portainer integration (Phase 1)
    portainer_endpoint_id INTEGER,               -- Portainer endpoint ID
    portainer_stack_name VARCHAR(100),           -- Docker stack name

    -- Health monitoring
    health_url VARCHAR(255),                     -- Health check endpoint
    health_check_interval INTEGER DEFAULT 30,    -- Seconds between checks

    -- Environment configuration
    is_active BOOLEAN DEFAULT true,
    is_production BOOLEAN DEFAULT false,         -- Extra safeguards for prod
    requires_approval BOOLEAN DEFAULT false,     -- Manual approval required

    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for active environments
CREATE INDEX IF NOT EXISTS idx_deploy_env_active ON deployment_environments(is_active);

-- ============================================================================
-- DEPLOYMENTS TABLE
-- Deployment history and tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    environment_id UUID NOT NULL REFERENCES deployment_environments(id),

    -- Version information
    version VARCHAR(50) NOT NULL,                -- Semantic version or tag
    git_sha VARCHAR(40),                         -- Full git commit SHA
    git_branch VARCHAR(100),                     -- Branch name
    git_tag VARCHAR(100),                        -- Git tag if applicable

    -- Deployment status
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    -- Status values: pending, queued, in_progress, success, failed,
    --                cancelled, rolled_back, rollback_failed

    -- GitHub Actions tracking
    github_run_id BIGINT,                        -- GitHub Actions run ID
    github_run_url VARCHAR(500),                 -- URL to GitHub Actions run
    github_run_number INTEGER,                   -- Run number for display

    -- Trigger information
    triggered_by VARCHAR(100) NOT NULL,          -- Username or 'system'
    trigger_type VARCHAR(30) DEFAULT 'manual',   -- manual, automatic, rollback

    -- Timing
    queued_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Rollback tracking
    rollback_of UUID REFERENCES deployments(id), -- If this is a rollback, what deployment?
    is_rollback BOOLEAN DEFAULT false,

    -- Additional data
    notes TEXT,                                  -- Deployment notes/description
    metadata JSONB DEFAULT '{}',                 -- Additional metadata
    error_message TEXT,                          -- Error details if failed

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_deployments_env ON deployments(environment_id);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_deployments_env_status ON deployments(environment_id, status);
CREATE INDEX IF NOT EXISTS idx_deployments_started ON deployments(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_deployments_github_run ON deployments(github_run_id);

-- ============================================================================
-- DEPLOYMENT LOGS TABLE
-- Detailed logs for each deployment
-- ============================================================================
CREATE TABLE IF NOT EXISTS deployment_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID NOT NULL REFERENCES deployments(id) ON DELETE CASCADE,

    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    level VARCHAR(20) NOT NULL DEFAULT 'info',   -- debug, info, warning, error
    stage VARCHAR(50),                           -- build, test, deploy, verify
    message TEXT NOT NULL,

    -- Source information
    source VARCHAR(50),                          -- github, portainer, health-monitor

    -- Additional context
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient log retrieval
CREATE INDEX IF NOT EXISTS idx_deploy_logs_deployment ON deployment_logs(deployment_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_deploy_logs_level ON deployment_logs(deployment_id, level);

-- ============================================================================
-- HEALTH SNAPSHOTS TABLE
-- Historical health status for trending and analysis
-- ============================================================================
CREATE TABLE IF NOT EXISTS deployment_health_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    environment_id UUID NOT NULL REFERENCES deployment_environments(id),

    -- Health status
    status VARCHAR(20) NOT NULL,                 -- healthy, degraded, unhealthy, unknown

    -- Response metrics
    response_time_ms INTEGER,                    -- Response time in milliseconds
    status_code INTEGER,                         -- HTTP status code

    -- Details
    details JSONB DEFAULT '{}',                  -- Detailed health info from endpoint
    error_message TEXT,                          -- Error if unhealthy

    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for efficient health history queries
CREATE INDEX IF NOT EXISTS idx_health_env ON deployment_health_snapshots(environment_id, recorded_at DESC);

-- Partition hint: Consider partitioning by month for large deployments
-- CREATE INDEX IF NOT EXISTS idx_health_recorded ON deployment_health_snapshots(recorded_at);

-- ============================================================================
-- VERSIONS TABLE
-- Available versions for deployment
-- ============================================================================
CREATE TABLE IF NOT EXISTS deployment_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Version identification
    version VARCHAR(50) UNIQUE NOT NULL,         -- Semantic version
    git_sha VARCHAR(40),                         -- Full git commit SHA
    git_tag VARCHAR(100),                        -- Git tag
    git_branch VARCHAR(100),                     -- Source branch

    -- Build information
    build_number INTEGER,
    build_url VARCHAR(500),
    build_status VARCHAR(30),                    -- success, failed
    built_at TIMESTAMP WITH TIME ZONE,

    -- Release information
    release_notes TEXT,
    is_prerelease BOOLEAN DEFAULT false,
    is_latest BOOLEAN DEFAULT false,

    -- Deployment tracking
    deployed_environments JSONB DEFAULT '[]',    -- Array of environment names

    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for version lookups
CREATE INDEX IF NOT EXISTS idx_versions_git_sha ON deployment_versions(git_sha);
CREATE INDEX IF NOT EXISTS idx_versions_latest ON deployment_versions(is_latest);

-- ============================================================================
-- APPROVAL RECORDS TABLE
-- Manual approval tracking for production deployments
-- ============================================================================
CREATE TABLE IF NOT EXISTS deployment_approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID NOT NULL REFERENCES deployments(id),

    -- Approval status
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, approved, rejected

    -- Approver information
    requested_by VARCHAR(100) NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    approved_by VARCHAR(100),
    approved_at TIMESTAMP WITH TIME ZONE,

    -- Notes
    request_notes TEXT,
    approval_notes TEXT,
    rejection_reason TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for approval lookups
CREATE INDEX IF NOT EXISTS idx_approvals_deployment ON deployment_approvals(deployment_id);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON deployment_approvals(status);

-- ============================================================================
-- VIEWS
-- Convenient views for common queries
-- ============================================================================

-- Current deployment status per environment
CREATE OR REPLACE VIEW current_deployments AS
SELECT DISTINCT ON (e.id)
    e.id AS environment_id,
    e.name AS environment_name,
    e.display_name,
    d.id AS deployment_id,
    d.version,
    d.git_sha,
    d.status AS deployment_status,
    d.completed_at AS deployed_at,
    d.triggered_by
FROM deployment_environments e
LEFT JOIN deployments d ON d.environment_id = e.id
    AND d.status = 'success'
WHERE e.is_active = true
ORDER BY e.id, d.completed_at DESC;

-- Latest health status per environment
CREATE OR REPLACE VIEW current_health_status AS
SELECT DISTINCT ON (e.id)
    e.id AS environment_id,
    e.name AS environment_name,
    e.display_name,
    h.status AS health_status,
    h.response_time_ms,
    h.recorded_at AS last_check,
    h.details
FROM deployment_environments e
LEFT JOIN deployment_health_snapshots h ON h.environment_id = e.id
WHERE e.is_active = true
ORDER BY e.id, h.recorded_at DESC;

-- ============================================================================
-- INITIAL DATA
-- Seed default environments
-- ============================================================================
INSERT INTO deployment_environments (name, display_name, description, is_production, requires_approval)
VALUES
    ('beta', 'Beta Environment', 'Development and testing environment', false, false),
    ('demo', 'Demo Environment', 'Staging and demo environment', false, false),
    ('production', 'Production', 'Live production environment', true, true)
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- FUNCTIONS
-- Utility functions for deployment management
-- ============================================================================

-- Function to get deployment duration
CREATE OR REPLACE FUNCTION get_deployment_duration(p_deployment_id UUID)
RETURNS INTERVAL AS $$
BEGIN
    RETURN (
        SELECT COALESCE(completed_at, NOW()) - COALESCE(started_at, created_at)
        FROM deployments
        WHERE id = p_deployment_id
    );
END;
$$ LANGUAGE plpgsql;

-- Function to get latest successful deployment for an environment
CREATE OR REPLACE FUNCTION get_latest_deployment(p_environment_id UUID)
RETURNS TABLE(
    deployment_id UUID,
    version VARCHAR(50),
    git_sha VARCHAR(40),
    completed_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT d.id, d.version, d.git_sha, d.completed_at
    FROM deployments d
    WHERE d.environment_id = p_environment_id
    AND d.status = 'success'
    ORDER BY d.completed_at DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update environment's updated_at timestamp
CREATE OR REPLACE FUNCTION update_environment_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_environment_timestamp
BEFORE UPDATE ON deployment_environments
FOR EACH ROW
EXECUTE FUNCTION update_environment_timestamp();

-- ============================================================================
-- CLEANUP FUNCTION
-- Retain only recent health snapshots (configurable retention)
-- ============================================================================
CREATE OR REPLACE FUNCTION cleanup_old_health_snapshots(retention_days INTEGER DEFAULT 7)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM deployment_health_snapshots
    WHERE recorded_at < NOW() - (retention_days || ' days')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMMENTS
-- Table and column documentation
-- ============================================================================
COMMENT ON TABLE deployment_environments IS 'Deployment target environments (beta, demo, production)';
COMMENT ON TABLE deployments IS 'Deployment history and tracking';
COMMENT ON TABLE deployment_logs IS 'Detailed logs for each deployment';
COMMENT ON TABLE deployment_health_snapshots IS 'Historical health status for trending';
COMMENT ON TABLE deployment_versions IS 'Available versions for deployment';
COMMENT ON TABLE deployment_approvals IS 'Manual approval tracking for production deployments';
