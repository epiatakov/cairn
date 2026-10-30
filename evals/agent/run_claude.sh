#!/usr/bin/env bash
# Real A/B run with Claude Code headless: every task, with and without brain recall.
# This spends API credits. Needs the `claude` CLI and ANTHROPIC_API_KEY.
#
#   evals/agent/run_claude.sh                       # 13 tasks x 2 arms x 3 repeats
#   evals/agent/run_claude.sh --repeats 1 --tasks docker-apt,git-untrack --model sonnet
set -euo pipefail
cd "$(dirname "$0")/../.."
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ANTHROPIC_API_KEY is not set; nothing to run." >&2
  exit 1
fi
python -m evals.agent --runner claude --repeats 3 "$@" | tee evals/results/agent-claude.md
