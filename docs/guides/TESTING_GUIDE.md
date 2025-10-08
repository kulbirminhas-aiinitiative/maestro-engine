# E2E Test Guide - MAESTRO Engine

**Date**: 2025-10-01
**Purpose**: End-to-end testing of web page creation workflow
**Entry Point**: `enhanced_lean_ultimate_mega_team_utcp.py`

## Overview

The E2E test will use the **Enhanced Lean Ultimate Mega Team (UTCP)** orchestrator to:
1. Accept a simple requirement ("Create a simple web page")
2. Execute multi-persona workflow (11 personas)
3. Generate files (HTML, CSS, JS)
4. Optionally validate with Quality Fabric
5. Return complete web application

## Endpoints Used

### Primary Entry Point
**File**: `src/mcp/enhanced_lean_ultimate_mega_team_utcp.py`
**Function**: `execute_enhanced_lean_workflow_utcp(requirement, config)`

### External Services (UTCP Integration)
```python
quality_fabric_url: "http://localhost:8000/api/execute"
template_service_url: "http://localhost:9600/api/templates"
orchestration_gateway_url: "http://localhost:8002/api/orchestrate"
```

### Personas Involved (11 Total)
1. **requirement_analyst** - Analyzes requirements
2. **solution_architect** - Designs architecture
3. **frontend_developer** - Creates HTML/CSS/JS
4. **backend_developer** - Creates API (if needed)
5. **devops_engineer** - Creates deployment config
6. **qa_engineer** - Sends to Quality Fabric
7. **security_specialist** - Security review
8. **ui_ux_designer** - Design specifications
9. **technical_writer** - Documentation
10. **deployment_specialist** - Deployment guide
11. **deployment_integration_tester** - Integration tests

## Prerequisites

### ✅ Services Running
```bash
# Check all services are up
curl -s http://localhost:8002/health  # MAESTRO Engine
curl -s http://localhost:8000/api/health  # Quality Fabric
curl -s http://localhost:9600/health  # Template Registry

# Check service registry
curl -s http://localhost:8002/registry/health | jq '.healthy_services'
# Expected: 3 (coordinator, quality_fabric, templates)
```

### ✅ Dependencies Available
```bash
cd /home/ec2-user/projects/maestro-engine
poetry run python3 -c "
import httpx; print('✅ httpx')
from mcp.mcp_cache_config import get_mcp_cache; print('✅ MCP cache')
"
```

### ⚠️ Optional Dependencies
- `unified_claude_tools` - Falls back to alternative if not available
- `chromadb` - RAG features disabled if not available

## Test Execution Methods

### Method 1: Command Line (Recommended)

**Simple test**:
```bash
cd /home/ec2-user/projects/maestro-engine
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py "Create a simple web page with a header and button"
```

**Expected Output**:
```
📋 Requirement: Create a simple web page with a header and button
🔗 Using UTCP-enabled workflow
[INFO] Session ID: enhanced_lean_utcp_1727798400
[INFO] Starting workflow execution...
[INFO] Requirement Analyst: Analyzing requirement...
[INFO] Solution Architect: Designing architecture...
[INFO] Frontend Developer: Creating UI components...
... (11 personas execute)
[INFO] Workflow complete!

✅ Success: True
🔧 Method: local_execution (or utcp_fallback)
📁 Files: 3-5
⏱️  Time: 30-120s

📊 Quality Score: 85/100
🔒 Security Score: 90/100
✅ Test Coverage: 75%
```

**Default requirement** (if no argument):
```bash
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py
# Uses default: "Create a modern todo list web application"
```

### Method 2: Python Script

Create `test_e2e_simple.py`:
```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, 'src')

from mcp.enhanced_lean_ultimate_mega_team_utcp import (
    execute_enhanced_lean_workflow_utcp,
    EnhancedTeamConfig
)

async def test_simple_web_page():
    """E2E test: Create a simple web page"""

    requirement = "Create a simple web page with a header, paragraph, and button"

    # Configure workflow
    config = EnhancedTeamConfig(
        enable_utcp=True,           # Enable UTCP service calls
        enable_rag=False,            # Disable RAG (optional)
        enable_mcp=True,             # Enable MCP cache
        enable_event_emission=True,  # Enable audit logging
        selected_personas=[          # Minimal persona set
            "requirement_analyst",
            "frontend_developer",
            "qa_engineer"
        ]
    )

    print(f"🧪 E2E Test: {requirement}")
    print(f"📋 Personas: {len(config.selected_personas)}")

    # Execute workflow
    result = await execute_enhanced_lean_workflow_utcp(requirement, config)

    # Validate results
    assert result['success'], "Workflow failed"
    assert len(result.get('files_generated', [])) > 0, "No files generated"

    print("\n✅ E2E Test PASSED")
    print(f"📁 Files: {result.get('files_generated', [])}")
    print(f"⏱️  Time: {result.get('total_execution_time', 0):.2f}s")

    return result

if __name__ == "__main__":
    asyncio.run(test_simple_web_page())
```

