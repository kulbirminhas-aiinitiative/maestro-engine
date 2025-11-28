#!/bin/bash
# E2E Development & QA Agent - JIRA Integration Workflow
# Implements: Initialization → Strategy → Implementation → Validation → Reporting → Closure

set -e

export JWT_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyWlBob1h4dGVyNEw5c2pGUWJxTHYiLCJlbWFpbCI6InRlc3RAbWFlc3Ryby5haSIsInJvbGUiOiJhZG1pbiIsImlhdCI6MTc2NDI3ODQwOSwiZXhwIjoxNzY0MzY0ODA5fQ.6njeq4zfDoyykzh4Z7PYFJXeIkr6x-HamvkA6ZXV5Ys"
API_BASE="http://localhost:3100/api"
QF_API_BASE="http://localhost:8000"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║     E2E Development & QA Workflow - JIRA Integration           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# ==============================================================================
# STEP 1: JIRA INITIALIZATION - Fetch 'To Do' Epics
# ==============================================================================
echo "📋 STEP 1: JIRA INITIALIZATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Fetching 'To Do' Epics from JIRA..."

EPICS_RESPONSE=$(curl -s -X GET "${API_BASE}/integrations/tasks?types=epic&statusCategories=todo,in_progress&pageSize=10" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json")

# Extract epic data
EPIC_COUNT=$(echo "$EPICS_RESPONSE" | jq -r '.output.items | length')

if [ "$EPIC_COUNT" -eq 0 ]; then
  echo "❌ No 'To Do' or 'In Progress' Epics found!"
  exit 1
fi

echo "✅ Found $EPIC_COUNT Epics"
echo ""
echo "Available Epics:"
echo "$EPICS_RESPONSE" | jq -r '.output.items[] | "  📌 [\(.externalId)] \(.title)\n     Status: \(.status.name) | Priority: \(.priority // "N/A") | Labels: \(.labels | join(", "))"'
echo ""

# Select first epic (or highest priority)
EPIC_ID=$(echo "$EPICS_RESPONSE" | jq -r '.output.items[0].externalId')
EPIC_TITLE=$(echo "$EPICS_RESPONSE" | jq -r '.output.items[0].title')
EPIC_STATUS=$(echo "$EPICS_RESPONSE" | jq -r '.output.items[0].status.name')

echo "🎯 Selected Epic: [$EPIC_ID] $EPIC_TITLE"
echo "   Current Status: $EPIC_STATUS"
echo ""

# Transition to 'In Progress' if currently 'To Do'
if [ "$EPIC_STATUS" = "To Do" ] || [ "$EPIC_STATUS" = "TODO" ]; then
  echo "🔄 Transitioning Epic to 'In Progress'..."
  TRANSITION_RESPONSE=$(curl -s -X POST "${API_BASE}/integrations/tasks/${EPIC_ID}/transition" \
    -H "Authorization: Bearer $JWT_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "targetStatus": "In Progress",
      "comment": "E2E Development & QA Agent started working on this epic"
    }')
  
  if echo "$TRANSITION_RESPONSE" | jq -e '.error' > /dev/null 2>&1; then
    echo "⚠️  Could not transition epic (might already be In Progress): $(echo $TRANSITION_RESPONSE | jq -r '.error.message')"
  else
    echo "✅ Epic transitioned to 'In Progress'"
  fi
  echo ""
fi

# Fetch subtasks/stories for this epic
echo "📝 Fetching tasks for Epic $EPIC_ID..."
TASKS_RESPONSE=$(curl -s -X GET "${API_BASE}/integrations/tasks?epicIds=${EPIC_ID}&pageSize=20" \
  -H "Authorization: Bearer $JWT_TOKEN")

TASK_COUNT=$(echo "$TASKS_RESPONSE" | jq -r '.output.items | length')
echo "✅ Found $TASK_COUNT tasks/stories in this epic"

if [ "$TASK_COUNT" -gt 0 ]; then
  echo ""
  echo "Tasks:"
  echo "$TASKS_RESPONSE" | jq -r '.output.items[] | "  🔹 [\(.externalId)] \(.title) - \(.status.name)"'
fi

echo ""
echo ""

# ==============================================================================
# STEP 2: STRATEGY GENERATION
# ==============================================================================
echo "🧠 STEP 2: STRATEGY GENERATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

STRATEGY_FILE="/tmp/e2e_strategy_${EPIC_ID}.md"
TEST_CASES_FILE="/tmp/e2e_test_cases_${EPIC_ID}.json"

cat > "$STRATEGY_FILE" << EOF
# Development Strategy for Epic: $EPIC_ID
## Epic Title: $EPIC_TITLE

### Overview
This epic has been selected for E2E development and QA workflow.

### Current Status
- **Epic ID**: $EPIC_ID
- **Status**: In Progress
- **Task Count**: $TASK_COUNT subtasks

### Development Plan
1. **Analysis Phase**
   - Review epic requirements and acceptance criteria
   - Identify dependencies and blockers
   - Assess current codebase state

2. **Implementation Phase**
   - Develop features according to acceptance criteria
   - Follow coding standards and best practices
   - Implement unit tests alongside features

3. **Testing Phase**
   - Execute comprehensive test suite
   - Validate against quality-fabric API (localhost:8000)
   - Perform integration testing

4. **Validation Phase**
   - Code review
   - Quality gates validation
   - Performance testing

### Test Strategy
- Unit Tests: Per component/module
- Integration Tests: API endpoints via quality-fabric
- E2E Tests: Full workflow validation

### Success Criteria
- All subtasks completed
- All tests passing
- Code review approved
- Epic transitioned to 'Done'

Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

echo "✅ Development strategy created: $STRATEGY_FILE"
echo ""

# Generate comprehensive test cases
cat > "$TEST_CASES_FILE" << EOF
{
  "epic_id": "$EPIC_ID",
  "epic_title": "$EPIC_TITLE",
  "generated_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "test_cases": [
    {
      "id": "TC-001",
      "title": "Verify API Health Check",
      "type": "integration",
      "priority": "high",
      "description": "Validate that quality-fabric API is healthy and responsive",
      "endpoint": "/health",
      "method": "GET",
      "expected_status": 200,
      "expected_response": {"status": "healthy"},
      "status": "pending",
      "execution_time_ms": null,
      "error": null
    },
    {
      "id": "TC-002",
      "title": "JIRA Epic Retrieval",
      "type": "integration",
      "priority": "high",
      "description": "Verify epic can be retrieved from JIRA via integration API",
      "endpoint": "/api/integrations/tasks/$EPIC_ID",
      "method": "GET",
      "expected_status": 200,
      "status": "pending",
      "execution_time_ms": null,
      "error": null
    },
    {
      "id": "TC-003",
      "title": "JIRA Task List for Epic",
      "type": "integration",
      "priority": "medium",
      "description": "Verify all tasks under epic can be listed",
      "endpoint": "/api/integrations/tasks?epicIds=$EPIC_ID",
      "method": "GET",
      "expected_status": 200,
      "status": "pending",
      "execution_time_ms": null,
      "error": null
    },
    {
      "id": "TC-004",
      "title": "Epic Status Transition",
      "type": "integration",
      "priority": "high",
      "description": "Verify epic status can be transitioned",
      "endpoint": "/api/integrations/tasks/$EPIC_ID/transition",
      "method": "POST",
      "expected_status": 200,
      "status": "pending",
      "execution_time_ms": null,
      "error": null
    }
  ]
}
EOF

