#!/bin/bash
# UserPromptSubmit hook — 유저 입력을 proc/90_archive/prompts/ 에 기록

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('prompt',''))" 2>/dev/null)
SESSION=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('session_id','unknown'))" 2>/dev/null)

if [ -z "$PROMPT" ]; then exit 0; fi

LOG_DIR="$(pwd)/proc/archive/prompts"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).md"

echo "" >> "$LOG_FILE"
echo "## $(date +%H:%M:%S) | session: ${SESSION:0:8}" >> "$LOG_FILE"
echo "$PROMPT" >> "$LOG_FILE"

exit 0
