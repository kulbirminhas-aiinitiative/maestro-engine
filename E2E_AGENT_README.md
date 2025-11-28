# End-to-End Development & QA Agent

## Overview

This agent automates the complete software development lifecycle with JIRA integration, from epic selection through testing and closure.

## Features

✅ **JIRA Integration** - Connects via Maestro Integration API  
✅ **Automated Workflow** - 6-step process from initialization to closure  
✅ **Test Execution** - Validates against quality-fabric API  
✅ **Intelligent Reporting** - Updates JIRA tasks based on test results  
✅ **Epic Closure** - Automatically closes epics when all tasks complete  

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              E2E Development & QA Agent                          │
└─────────────────────────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
  Maestro JIRA API      Quality-Fabric        Local Repository
  localhost:3100        localhost:8000       (Code Implementation)
```

## Workflow Steps

### 1. JIRA Initialization 📋
- Fetch 'To Do' Epics from JIRA
- Select relevant epic (automatic or specified)
- Transition epic to 'In Progress' if needed
- Load all subtasks/tasks under the epic

### 2. Strategy Generation 🧠
- Generate development plan document
- Create comprehensive test cases
- Define acceptance criteria
- Document in `/tmp/e2e_agent_output/`

### 3. Implementation 💻
- Execute code development/fixes
- Apply changes based on strategy
- *Note: Current version is placeholder - extend for actual implementation*

### 4. Validation 🧪
- Run tests against quality-fabric API (localhost:8000)
- Execute each test case
- Measure response times
- Capture pass/fail status and error logs

### 5. Reporting 📊
- Update test cases with execution results
- Add test report to epic as comment
- **IF tests passed**: Transition tasks to 'Done'
- **ELSE**: Leave tasks as-is (In Progress/To Do)

### 6. Closure 🎯
- Check if all tasks are 'Done'
- **IF all done**: Transition epic to 'Done'
- **ELSE**: Leave epic as 'In Progress'

## Prerequisites

### Services Required
1. **Maestro Backend** (port 3100)
   ```bash
   cd ~/projects/maestro-frontend-production/backend
   npm run dev
   ```

2. **Quality-Fabric API** (port 8000)
   ```bash
   # Start if needed
   ```

3. **JWT Token** (required for authentication)

### Generate JWT Token

```bash
cd ~/projects/maestro-frontend-production/backend
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

## Installation

```bash
# Clone or navigate to project
cd /home/ec2-user/projects/maestro-engine-new

# Install dependencies (if needed)
pip install httpx

# Verify files
ls -l e2e_dev_qa_agent.py run_e2e_agent.sh
```

## Usage

### Quick Start

```bash
# Set JWT token
export JWT_TOKEN='your_generated_jwt_token_here'

# Run agent (auto-selects first 'To Do' epic)
./run_e2e_agent.sh
```

### With Specific Epic

```bash
# Specify epic key
export JWT_TOKEN='your_jwt_token'
./run_e2e_agent.sh MD-1831
```

### Advanced Usage

```bash
# Set custom API URLs
export MAESTRO_API_URL='http://localhost:3100/api'
export QF_API_URL='http://localhost:8000'
export JWT_TOKEN='your_jwt_token'
export EPIC_KEY='MD-1831'  # Optional

# Run Python script directly
python3 e2e_dev_qa_agent.py
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_TOKEN` | *(required)* | Authentication token for Maestro API |
| `MAESTRO_API_URL` | `http://localhost:3100/api` | Maestro Integration API base URL |
| `QF_API_URL` | `http://localhost:8000` | Quality-Fabric API base URL |
| `EPIC_KEY` | *(optional)* | Specific epic to process (e.g., MD-1831) |

## Output Files

All output is saved to `/tmp/e2e_agent_output/`:

```
/tmp/e2e_agent_output/
├── strategy_{EPIC_KEY}.md              # Development strategy document
├── test_cases_{EPIC_KEY}.json          # Generated test cases (before)
└── test_cases_{EPIC_KEY}_results.json  # Test execution results (after)
```

### Example Output

**strategy_MD-1831.md**:
```markdown
# Development Strategy: MD-1831

## Epic Overview
- **Key**: MD-1831
- **Summary**: Template Versions & Recommendation APIs
- **Status**: In Progress
- **Priority**: high

## Development Plan
...
```

**test_cases_MD-1831_results.json**:
```json
{
  "id": "TC-001",
  "name": "Quality-Fabric API Health Check",
  "status": "passed",
  "execution_time_ms": 45.2,
  "error": null
}
```

## API Reference

### JIRA Integration (via Maestro)

Based on: `~/projects/maestro-frontend-production/docs/api/jira-integration-api.md`

#### List Epics
```bash
GET /api/integrations/tasks?types=epic&statusCategories=todo
Authorization: Bearer <JWT_TOKEN>
```

#### Get Task
```bash
GET /api/integrations/tasks/{task_id}
Authorization: Bearer <JWT_TOKEN>
```

#### Transition Task
```bash
POST /api/integrations/tasks/{task_id}/transition
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "targetStatus": "In Progress|Done",
  "comment": "Optional comment",
  "resolution": "Fixed"
}
```

#### List Tasks for Epic
```bash
GET /api/integrations/tasks?epicIds={epic_id}
Authorization: Bearer <JWT_TOKEN>
```

## Example Execution