echo "✅ Test cases generated: $TEST_CASES_FILE"
cat "$TEST_CASES_FILE" | jq -r '.test_cases[] | "  🧪 [\(.id)] \(.title) - Priority: \(.priority)"'
echo ""
echo ""

# ==============================================================================
# STEP 3: IMPLEMENTATION
# ==============================================================================
echo "⚙️  STEP 3: IMPLEMENTATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "ℹ️  In a real scenario, this would execute code development/fixes"
echo "ℹ️  For this demo, we'll focus on validation of existing APIs"
echo ""
echo ""

# ==============================================================================
# STEP 4: VALIDATION - Run Tests
# ==============================================================================
echo "🧪 STEP 4: VALIDATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Running tests against quality-fabric API (localhost:8000)..."
echo ""

# Test Case 1: Health Check
echo "Running TC-001: API Health Check..."
TC1_START=$(date +%s%3N)
TC1_RESPONSE=$(curl -s -w "\n%{http_code}" "$QF_API_BASE/health")
TC1_HTTP_CODE=$(echo "$TC1_RESPONSE" | tail -n 1)
TC1_BODY=$(echo "$TC1_RESPONSE" | head -n -1)
TC1_END=$(date +%s%3N)
TC1_DURATION=$((TC1_END - TC1_START))

if [ "$TC1_HTTP_CODE" = "200" ]; then
  TC1_STATUS="passed"
  echo "  ✅ PASSED (${TC1_DURATION}ms) - API is healthy"
  jq '.test_cases[0] |= . + {"status": "passed", "execution_time_ms": '$TC1_DURATION', "http_code": '$TC1_HTTP_CODE'}' \
    "$TEST_CASES_FILE" > "${TEST_CASES_FILE}.tmp" && mv "${TEST_CASES_FILE}.tmp" "$TEST_CASES_FILE"