**Run**:
```bash
poetry run python test_e2e_simple.py
```

### Method 3: Via Orchestration Gateway (HTTP API)

**Start orchestration gateway** (if not running):
```bash
cd /home/ec2-user/projects/maestro-engine
poetry run python src/orchestration/maestro_unified_orchestration_gateway.py &
# Runs on port 8004
```

**Send HTTP request**:
```bash
curl -X POST http://localhost:8004/v4/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "requirement": "Create a simple web page with a header and button",
    "workflow_type": "interconnected",
    "personas": ["requirement_analyst", "frontend_developer", "qa_engineer"]
  }' | jq
```

**Expected Response**:
```json
{
  "success": true,
  "session_id": "orchestration_123456",
  "files_generated": ["index.html", "styles.css", "script.js"],
  "execution_time": 45.2,
  "quality_validation": {
    "quality_score": 85,
    "security_score": 90
  }
}
```

## Output Locations

### Generated Files
```
/tmp/maestro_output/enhanced_lean_utcp_[timestamp]/
├── index.html                      # Main HTML file
├── styles.css                      # Stylesheet
├── script.js                       # JavaScript
├── README.md                       # Documentation
└── audit_logs/                     # Audit trail
    ├── session_state.json
    └── workflow_events.json
```

### MCP Cache
```
/tmp/mcp_cache/
├── mcp_cache.json                  # Updated with new session
└── session_state.json              # Session metadata
```

### Logs
```
Console output                       # Real-time progress
/tmp/maestro-engine.log             # Service logs (if running as service)
```

## Workflow Execution Flow

```
1. User Provides Requirement
   ↓
2. Enhanced Lean Team UTCP
   ├─ Session ID generated
   ├─ Config validated
   └─ MCP cache initialized
   ↓
3. Persona Execution (Sequential/Parallel)
   ├─ Requirement Analyst
   │  └─ Analyzes: "web page" → HTML/CSS/JS needed
   ├─ Solution Architect (skipped for simple pages)
   ├─ Frontend Developer
   │  ├─ Checks template registry (http://localhost:9600)
   │  ├─ Generates HTML structure
   │  ├─ Generates CSS styles
   │  └─ Generates JavaScript
   ├─ Backend Developer (skipped if no backend needed)
   ├─ QA Engineer
   │  └─ Sends to Quality Fabric (http://localhost:8000)
   └─ Other personas as configured
   ↓
4. Quality Validation (Optional)
   ├─ Quality Fabric runs tests
   ├─ Security scan
   └─ Returns quality scores
   ↓
5. Results Aggregation
   ├─ Collect all generated files
   ├─ Save to output directory
   ├─ Update MCP cache
   └─ Generate audit trail
   ↓
6. Return Results
   └─ Success status, files, metrics
```

## Service Integration

### UTCP Service Calls

**Template Service**:
```python
# Frontend Developer checks for templates
GET http://localhost:9600/api/templates?category=web_page
# If found: Use template
# If not found: Generate from scratch
```

**Quality Fabric**:
```python
# QA Engineer validates code
POST http://localhost:8000/api/execute
{
  "test_spec": {
    "type": "static_analysis",
    "files": ["index.html", "styles.css", "script.js"]
  }
}
# Returns: Quality scores, test results
```

**Orchestration Gateway** (optional):
```python
# Can delegate to orchestration gateway
POST http://localhost:8002/api/orchestrate
{
  "requirement": "...",
  "workflow_type": "phase_1"
}
```

### Fallback Behavior

If external services unavailable:
```python
utcp_config.fallback_to_local = True  # (default)

# Behavior:
# 1. Try UTCP service call (with retry)
# 2. If fails → Fallback to local execution
# 3. Log warning but continue
```

## Expected Execution Time

| Configuration | Personas | Est. Time |
|---------------|----------|-----------|
| Minimal (3 personas) | analyst, frontend, qa | 30-60s |
| Standard (7 personas) | analyst, architect, devs, qa | 60-120s |
| Full (11 personas) | All personas | 120-300s |

**Factors affecting time**:
- Complexity of requirement
- External service response times
- RAG search time (if enabled)
- Quality validation depth

## Success Criteria

### ✅ Test Passes If:
1. `result['success'] == True`
2. `len(result['files_generated']) > 0`
3. Files exist on disk
4. No critical errors in logs
5. Quality score > 70 (if validation enabled)

### ❌ Test Fails If:
1. `result['success'] == False`
2. No files generated
3. Exception raised
4. All services timeout
5. Quality score < 50

## Troubleshooting

### Issue: "httpx not available"
```bash
poetry add httpx
```

