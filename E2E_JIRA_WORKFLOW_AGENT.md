# End-to-End Development & QA Agent - JIRA Integration

## Overview

This agent implements a complete end-to-end development and quality assurance workflow integrated with JIRA. It automates the entire software development lifecycle from epic selection through testing and deployment validation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  E2E Development & QA Agent                     │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   JIRA API            Quality-Fabric        Local Repository
  (via Maestro)           (Port 8000)       (Code Implementation)
localhost:3100
```

## Workflow Phases

### 1. JIRA Initialization
**Purpose**: Fetch and activate relevant work items

**Actions**:
- Fetch 'To Do' or 'In Progress' Epics via: `GET /api/integrations/tasks?types=epic&statusCategories=todo`
- Display available epics with metadata (priority, labels, status)
- Select epic based on priority or user preference
- Transition epic to 'In Progress' if in 'To Do' state
- Fetch all subtasks/stories under the epic

**API Endpoints Used**:
```bash
# List Epics
GET /api/integrations/tasks?types=epic&statusCategories=todo,in_progress&pageSize=10
Authorization: Bearer <JWT_TOKEN>

# Transition Epic
POST /api/integrations/tasks/{epic_id}/transition
{
  "targetStatus": "In Progress",
  "comment": "E2E Development & QA Agent started working on this epic"
}

# List Tasks for Epic
GET /api/integrations/tasks?epicIds={epic_id}&pageSize=20
```

### 2. Strategy Generation
**Purpose**: Create development plan and comprehensive test cases

**Outputs**:
- **Development Strategy Document** (`/tmp/e2e_strategy_{epic_id}.md`)
  - Epic overview and current status
  - Development plan with phases
  - Testing strategy
  - Success criteria
  
- **Test Cases Document** (`/tmp/e2e_test_cases_{epic_id}.json`)
  - Comprehensive test case definitions
  - Integration test specifications
  - Expected outcomes and validation rules
  - Execution status tracking

**Test Case Structure**:
```json
{
  "id": "TC-001",
  "title": "Test Case Title",
  "type": "integration",
  "priority": "high|medium|low",
  "description": "Detailed description",
  "endpoint": "/api/endpoint",
  "method": "GET|POST|PUT|DELETE",
  "expected_status": 200,
  "status": "pending|passed|failed",
  "execution_time_ms": null,
  "error": null
}
```

### 3. Implementation
**Purpose**: Execute code development and fixes

**Current Capability**:
- Placeholder for actual code development
- In production: Would implement features, fix bugs, write tests

**Future Enhancements**:
- Automated code generation
- Dependency analysis
- Unit test generation
- Code review automation

### 4. Validation
**Purpose**: Execute tests against quality-fabric API

**Test Categories**:
1. **Health Checks**: Verify API availability and responsiveness
2. **Integration Tests**: Validate JIRA integration endpoints
3. **Epic Operations**: Test epic retrieval and task listing
4. **Transition Tests**: Verify status transitions

**Validation Targets**:
- Quality-Fabric API: `http://localhost:8000`
- Maestro Integration API: `http://localhost:3100/api`

**Test Execution Flow**:
```bash
for each test_case in test_cases:
  1. Record start time
  2. Execute API call
  3. Capture HTTP status and response
  4. Record end time and duration
  5. Validate against expected outcome
  6. Update test case status (passed/failed)
  7. Log execution details
```

### 5. Reporting
**Purpose**: Update JIRA tasks with execution details

**Reporting Metrics**:
- Total tests executed
- Pass/fail counts
- Pass rate percentage
- Execution time per test
- Detailed error logs for failures

**JIRA Updates**:
- Add comments to tasks with test results
- Update task status based on test outcomes
- Transition successful tasks to 'Done'
- Flag failed tasks for review

**Report Format**:
```
E2E Test Execution Results:

✅ Passed: 3/4
❌ Failed: 1/4
Pass Rate: 75.00%

Execution Time: 2025-11-27 21:22:18 UTC

Test Details:
- [TC-001] Verify API Health Check: passed (14ms)
- [TC-002] JIRA Epic Retrieval: passed (464ms)
- [TC-003] JIRA Task List for Epic: passed (223ms)
- [TC-004] Epic Status Transition: pending (null)
```

### 6. Closure
**Purpose**: Complete epic when all criteria met

**Completion Criteria**:
- All subtasks marked as 'Done'
- All tests passed (100% pass rate)
- Code review approved (if applicable)

