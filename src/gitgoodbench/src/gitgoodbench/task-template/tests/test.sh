#!/usr/bin/env bash
set -euo pipefail
# Use installed verifier tools, not executables on an agent-controlled PATH.
# verify.py writes /logs/verifier/reward.txt and reward.json atomically.
export PATH=/usr/local/bin:/usr/bin:/bin
exec python3 -I "$(dirname "$0")/verify.py" \
  "${HARBOR_REPO_DIR:-/workspace/repo}" \
  "${HARBOR_TESTS_DIR:-/tests}/target.bundle" \
  "${HARBOR_VERIFIER_LOG_DIR:-/logs/verifier}"