else
  TC1_STATUS="failed"
  echo "  ❌ FAILED (${TC1_DURATION}ms) - HTTP $TC1_HTTP_CODE"
  jq '.test_cases[0] |= . + {"status": "failed", "execution_time_ms": '$TC1_DURATION', "http_code": '$TC1_HTTP_CODE', "error": "Unexpected HTTP status"}' \
    "$TEST_CASES_FILE" > "${TEST_CASES_FILE}.tmp" && mv "${TEST_CASES_FILE}.tmp" "$TEST_CASES_FILE"
fi

# Test Case 2: Epic Retrieval
echo "Running TC-002: JIRA Epic Retrieval..."
TC2_START=$(date +%s%3N)
TC2_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${API_BASE}/integrations/tasks/${EPIC_ID}" \
  -H "Authorization: Bearer $JWT_TOKEN")
TC2_HTTP_CODE=$(echo "$TC2_RESPONSE" | tail -n 1)
TC2_BODY=$(echo "$TC2_RESPONSE" | head -n -1)
TC2_END=$(date +%s%3N)
TC2_DURATION=$((TC2_END - TC2_START))

if [ "$TC2_HTTP_CODE" = "200" ]; then
  TC2_STATUS="passed"
  echo "  ✅ PASSED (${TC2_DURATION}ms) - Epic retrieved successfully"
  jq '.test_cases[1] |= . + {"status": "passed", "execution_time_ms": '$TC2_DURATION', "http_code": '$TC2_HTTP_CODE'}' \
    "$TEST_CASES_FILE" > "${TEST_CASES_FILE}.tmp" && mv "${TEST_CASES_FILE}.tmp" "$TEST_CASES_FILE"
else
  TC2_STATUS="failed"
  echo "  ❌ FAILED (${TC2_DURATION}ms) - HTTP $TC2_HTTP_CODE"
  jq '.test_cases[1] |= . + {"status": "failed", "execution_time_ms": '$TC2_DURATION', "http_code": '$TC2_HTTP_CODE', "error": "Epic not found or unauthorized"}' \
    "$TEST_CASES_FILE" > "${TEST_CASES_FILE}.tmp" && mv "${TEST_CASES_FILE}.tmp" "$TEST_CASES_FILE"
fi

# Test Case 3: Task List
echo "Running TC-003: JIRA Task List for Epic..."
TC3_START=$(date +%s%3N)
TC3_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "${API_BASE}/integrations/tasks?epicIds=${EPIC_ID}" \
  -H "Authorization: Bearer $JWT_TOKEN")
TC3_HTTP_CODE=$(echo "$TC3_RESPONSE" | tail -n 1)
TC3_BODY=$(echo "$TC3_RESPONSE" | head -n -1)
TC3_END=$(date +%s%3N)
TC3_DURATION=$((TC3_END - TC3_START))

if [ "$TC3_HTTP_CODE" = "200" ]; then
  TC3_STATUS="passed"
  echo "  ✅ PASSED (${TC3_DURATION}ms) - Tasks listed successfully"
  jq '.test_cases[2] |= . + {"status": "passed", "execution_time_ms": '$TC3_DURATION', "http_code": '$TC3_HTTP_CODE'}' \
    "$TEST_CASES_FILE" > "${TEST_CASES_FILE}.tmp" && mv "${TEST_CASES_FILE}.tmp" "$TEST_CASES_FILE"
else
  TC3_STATUS="failed"
  echo "  ❌ FAILED (${TC3_DURATION}ms) - HTTP $TC3_HTTP_CODE"
  jq '.test_cases[2] |= . + {"status": "failed", "execution_time_ms": '$TC3_DURATION', "http_code": '$TC3_HTTP_CODE', "error": "Could not list tasks"}' \
    "$TEST_CASES_FILE" > "${TEST_CASES_FILE}.tmp" && mv "${TEST_CASES_FILE}.tmp" "$TEST_CASES_FILE"
fi

echo ""
echo ""

# ==============================================================================
# STEP 5: REPORTING
# ==============================================================================
echo "📊 STEP 5: REPORTING"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Calculate test summary
TOTAL_TESTS=$(jq '.test_cases | length' "$TEST_CASES_FILE")
PASSED_TESTS=$(jq '[.test_cases[] | select(.status == "passed")] | length' "$TEST_CASES_FILE")
FAILED_TESTS=$(jq '[.test_cases[] | select(.status == "failed")] | length' "$TEST_CASES_FILE")
PASS_RATE=$(echo "scale=2; $PASSED_TESTS * 100 / $TOTAL_TESTS" | bc)

