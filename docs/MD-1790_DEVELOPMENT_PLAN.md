# MD-1790: Unified Deployment Management GUI - Development Plan

## Epic Overview
- **Epic ID**: MD-1790
- **Title**: [Platform] Unified Deployment Management GUI
- **Status**: In Progress
- **Priority**: High

## Current State Analysis

### Already Implemented (95% Backend Complete)
| Component | Status | File |
|-----------|--------|------|
| Deployment Service | ✅ Done | `src/services/deployment_service.py` |
| Deployment Management Service | ✅ Done | `src/services/deployment_management_service.py` |
| Deployment Health Monitor | ✅ Done | `src/services/deployment_health_monitor.py` |
| Post-Deployment Verification | ✅ Done | `src/services/post_deployment_verification_service.py` |
| REST API Routes | ✅ Done | `src/api/deployment_routes.py` |
| Database Schema | ✅ Done | `src/database/schemas/deployment_schema.sql` |
| Configuration | ✅ Done | `config/deployment_config.yaml` |

### Critical Missing Components
1. **GitHub Actions Client** - Required for actual deployments
2. **Database Integration** - Services use in-memory storage
3. **WebSocket Events** - Real-time updates not functional

---

## Implementation Phases

### Phase 1: GitHub Actions Client (HIGH PRIORITY)

**File**: `src/clients/github_actions_client.py`

This is the **blocking dependency** - without it, no deployments can be triggered.

Features:
- Trigger GitHub Actions workflow
- Poll workflow status
- Get workflow logs
- Handle authentication

### Phase 2: Database Integration

**File**: Update existing services to use PostgreSQL

- Create SQLAlchemy models
- Replace in-memory storage
- Implement migrations

### Phase 3: WebSocket Events (MEDIUM PRIORITY)

**File**: `src/websocket/deployment_events.py`

- Real-time deployment status updates
- Health status broadcasts
- Event subscription management

---

## Test Cases

### TC-1790-01: GitHub Actions Client Tests
| ID | Test Case | Expected Result |
|----|-----------|-----------------|
| TC-01.1 | Trigger workflow successfully | Returns workflow run ID |
| TC-01.2 | Handle invalid token | Returns authentication error |
| TC-01.3 | Poll workflow status | Returns running/completed status |
| TC-01.4 | Get workflow logs | Returns log content |

### TC-1790-02: API Integration Tests
| ID | Test Case | Expected Result |
|----|-----------|-----------------|
| TC-02.1 | GET /environments returns all envs | List of Beta, Demo, Prod |
| TC-02.2 | POST /deploy triggers workflow | Returns deployment ID |
| TC-02.3 | GET /health returns status | Health status per env |
| TC-02.4 | POST /rollback triggers rollback | Rollback initiated |

---

## Acceptance Criteria Mapping

| AC | Requirement | Implementation |
|----|-------------|----------------|
| AC-1 | Single dashboard for all environments | ✅ Backend done, needs frontend |
| AC-2 | Current deployed version per environment | ✅ `EnvironmentStatus.current_version` |
| AC-3 | Health status per environment | ✅ `DeploymentHealthMonitor` |
| AC-4 | One-click deploy from versions | ⚠️ Needs GitHub Actions client |
| AC-5 | Deployment history with status | ✅ Full history API |
| AC-6 | Basic rollback capability | ✅ Rollback endpoint |

---

## Implementation Order

1. **Create GitHub Actions Client** - Unblocks deployment functionality
2. **Add comprehensive tests** - Ensure reliability
3. **Integrate with existing services** - Wire up the client
4. **Validate with quality-fabric** - Run all tests

---

## Success Criteria

- [ ] GitHub Actions client successfully triggers workflows
- [ ] Deployment API endpoints functional end-to-end
- [ ] All unit tests pass
- [ ] Quality Fabric validation passes