### Issue: "unified_claude_tools not available"
**Solution**: This is optional, workflow will fallback
```bash
# To enable (if needed):
poetry add unified-claude-tools
# Or continue without it - fallback mode works
```

### Issue: External services timeout
```bash
# Check services are running
curl http://localhost:8000/api/health
curl http://localhost:9600/health

# Increase timeout
config = EnhancedTeamConfig()
config.utcp_config.timeout = 1200  # 20 minutes
```

### Issue: No files generated
```bash
# Check output directory
ls -la /tmp/maestro_output/

# Check MCP cache
cat /tmp/mcp_cache/session_state.json | jq '.cache_size'

# Check logs for errors
grep -i error /tmp/maestro-engine.log
```

### Issue: Quality validation fails
```bash
# Quality Fabric might be strict
# Check what failed:
curl http://localhost:8000/api/health

# Disable quality validation if needed:
config = EnhancedTeamConfig()
config.selected_personas = [
    "requirement_analyst",
    "frontend_developer"
    # Remove "qa_engineer" to skip validation
]
```

## Test Examples

### Example 1: Minimal Web Page (Fast)
```bash
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a simple HTML page with Hello World"
```

**Expected**: 1-2 files, 20-30 seconds

### Example 2: Interactive Web Page
```bash
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a web page with a form that collects name and email"
```

**Expected**: 3-4 files (HTML, CSS, JS), 40-60 seconds

### Example 3: Dashboard Page
```bash
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a dashboard web page with metrics cards and a chart"
```

**Expected**: 4-5 files, 60-90 seconds

### Example 4: Full Todo App
```bash
poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py
# Uses default requirement: "Create a modern todo list web application"
```

**Expected**: 5-8 files, 120-180 seconds

## Validation Steps

After test completes:

**1. Check files exist**:
```bash
ls -la /tmp/maestro_output/enhanced_lean_utcp_*/
```

**2. View generated HTML**:
```bash
# Find latest session
SESSION=$(ls -t /tmp/maestro_output/ | head -1)
cat /tmp/maestro_output/$SESSION/index.html
```

**3. Test in browser**:
```bash
# Start simple HTTP server
cd /tmp/maestro_output/$SESSION
python3 -m http.server 8080
# Open: http://localhost:8080
```

**4. Check MCP cache**:
```bash
cat /tmp/mcp_cache/session_state.json | jq '{
  cache_size: .cache_size,
  active_sessions: (.active_sessions | length),
  latest_session: .active_sessions[-1]
}'
```

**5. Review audit logs**:
```bash
cat /tmp/maestro_output/$SESSION/audit_logs/workflow_events.json | jq
```

## Advanced Configuration

### Custom Persona Selection
```python
config = EnhancedTeamConfig(
    selected_personas=[
        "requirement_analyst",    # Always recommended
        "frontend_developer",     # For web pages
        "ui_ux_designer",         # For better design
        "qa_engineer"             # For validation
    ]
)
```

### Disable External Services
```python
config = EnhancedTeamConfig(
    enable_utcp=False,           # No external service calls
    enable_rag=False,            # No RAG search
    enable_mcp=True,             # Keep MCP cache only
)
```

### Custom Output Path
```python
config = EnhancedTeamConfig(
    project_path="/tmp/my_custom_output"
)
```

### Extended Timeout
```python
config = EnhancedTeamConfig()
config.utcp_config.timeout = 1800  # 30 minutes
config.max_execution_time = 3600   # 1 hour max
```

## Performance Monitoring

### Track execution time
```bash
time poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
  "Create a simple web page"
```

### Monitor service health during test
```bash
# In another terminal:
watch -n 2 'curl -s http://localhost:8002/registry/health | jq ".healthy_services"'
```

### Check MCP cache growth
```bash
# Before test
du -sh /tmp/mcp_cache/

# After test
du -sh /tmp/mcp_cache/

# View delta
```

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: E2E Test - Web Page Creation
  run: |
    cd maestro-engine
    poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
      "Create a simple web page" > test_output.log

    # Validate
    grep "Success: True" test_output.log
    ls /tmp/maestro_output/*/index.html
```

### Jenkins Example
```groovy
stage('E2E Test') {
    steps {
        sh '''
            cd maestro-engine
            poetry run python src/mcp/enhanced_lean_ultimate_mega_team_utcp.py \
              "Create a simple web page"
        '''
    }
}
```

## Next Steps

After successful E2E test:

1. **Review generated files** - Check quality
2. **Test in browser** - Verify functionality
3. **Check audit logs** - Review workflow execution
4. **Monitor cache** - Ensure MCP cache working
5. **Run with different requirements** - Test variations
6. **Integrate into CI/CD** - Automate testing

---

**Ready to Run**: ✅
**Recommended Test**: `"Create a simple web page with a header and button"`
**Expected Duration**: 30-60 seconds
**Success Rate**: >90% (with services running)