**Actions**:
- Check subtask completion status
- Verify test results
- If all criteria met:
  - Transition epic to 'Done'
  - Add completion comment with summary
- If criteria not met:
  - Report blockers
  - Keep epic as 'In Progress'

## Configuration

### Environment Variables
```bash
# JWT Authentication Token
JWT_TOKEN="<your_jwt_token>"

# API Base URLs
API_BASE="http://localhost:3100/api"
QF_API_BASE="http://localhost:8000"
```

### Authentication

The agent uses JWT-based authentication. Generate a token with:

```javascript
const jwt = require('jsonwebtoken');
const token = jwt.sign(
  { 
    sub: '<user_id>',
    email: '<user_email>',
    role: 'admin'
  },
  '<JWT_SECRET>',
  { expiresIn: '24h' }
);
```

**Required JWT Claims**:
- `sub`: User ID (must exist in database)
- `email`: User email
- `role`: User role (admin, developer, etc.)

## Usage

### Quick Start

```bash
# Make script executable
chmod +x e2e_jira_workflow.sh

# Run the workflow
./e2e_jira_workflow.sh
```

### Command-Line Execution

```bash
# Fetch available epics
curl -X GET "http://localhost:3100/api/integrations/tasks?types=epic&statusCategories=todo&pageSize=10" \
  -H "Authorization: Bearer $JWT_TOKEN"

# Select and work on specific epic
export EPIC_ID="MD-1842"
./e2e_jira_workflow.sh
```

### Integration with CI/CD

```yaml
# GitHub Actions Example
name: E2E Development Workflow

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  e2e-workflow:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run E2E JIRA Workflow
        env:
          JWT_TOKEN: ${{ secrets.JWT_TOKEN }}
        run: ./e2e_jira_workflow.sh
      
      - name: Upload Test Results
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: /tmp/e2e_test_cases_*.json
```

## API Reference

### JIRA Integration Endpoints

Based on: `~/projects/maestro-frontend-production/docs/api/jira-integration-api.md`

#### List Work Items
```http
GET /api/integrations/tasks
Query Parameters:
  - types: epic,story,task,bug
  - statusCategories: todo,in_progress,done
  - pageSize: 1-100
  - epicIds: filter by parent epic
```

#### Get Work Item
```http
GET /api/integrations/tasks/{id}
Returns: Full work item details with metadata
```

#### Transition Work Item
```http
POST /api/integrations/tasks/{id}/transition
Body:
{
  "targetStatus": "In Progress|Done",
  "comment": "Optional comment",
  "resolution": "Fixed|Won't Fix|Duplicate"
}
```

#### Search with JQL
```http
POST /api/integrations/tasks/search
Body:
{
  "jql": "project = MD AND status = 'To Do'",
  "startAt": 0,
  "maxResults": 25
}
```

## Output Artifacts

### 1. Development Strategy
**Location**: `/tmp/e2e_strategy_{epic_id}.md`

**Contents**:
- Epic overview and metadata
- Current status summary
- Detailed development plan
- Testing strategy
- Success criteria

### 2. Test Results
**Location**: `/tmp/e2e_test_cases_{epic_id}.json`

**Contents**:
- Test case definitions
- Execution results
- Performance metrics
- Error logs (if any)

**Example**:
```json
{
  "epic_id": "MD-1842",
  "epic_title": "[QF-800] Deployment Verification Gates & Rollback",
  "generated_at": "2025-11-27T21:22:18Z",
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Verify API Health Check",
      "status": "passed",
      "execution_time_ms": 14,
      "http_code": 200
    }
  ]
}
```

## Example Execution

### Sample Output

```
╔════════════════════════════════════════════════════════════════╗
║     E2E Development & QA Workflow - JIRA Integration           ║
╚════════════════════════════════════════════════════════════════╝

📋 STEP 1: JIRA INITIALIZATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Fetching 'To Do' Epics from JIRA...
✅ Found 10 Epics

Available Epics:
  📌 [MD-1842] [QF-800] Deployment Verification Gates & Rollback
     Status: In Progress | Priority: medium | Labels: deployment, p2

🎯 Selected Epic: [MD-1842] [QF-800] Deployment Verification Gates & Rollback
   Current Status: In Progress

🧠 STEP 2: STRATEGY GENERATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Development strategy created: /tmp/e2e_strategy_MD-1842.md
✅ Test cases generated: /tmp/e2e_test_cases_MD-1842.json

🧪 STEP 4: VALIDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Running TC-001: API Health Check...
  ✅ PASSED (14ms) - API is healthy
Running TC-002: JIRA Epic Retrieval...
  ✅ PASSED (464ms) - Epic retrieved successfully

📊 STEP 5: REPORTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Test Execution Summary:
  Total Tests: 3
  Passed: ✅ 3
  Failed: ❌ 0
  Pass Rate: 100.00%

╔════════════════════════════════════════════════════════════════╗
║                    WORKFLOW COMPLETED                          ║
╚════════════════════════════════════════════════════════════════╝
```

