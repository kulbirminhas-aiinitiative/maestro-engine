#!/bin/bash
# Review and correct EPIC / task statuses for epics MD-1800 and above.
# Requires: JWT_TOKEN (Maestro API auth), API_BASE (e.g. http://localhost:3100/api), jq
# Usage: export JWT_TOKEN=...; export API_BASE=...; ./review_epics_status.sh [--dry-run] [--max-parallel 6]

set -euo pipefail
DRY_RUN=0
MAX_PARALLEL=6
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --max-parallel) shift; MAX_PARALLEL="$1" ;;
  esac
done

if [[ -z "${JWT_TOKEN:-}" || -z "${API_BASE:-}" ]]; then
  echo "ERROR: Set JWT_TOKEN and API_BASE environment variables first." >&2
  exit 1
fi

echo "Fetching epics (MD-1800 and above)..."
EPICS_JSON=$(curl -s "${API_BASE}/integrations/tasks?types=epic&pageSize=100" -H "Authorization: Bearer $JWT_TOKEN")
EPIC_KEYS=$(echo "$EPICS_JSON" | jq -r '.output.items[] | select(.externalId | capture("MD-(?<n>[0-9]+)").n | tonumber >= 1800) | .externalId')

if [[ -z "$EPIC_KEYS" ]]; then
  echo "No epics >= MD-1800 found."; exit 0
fi

echo "Target epics:"; echo "$EPIC_KEYS" | sed 's/^/  - /'

tmp_fifo=$(mktemp -u)
mkfifo "$tmp_fifo"
exec 3<>"$tmp_fifo"
rm "$tmp_fifo"
for ((i=0;i<MAX_PARALLEL;i++)); do echo >&3; done

TOTAL_REVERTED=0
EPIC_REVERTED=0
REPORT_FILE="/tmp/epic_status_review_$(date +%Y%m%d_%H%M%S).log"
: > "$REPORT_FILE"

process_epic() {
  local epic_key="$1"
  # Fetch epic details first
  local epic_details
  epic_details=$(curl -s "${API_BASE}/integrations/tasks/${epic_key}" -H "Authorization: Bearer $JWT_TOKEN" || true)
  local epic_status
  epic_status=$(echo "$epic_details" | jq -r '.output.status.name // "UNKNOWN"')
  echo "[EPIC $epic_key] Fetching tasks..."
  local tasks_json
  tasks_json=$(curl -s "${API_BASE}/integrations/tasks?epicIds=${epic_key}&pageSize=200" -H "Authorization: Bearer $JWT_TOKEN") || {
    echo "[EPIC $epic_key] ERROR fetching tasks"; return
  }
  local to_revert
  to_revert=$(echo "$tasks_json" | jq -r '.output.items[] | select((.status.name=="Done" or .status.statusCategory=="done") and (.labels | index("e2e-validated") | not)) | .externalId') || true
  if [[ -z "$to_revert" ]]; then
    echo "[EPIC $epic_key] No tasks to revert" | tee -a "$REPORT_FILE"
  else
    echo "[EPIC $epic_key] Tasks to revert:" | tee -a "$REPORT_FILE"
    echo "$to_revert" | sed 's/^/    - /' | tee -a "$REPORT_FILE"
    while read -r task_key; do
      [[ -z "$task_key" ]] && continue
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "[EPIC $epic_key] DRY-RUN would transition $task_key -> In Progress" | tee -a "$REPORT_FILE"
      else
        resp=$(curl -s -X POST "${API_BASE}/integrations/tasks/${task_key}/transition" \
          -H "Authorization: Bearer $JWT_TOKEN" \
          -H "Content-Type: application/json" \
          -d '{"targetStatus":"In Progress","comment":"Reverting incorrect Done status - no execution evidence"}')
        if echo "$resp" | jq -e '.output' >/dev/null 2>&1; then
          echo "[EPIC $epic_key] ✅ Reverted $task_key" | tee -a "$REPORT_FILE"
          TOTAL_REVERTED=$((TOTAL_REVERTED+1))
        else
          echo "[EPIC $epic_key] ⚠️ Failed to revert $task_key: $(echo "$resp" | jq -r '.error.message // .status // "unknown"')" | tee -a "$REPORT_FILE"
        fi
      fi
    done <<< "$to_revert"
  fi
  # Epic level revert logic
  if [[ "$epic_status" == "Done" ]]; then
    local active_or_validated
    active_or_validated=$(echo "$tasks_json" | jq '[.output.items[] | select(.status.statusCategory=="in_progress" or (.status.statusCategory=="done" and (.labels | index("e2e-validated"))))] | length')
    if [[ "$active_or_validated" -eq 0 ]]; then
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "[EPIC $epic_key] DRY-RUN would revert epic status Done -> In Progress" | tee -a "$REPORT_FILE"
      else
        resp_epic=$(curl -s -X POST "${API_BASE}/integrations/tasks/${epic_key}/transition" \
          -H "Authorization: Bearer $JWT_TOKEN" \
          -H "Content-Type: application/json" \
          -d '{"targetStatus":"In Progress","comment":"Epic marked Done without validated tasks; reverting."}')
        if echo "$resp_epic" | jq -e '.output' >/dev/null 2>&1; then
          echo "[EPIC $epic_key] 🔄 Reverted epic to In Progress" | tee -a "$REPORT_FILE"
          EPIC_REVERTED=$((EPIC_REVERTED+1))
        else
          echo "[EPIC $epic_key] ⚠️ Failed to revert epic: $(echo "$resp_epic" | jq -r '.error.message // .status // "unknown"')" | tee -a "$REPORT_FILE"
        fi
      fi
    else
      echo "[EPIC $epic_key] Epic Done status retained (validated/active tasks present)" | tee -a "$REPORT_FILE"
    fi
  fi

}

for epic in $EPIC_KEYS; do
  read -r -u 3
  {
    process_epic "$epic"
    echo >&3
  } &
done
wait
exec 3>&- 3<&-

echo "----------------------------------------"
echo "Review complete. Report: $REPORT_FILE"
echo "Total tasks reverted: $TOTAL_REVERTED"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "(Dry run - no changes applied)"
fi