```bash
$ ./run_e2e_agent.sh

╔════════════════════════════════════════════════════════════════╗
║     E2E Development & QA Agent with JIRA Integration           ║
╚════════════════════════════════════════════════════════════════╝

✅ Using JWT Token
ℹ️  Configuration:
  Maestro API: http://localhost:3100/api
  Quality-Fabric API: http://localhost:8000
  Output: /tmp/e2e_agent_output/

🚀 Starting E2E Development & QA Agent...

======================================================================
📋 STEP 1: JIRA INITIALIZATION
======================================================================

🏃 Fetching 'To Do' Epics from JIRA...
✅ Found 3 epic(s)

  1. [MD-1831] Template Versions & Recommendation APIs
     Status: To Do | Priority: high

✅ Selected: [MD-1831] Template Versions & Recommendation APIs
🏃 Transitioning MD-1831 to 'In Progress'...
✅ Epic transitioned to 'In Progress'
🏃 Fetching tasks for epic MD-1831...
✅ Loaded 5 task(s) under this epic

======================================================================
🧠 STEP 2: STRATEGY GENERATION
======================================================================

✅ Strategy document: /tmp/e2e_agent_output/strategy_MD-1831.md
✅ Generated 3 test cases: /tmp/e2e_agent_output/test_cases_MD-1831.json

======================================================================
💻 STEP 3: IMPLEMENTATION
======================================================================

ℹ️  Implementation phase - Placeholder for actual development
✅ Simulating successful implementation

======================================================================
🧪 STEP 4: VALIDATION
======================================================================

🏃 Running TC-001: Quality-Fabric API Health Check...
✅ TC-001 PASSED (45ms)
🏃 Running TC-002: Epic MD-1831 Retrieval...
✅ TC-002 PASSED (123ms)
🏃 Running TC-003: Tasks List for Epic MD-1831...
✅ TC-003 PASSED (89ms)

📊 Validation Summary: 3/3 passed, 0/3 failed

======================================================================
📊 STEP 5: REPORTING
======================================================================

✅ Test results saved: /tmp/e2e_agent_output/test_cases_MD-1831_results.json
🏃 Adding test report to epic MD-1831...
✅ Epic updated with test report
🏃 Updating task MD-1832...
✅ Task MD-1832 transitioned to 'Done'
🏃 Updating task MD-1833...
✅ Task MD-1833 transitioned to 'Done'

======================================================================
🎯 STEP 6: CLOSURE
======================================================================

ℹ️  Tasks completed: 5/5
🏃 All tasks completed! Transitioning epic MD-1831 to 'Done'...
✅ Epic MD-1831 transitioned to 'Done'

======================================================================
🎉 WORKFLOW COMPLETED
======================================================================

Epic: MD-1831 - Template Versions & Recommendation APIs
Status: Done
Tests: 3/3 passed (100.0%)
Duration: 12.3s

✅ Workflow completed successfully!

📁 Output files saved to: /tmp/e2e_agent_output/
```

## Error Handling

### Common Issues

**1. JWT Token Not Set**
```
❌ ERROR: JWT_TOKEN environment variable not set
```
Solution: Generate and export JWT token

**2. Maestro API Not Responding**
```
⚠️  WARNING: Maestro API not responding at http://localhost:3100
```
Solution: Start Maestro backend service

**3. No Epics Found**
```
ValueError: No epics found in 'To Do' or 'In Progress' status
```
Solution: Check JIRA for available epics or specify EPIC_KEY

**4. Task Transition Failed**
```
❌ Failed to update task MD-1832: Transition 'Done' not found
```
Solution: Check JIRA workflow for available transitions

## Extending the Agent

### Add Custom Test Cases

Edit `_generate_test_cases()` method in `e2e_dev_qa_agent.py`:

```python
def _generate_test_cases(self, epic: Epic) -> List[TestCase]:
    test_cases = [
        TestCase(
            id="TC-004",
            name="Custom Test",
            description="Your test description",
            endpoint="/api/custom/endpoint",
            method="POST",
            expected_status=201
        )
    ]
    return test_cases
```

### Implement Actual Code Development

Modify `step3_implementation()`:

```python
async def step3_implementation(self, epic: Epic) -> bool:
    # Add your implementation logic
    # - Generate code based on requirements
    # - Apply fixes
    # - Run unit tests
    return True
```

### Add Custom Validation Logic

Extend `step4_validation()` with additional test types:

```python
async def step4_validation(self, test_cases: List[TestCase]) -> List[TestCase]:
    # Add custom validation logic
    # - Database checks
    # - Integration tests
    # - Performance tests
    return test_cases
```

## CI/CD Integration

### GitHub Actions

```yaml
name: E2E Development Workflow

on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours
  workflow_dispatch:

jobs:
  e2e-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Run E2E Agent
        env:
          JWT_TOKEN: ${{ secrets.JWT_TOKEN }}
        run: ./run_e2e_agent.sh
      
      - name: Upload Results
        uses: actions/upload-artifact@v3
        with:
          name: e2e-results
          path: /tmp/e2e_agent_output/
```

## Troubleshooting

### Debug Mode

Enable verbose logging:

```python
# In e2e_dev_qa_agent.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Manual Testing

Test individual components:

```bash
# Test Maestro API
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://localhost:3100/api/integrations/tasks?types=epic

# Test Quality-Fabric API
curl http://localhost:8000/api/health
```

## Support & Contributions

- **Documentation**: This file and JIRA API reference
- **Issues**: Report via JIRA or project tracker
- **Contributions**: Follow existing code patterns

## Version History

- **v1.0.0** (2025-11-27): Initial implementation
  - Complete 6-step workflow
  - JIRA integration via Maestro API
  - Quality-Fabric validation
  - Automated task transitions
  - Epic closure logic

---

**Author**: E2E Development & QA Agent  
**Last Updated**: 2025-11-27  
**License**: Proprietary