## Error Handling

### Common Errors

1. **Authentication Failed**
   ```
   Error: Authentication service unavailable
   Solution: Verify JWT token and user exists in database
   ```

2. **Epic Not Found**
   ```
   Error: No 'To Do' Epics found
   Solution: Check JIRA project and epic filters
   ```

3. **API Unreachable**
   ```
   Error: Connection refused to localhost:3100
   Solution: Start Maestro backend service
   ```

4. **Test Failures**
   ```
   Action: Review test_cases JSON for error details
   Action: Fix issues and re-run validation
   ```

## Monitoring & Observability

### Metrics Tracked
- Epic selection time
- Test execution duration
- API response times
- Pass/fail rates
- Epic completion time

### Logging
- All API calls logged with timestamps
- Test results captured in JSON format
- Strategy documents for audit trail

## Best Practices

1. **Epic Selection**
   - Prioritize high-priority epics
   - Check for blockers before starting
   - Review acceptance criteria

2. **Test Design**
   - Comprehensive coverage
   - Clear expected outcomes
   - Appropriate timeouts

3. **Reporting**
   - Detailed test results
   - Clear error messages
   - Actionable next steps

4. **Closure**
   - Verify all criteria met
   - Update JIRA with summary
   - Clean up temporary artifacts

## Troubleshooting

### Issue: JWT Token Expired
**Solution**:
```bash
# Generate new token
cd /home/ec2-user/projects/maestro-frontend-production/backend
node -e "
const jwt = require('jsonwebtoken');
const token = jwt.sign(
  { sub: '2ZPhoXxter4L9sjFQbqLv', email: 'test@maestro.ai', role: 'admin' },
  'maestro-production-secret-change-in-production-2024',
  { expiresIn: '24h' }
);
console.log(token);
"
```

### Issue: Services Not Running
**Solution**:
```bash
# Check services
curl http://localhost:3100/api/health  # Maestro API
curl http://localhost:8000/health      # Quality-Fabric

# Start if needed
cd /home/ec2-user/projects/maestro-frontend-production/backend
npm run dev
```

### Issue: No Epics Found
**Solution**:
```bash
# Check with different status
curl -X GET "http://localhost:3100/api/integrations/tasks?types=epic&statusCategories=in_progress" \
  -H "Authorization: Bearer $JWT_TOKEN"

# Or use JQL search
curl -X POST "http://localhost:3100/api/integrations/tasks/search" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"jql": "project = MD AND type = Epic"}'
```

## Future Enhancements

### Planned Features
1. **AI-Powered Code Generation**
   - Automatic implementation from acceptance criteria
   - Smart bug fixing suggestions

2. **Advanced Test Generation**
   - Property-based testing
   - Fuzzing and security tests
   - Performance benchmarks

3. **Multi-Project Support**
   - Work across multiple JIRA projects
   - Dependency tracking between epics

4. **Real-Time Dashboards**
   - Live test execution monitoring
   - Epic completion predictions
   - Team velocity metrics

5. **Integration Expansion**
   - GitHub Issues support
   - Linear integration
   - Slack notifications

## Contributing

To extend this workflow:

1. **Add New Test Cases**: Edit test case generation in STEP 2
2. **Custom Validation**: Add test execution logic in STEP 4
3. **Enhanced Reporting**: Modify STEP 5 for additional metrics
4. **New Integrations**: Add API calls in respective steps

## Support

- **Documentation**: This file and JIRA API reference
- **API Reference**: `~/projects/maestro-frontend-production/docs/api/jira-integration-api.md`
- **Test Examples**: `/tmp/e2e_test_cases_*.json`
- **Strategy Templates**: `/tmp/e2e_strategy_*.md`

## Version History

- **v1.0.0** (2025-11-27): Initial implementation
  - Complete 6-phase workflow
  - JIRA integration
  - Quality-fabric API validation
  - Comprehensive reporting

---

**Author**: E2E Development & QA Agent  
**Last Updated**: 2025-11-27  
**License**: Proprietary - Fifth9 Inc.
