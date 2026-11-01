"""Agent runners. A runner gets a prepared repository and a prompt and edits the repository.

- ``mock``: deterministic and free. It applies the task's reference fix when recall
  surfaced one of the task's brain entries, and the naive fix otherwise. It tests the
  harness and the recall step end to end; it is not evidence that the brain helps agents.
- ``claude``: Claude Code headless (``claude -p``). Needs the ``claude`` CLI and
  ``ANTHROPIC_API_KEY``, and costs money.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .tasks import Task


@dataclass
class RunResult:
    turns: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    error: str | None = None


class Runner(Protocol):
    name: str

    def unavailable_reason(self) -> str | None:
        """Why this runner cannot run here, or None if it can."""
        ...

    def run(self, task: Task, repo: Path, prompt: str, recalled: list[str]) -> RunResult: ...


class MockRunner:
    name = "mock"

    def unavailable_reason(self) -> str | None:
        return None

    def run(self, task: Task, repo: Path, prompt: str, recalled: list[str]) -> RunResult:
        if set(recalled) & set(task.brain_ids):
            task.solve(repo)
        else:
            task.naive(repo)
        return RunResult(turns=1)


class ClaudeRunner:
    """Run Claude Code non-interactively in the task repository.

    ``--bare`` skips CLAUDE.md discovery, auto-memory, hooks and plugins, so neither arm
    sees the operator's own notes; the brain reaches the agent only through the prompt.
    Web tools are disabled so the agent cannot look the pitfall up instead.
    """

    name = "claude"

    def __init__(
        self,
        *,
        model: str | None = None,
        max_turns: int = 25,
        max_budget_usd: float = 1.0,
        timeout: float = 900,
        executable: str = "claude",
    ) -> None:
        self.model = model
        self.max_turns = max_turns
        self.max_budget_usd = max_budget_usd
        self.timeout = timeout
        self.executable = executable

    def unavailable_reason(self) -> str | None:
        if shutil.which(self.executable) is None:
            return f"'{self.executable}' is not on PATH"
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return "ANTHROPIC_API_KEY is not set"
        return None

    def command(self) -> list[str]:
        cmd = [
            self.executable,
            "--print",
            "--output-format",
            "json",
            "--bare",
            "--no-session-persistence",
            "--dangerously-skip-permissions",
            "--max-turns",
            str(self.max_turns),
            "--max-budget-usd",
            str(self.max_budget_usd),
        ]
        if self.model:
            cmd += ["--model", self.model]
        return [*cmd, "--disallowedTools", "WebFetch", "WebSearch"]

    def run(self, task: Task, repo: Path, prompt: str, recalled: list[str]) -> RunResult:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        try:
            proc = subprocess.run(
                self.command(),
                cwd=repo,
                input=prompt,  # stdin, so the variadic --disallowedTools cannot eat it
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return RunResult(error=f"timeout after {self.timeout:.0f}s")
        return parse_output(proc.stdout, proc.returncode, proc.stderr)


def parse_output(stdout: str, returncode: int = 0, stderr: str = "") -> RunResult:
    """Read the ``--output-format json`` result object; tolerate missing fields."""
    try:
        data = json.loads(stdout.strip().splitlines()[-1]) if stdout.strip() else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict) or not data:
        tail = (stderr or stdout).strip().splitlines()[-1:] or [f"exit {returncode}"]
        return RunResult(error=tail[0][:200])
    usage = data.get("usage") or {}
    input_tokens = sum(
        usage.get(key) or 0
        for key in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    error = data.get("subtype") if data.get("is_error") or returncode else None
    return RunResult(
        turns=data.get("num_turns"),
        input_tokens=input_tokens if usage else None,
        output_tokens=usage.get("output_tokens"),
        cost_usd=data.get("total_cost_usd"),
        error=error,
    )
