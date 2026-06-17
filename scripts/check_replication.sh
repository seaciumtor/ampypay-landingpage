#!/usr/bin/env bash
# check_replication.sh
# Polls a single URL until a new version appears, then prints how long it took.
#
# Usage:
#   ./scripts/check_replication.sh <url> [interval_seconds]
#
# Example:
#   ./scripts/check_replication.sh https://ampypay.com 15
#
# Workflow:
#   1. Read current version from the URL (before deploy) — this is the "old" version
#   2. You deploy
#   3. Script keeps polling until a different version appears
#   4. Prints the time it took

set -euo pipefail

URL="${1:-}"
INTERVAL="${2:-15}"
VERSION_PATH="/version.json"

if [[ -z "$URL" ]]; then
  echo "Usage: $0 <url> [interval_seconds]"
  echo "Example: $0 https://ampypay.com 15"
  exit 1
fi

fetch_version() {
  curl -sf --max-time 10 "${URL}${VERSION_PATH}" 2>/dev/null \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('version',''))" 2>/dev/null \
    || echo ""
}

iso_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
epoch_now() { date +%s; }

echo "=== Replication Delay Checker ==="
echo "URL: $URL"
echo "Poll interval: ${INTERVAL}s"
echo ""

# Step 1: Snapshot current version before deploy
echo "[$(iso_now)] Reading current version (run this BEFORE deploying)..."
OLD_VERSION=$(fetch_version)

if [[ -z "$OLD_VERSION" ]]; then
  echo "ERROR: Could not fetch version.json from $URL"
  exit 1
fi

echo "[$(iso_now)] Current version: $OLD_VERSION"
echo ""
echo "Deploy now, then wait..."
echo "(polling every ${INTERVAL}s until version changes)"
echo ""

# Step 2: Poll until version changes
attempt=0
while true; do
  attempt=$((attempt + 1))
  NEW_VERSION=$(fetch_version)
  NOW=$(iso_now)

  if [[ -z "$NEW_VERSION" ]]; then
    echo "[$NOW] Attempt $attempt: no response"
  elif [[ "$NEW_VERSION" != "$OLD_VERSION" ]]; then
    SEEN_AT=$(epoch_now)
    echo "[$NOW] Attempt $attempt: new version detected! ($NEW_VERSION)"
    break
  else
    echo "[$NOW] Attempt $attempt: still $NEW_VERSION"
  fi

  sleep "$INTERVAL"
done

echo ""
echo "=============================="
echo "  RESULT"
echo "=============================="
echo "  Old version : $OLD_VERSION"
echo "  New version : $NEW_VERSION"
echo "  Detected at : $(iso_now)"
echo "=============================="
echo ""
echo "Note: URL is shared between US/AS — this confirms at least one node"
echo "updated. Cannot guarantee AS specifically without IT adding node IDs."