echo "Test Execution Summary:"
echo "  Total Tests: $TOTAL_TESTS"
echo "  Passed: ✅ $PASSED_TESTS"
echo "  Failed: ❌ $FAILED_TESTS"
echo "  Pass Rate: ${PASS_RATE}%"
echo ""

# Update JIRA tasks with test results
if [ "$TASK_COUNT" -gt 0 ]; then
  echo "Updating JIRA tasks with execution results..."
  
  # Get first task from epic
  FIRST_TASK_ID=$(echo "$TASKS_RESPONSE" | jq -r '.output.items[0].externalId // empty')
  
  if [ -n "$FIRST_TASK_ID" ]; then
    COMMENT_BODY="E2E Test Execution Results:\\n\\n✅ Passed: $PASSED_TESTS/$TOTAL_TESTS\\n❌ Failed: $FAILED_TESTS/$TOTAL_TESTS\\nPass Rate: ${PASS_RATE}%\\n\\nExecution Time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")\\n\\nTest Details:\\n$(jq -r '.test_cases[] | "- [\(.id)] \(.title): \(.status) (\(.execution_time_ms)ms)"' "$TEST_CASES_FILE")"
    
    # Note: Comment API would require additional endpoint, skipping for demo
    echo "  ℹ️  Would update task $FIRST_TASK_ID with test results"
    
    # If all tests passed, transition task to Done
    if [ "$FAILED_TESTS" -eq 0 ]; then
      echo "  🎉 All tests passed! Task $FIRST_TASK_ID eligible for 'Done' transition"
      # TRANSITION_RESPONSE=$(curl -s -X POST "${API_BASE}/integrations/tasks/${FIRST_TASK_ID}/transition" ...)
    fi
  fi
fi

echo ""
echo ""

# ==============================================================================
# STEP 6: CLOSURE
# ==============================================================================
echo "🏁 STEP 6: CLOSURE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check if all subtasks are done
if [ "$TASK_COUNT" -gt 0 ]; then
  DONE_TASKS=$(echo "$TASKS_RESPONSE" | jq '[.output.items[] | select(.status.category == "done")] | length')
  echo "Subtask Completion: $DONE_TASKS/$TASK_COUNT tasks done"
  
  if [ "$DONE_TASKS" -eq "$TASK_COUNT" ]; then
    echo "✅ All subtasks completed!"
    
    if [ "$FAILED_TESTS" -eq 0 ]; then
      echo "✅ All tests passed!"
      echo ""
      echo "🎯 Transitioning Epic $EPIC_ID to 'Done'..."
      
      # Note: Keeping epic in "In Progress" for demo - in production would transition to Done
      echo "  ℹ️  Demo mode: Keeping epic as 'In Progress' for review"
      # EPIC_DONE_RESPONSE=$(curl -s -X POST "${API_BASE}/integrations/tasks/${EPIC_ID}/transition" ...)
    else
      echo "⚠️  Cannot complete epic: $FAILED_TESTS test(s) failed"
    fi
  else
    echo "⏳ Epic not ready for completion: $((TASK_COUNT - DONE_TASKS)) task(s) remaining"
  fi
else
  echo "ℹ️  Epic has no subtasks - evaluating based on test results only"
  
  if [ "$FAILED_TESTS" -eq 0 ]; then
    echo "✅ All tests passed - Epic can be transitioned to 'Done'"
  else
    echo "⚠️  Cannot complete epic: $FAILED_TESTS test(s) failed"
  fi
fi

echo ""
echo ""

# ==============================================================================
# SUMMARY
# ==============================================================================
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    WORKFLOW COMPLETED                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 Epic: [$EPIC_ID] $EPIC_TITLE"
echo "🧪 Tests: $PASSED_TESTS/$TOTAL_TESTS passed (${PASS_RATE}%)"
echo "📁 Strategy: $STRATEGY_FILE"
echo "📊 Results: $TEST_CASES_FILE"
echo ""
echo "Next Steps:"
if [ "$FAILED_TESTS" -gt 0 ]; then
  echo "  1. Review failed test cases in: $TEST_CASES_FILE"
  echo "  2. Fix issues and re-run validation"
  echo "  3. Update JIRA tasks with fixes"
else
  echo "  ✅ All validation passed!"
  echo "  1. Review test results: $TEST_CASES_FILE"
  echo "  2. Complete remaining subtasks (if any)"
  echo "  3. Transition epic to 'Done'"
fi
echo ""
