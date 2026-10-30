"""Scripted agent tasks. Each one is built around a pitfall that ``evals/brain`` documents.

A task is a throwaway repository (``files``), a prompt, and a deterministic ``check`` that
inspects the repository afterwards. ``check`` reports two things:

- ``passed``: the task is done and the fix is the durable one.
- ``pitfall``: the final state still shows the known failure the brain warns about, for
  example a separate ``RUN apt-get update`` layer or a ``.gitignore``-only "untrack".

``solve`` and ``naive`` are reference edits: what an agent that recalled the entry would do,
and a plausible fix that repeats the known failure. The mock runner uses them, and the tests
use them to prove every checker can tell the two apart.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

GIT = ["git", "-c", "user.name=cairn-eval", "-c", "user.email=eval@example.invalid"]


@dataclass(frozen=True)
class Outcome:
    passed: bool
    pitfall: bool
    detail: str = ""


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    files: dict[str, str]
    brain_ids: tuple[str, ...]
    check: Callable[[Path], Outcome]
    solve: Callable[[Path], None]
    naive: Callable[[Path], None]
    executable: tuple[str, ...] = field(default=())

    def setup(self, repo: Path) -> None:
        """Write the files and commit them, so the agent starts from a clean git repo."""
        repo.mkdir(parents=True, exist_ok=True)
        for rel, text in self.files.items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8", newline="") as fh:
                fh.write(text)
        for rel in self.executable:
            (repo / rel).chmod(0o755)
        run(["git", "init", "-q", "-b", "main"], repo)
        run(["git", "add", "-A"], repo)
        run([*GIT, "commit", "-q", "-m", "Initial commit"], repo)


def run(
    cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: float = 30
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def python(code: str, repo: Path, env: dict[str, str] | None = None) -> str:
    """Run ``code`` with the repo as the import root; return stdout or raise on failure."""
    proc = run([sys.executable, "-c", code], repo, env)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip().splitlines()[-1] if proc.stderr else "failed")
    return proc.stdout.strip()


def read(repo: Path, rel: str) -> str:
    path = repo / rel
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def edit(repo: Path, rel: str, old: str, new: str) -> None:
    text = read(repo, rel)
    assert old in text, f"{rel}: {old!r} not found"
    write(repo, rel, text.replace(old, new, 1))


# -- 1. CRLF shebang ----------------------------------------------------------


def _crlf_check(repo: Path) -> Outcome:
    script = repo / "scripts/build.sh"
    if not script.exists():
        return Outcome(False, True, "scripts/build.sh is gone")
    attrs = read(repo, ".gitattributes")
    rule = re.search(r"^\s*(\*|\*\.sh|\S*\.sh)\s.*eol=lf", attrs, re.MULTILINE)
    has_cr = b"\r" in script.read_bytes()
    proc = run(["bash", "-c", "./scripts/build.sh"], repo)
    works = proc.returncode == 0 and "build ok" in proc.stdout
    pitfall = has_cr or not rule
    detail = f"cr={has_cr} eol_rule={bool(rule)} runs={works}"
    return Outcome(works and not pitfall, pitfall, detail)


def _crlf_solve(repo: Path) -> None:
    _crlf_naive(repo)
    write(repo, ".gitattributes", "*.sh text eol=lf\n")


def _crlf_naive(repo: Path) -> None:
    write(repo, "scripts/build.sh", read(repo, "scripts/build.sh").replace("\r\n", "\n"))


# -- 2. ripgrep glob in a .bat file ------------------------------------------

_RG_FILTER = re.compile(r'(-g|--glob)(\s+|=)("\*\.py"|\*\.py\b)|(-t|--type)(\s+|=)py\b')


def _rg_check(repo: Path) -> Outcome:
    text = read(repo, "tools/list_python.bat")
    lines = [line for line in text.splitlines() if re.match(r"\s*rg\b", line)]
    if not lines:
        return Outcome(False, False, "no rg command left")
    pitfall = any(re.search(r"'[^']*\*[^']*'", line) for line in lines)
    ok = any(_RG_FILTER.search(line) and "src" in line for line in lines)
    return Outcome(ok and not pitfall, pitfall, lines[0].strip())


def _rg_solve(repo: Path) -> None:
    edit(repo, "tools/list_python.bat", "-g '*.py'", '-g "*.py"')


def _rg_naive(repo: Path) -> None:
    edit(repo, "tools/list_python.bat", "-g '*.py'", "-g '**/*.py'")


# -- 3. npm lockfile out of sync ---------------------------------------------


def _npm_check(repo: Path) -> Outcome:
    try:
        manifest = json.loads(read(repo, "package.json"))
        lock = json.loads(read(repo, "package-lock.json"))
    except json.JSONDecodeError as exc:
        return Outcome(False, False, f"invalid JSON: {exc}")
    deps = manifest.get("dependencies", {})
    packages = lock.get("packages", {})
    in_sync = (
        "is-odd" in deps
        and packages.get("", {}).get("dependencies") == deps
        and all(f"node_modules/{name}" in packages for name in deps)
    )
    ci = read(repo, ".github/workflows/ci.yml")
    pitfall = "npm ci" not in ci
    return Outcome(in_sync and not pitfall, pitfall, f"in_sync={in_sync} npm_ci={not pitfall}")


def _npm_solve(repo: Path) -> None:
    lock = json.loads(read(repo, "package-lock.json"))
    lock["packages"][""]["dependencies"]["is-odd"] = "^3.0.1"
    lock["packages"]["node_modules/is-odd"] = {
        "version": "3.0.1",
        "resolved": "https://registry.npmjs.org/is-odd/-/is-odd-3.0.1.tgz",
        "dependencies": {"is-number": "^6.0.0"},
    }
    lock["packages"]["node_modules/is-number"] = {
        "version": "6.0.0",
        "resolved": "https://registry.npmjs.org/is-number/-/is-number-6.0.0.tgz",
    }
    write(repo, "package-lock.json", json.dumps(lock, indent=2) + "\n")


def _npm_naive(repo: Path) -> None:
    edit(repo, ".github/workflows/ci.yml", "npm ci", "npm install")


_NPM_LOCK = {
    "name": "shop-frontend",
    "version": "1.0.0",
    "lockfileVersion": 3,
    "requires": True,
    "packages": {
        "": {
            "name": "shop-frontend",
            "version": "1.0.0",
            "dependencies": {"left-pad": "^1.3.0"},
        },
        "node_modules/left-pad": {
            "version": "1.3.0",
            "resolved": "https://registry.npmjs.org/left-pad/-/left-pad-1.3.0.tgz",
        },
    },
}

# -- 4. 64-bit ids in JSON ---------------------------------------------------

_BIG_ID = 2**63 - 25


def _json_check(repo: Path) -> Outcome:
    code = (
        "import json; from api.serialize import to_json; "
        f"print(json.dumps(json.loads(to_json({{'id': {_BIG_ID}, 'name': 'a'}}))['id']))"
    )
    try:
        value = json.loads(python(code, repo))
    except (RuntimeError, json.JSONDecodeError) as exc:
        return Outcome(False, False, f"error: {exc}")
    pitfall = isinstance(value, int) and abs(value) > 2**53
    return Outcome(value == str(_BIG_ID), pitfall, f"id={value!r}")


def _json_solve(repo: Path) -> None:
    edit(repo, "api/serialize.py", '"id": user["id"]', '"id": str(user["id"])')


def _json_naive(repo: Path) -> None:
    edit(repo, "api/serialize.py", '"id": user["id"]', '"id": int(user["id"])')


# -- 5. SQLite database is locked --------------------------------------------


def _sqlite_check(repo: Path) -> Outcome:
    code = (
        "import tempfile, os; from app.db import connect; "
        "c = connect(os.path.join(tempfile.mkdtemp(), 'x.db')); "
        "print(c.execute('PRAGMA journal_mode').fetchone()[0])"
    )
    try:
        mode = python(code, repo).lower()
    except RuntimeError as exc:
        return Outcome(False, False, f"error: {exc}")
    return Outcome(mode == "wal", mode != "wal", f"journal_mode={mode}")


def _sqlite_solve(repo: Path) -> None:
    edit(
        repo,
        "app/db.py",
        "    return sqlite3.connect(path)\n",
        "    conn = sqlite3.connect(path, timeout=5)\n"
        '    conn.execute("PRAGMA journal_mode=WAL")\n'
        "    return conn\n",
    )


def _sqlite_naive(repo: Path) -> None:
    edit(repo, "app/db.py", "sqlite3.connect(path)", "sqlite3.connect(path, timeout=30)")


# -- 6. venv layout on Windows -----------------------------------------------


def _venv_check(repo: Path) -> Outcome:
    code = (
        "from pathlib import PurePosixPath as P; from scripts.venv_python import venv_python; "
        "print(venv_python(P('.venv'), 'nt').as_posix()); "
        "print(venv_python(P('.venv'), 'posix').as_posix())"
    )
    try:
        nt, posix = python(code, repo).splitlines()
    except (RuntimeError, ValueError) as exc:
        return Outcome(False, False, f"error: {exc}")
    ok = nt.lower() in (".venv/scripts/python.exe", ".venv/scripts/python") and posix in (
        ".venv/bin/python",
        ".venv/bin/python3",
    )
    return Outcome(ok, "/bin/" in nt, f"nt={nt} posix={posix}")


def _venv_solve(repo: Path) -> None:
    edit(
        repo,
        "scripts/venv_python.py",
        '    return venv / "bin" / "python"',
        '    if os_name == "nt":\n'
        '        return venv / "Scripts" / "python.exe"\n'
        '    return venv / "bin" / "python"',
    )


def _venv_naive(repo: Path) -> None:
    edit(
        repo,
        "scripts/venv_python.py",
        '    return venv / "bin" / "python"',
        '    return venv / "bin" / ("python.exe" if os_name == "nt" else "python")',
    )


# -- 7. YAML Norway problem --------------------------------------------------


def _yaml_check(repo: Path) -> Outcome:
    text = "\n".join(
        line.split("#", 1)[0] for line in read(repo, "config/countries.yaml").split("\n")
    )
    bare_no = re.search(r"""(?<![\w"'])NO(?![\w"'])""", text)
    quoted_no = re.search(r"""["']NO["']""", text)
    others = all(re.search(rf"\b{code}\b", text) for code in ("SE", "DK", "FI"))
    return Outcome(
        bool(quoted_no) and not bare_no and others, bool(bare_no), f"bare_NO={bool(bare_no)}"
    )


def _yaml_solve(repo: Path) -> None:
    edit(repo, "config/countries.yaml", "  - NO\n", '  - "NO"\n')


def _yaml_naive(repo: Path) -> None:
    text = read(repo, "config/countries.yaml")
    text = re.sub(r"countries:\n(  - \w+\n)+", "countries: [SE, NO, DK, FI]\n", text)
    write(repo, "config/countries.yaml", text)


# -- 8. Dockerfile apt-get update layer --------------------------------------


def _docker_runs(repo: Path) -> list[str]:
    text = read(repo, "Dockerfile").replace("\\\n", " ")
    return [line for line in text.splitlines() if re.match(r"\s*RUN\b", line)]


def _docker_check(repo: Path) -> Outcome:
    runs = _docker_runs(repo)
    pitfall = any("apt-get update" in r and "apt-get install" not in r for r in runs)
    combined = any(
        "apt-get update" in r and "apt-get install" in r and "jq" in r and "curl" in r for r in runs
    )
    return Outcome(combined and not pitfall, pitfall, f"runs={len(runs)}")


def _docker_solve(repo: Path) -> None:
    edit(
        repo,
        "Dockerfile",
        "RUN apt-get update\nRUN apt-get install -y curl\n",
        "RUN apt-get update && apt-get install -y curl jq && rm -rf /var/lib/apt/lists/*\n",
    )


def _docker_naive(repo: Path) -> None:
    edit(repo, "Dockerfile", "apt-get install -y curl", "apt-get install -y curl jq")


# -- 9. bash pipeline hides a failed download --------------------------------


def _pipefail_check(repo: Path) -> Outcome:
    stub = repo / ".eval-bin"
    stub.mkdir(exist_ok=True)
    (stub / "curl").write_text("#!/bin/sh\necho 'curl: (22) 404' >&2\nexit 22\n", encoding="utf-8")
    (stub / "curl").chmod(0o755)
    try:
        env = {"PATH": f"{stub}{os.pathsep}{os.environ['PATH']}", "RELEASE_URL": "https://x"}
        proc = run(["bash", "deploy.sh"], repo, env)
    finally:
        shutil.rmtree(stub, ignore_errors=True)
    reported = "deployed" in proc.stdout
    return Outcome(proc.returncode != 0 and not reported, reported, f"rc={proc.returncode}")


def _pipefail_solve(repo: Path) -> None:
    edit(repo, "deploy.sh", "set -e\n", "set -euo pipefail\n")


def _pipefail_naive(repo: Path) -> None:
    edit(repo, "deploy.sh", "> /dev/null\n", "> /dev/null || exit 1\n")


# -- 10. utcnow().timestamp() -------------------------------------------------


def _utc_check(repo: Path) -> Outcome:
    code = "import time; from auth.tokens import expires_at; print(expires_at(30) - time.time())"
    deltas = []
    for tz in ("EST+5", "JST-9", "UTC0"):
        try:
            deltas.append(float(python(code, repo, {"TZ": tz})))
        except (RuntimeError, ValueError) as exc:
            return Outcome(False, False, f"TZ={tz}: {exc}")
    ok = all(abs(d - 1800) < 60 for d in deltas)
    pitfall = any(abs(d - 1800) >= 3600 for d in deltas)
    return Outcome(ok, pitfall, "deltas=" + ",".join(f"{d:.0f}" for d in deltas))


def _utc_solve(repo: Path) -> None:
    edit(
        repo,
        "auth/tokens.py",
        "from datetime import datetime, timedelta",
        "from datetime import datetime, timedelta, timezone",
    )
    edit(repo, "auth/tokens.py", "datetime.utcnow()", "datetime.now(timezone.utc)")


def _utc_naive(repo: Path) -> None:
    edit(repo, "auth/tokens.py", "from datetime import", "import time\nfrom datetime import")
    edit(
        repo,
        "auth/tokens.py",
        "return (datetime.utcnow() + timedelta(minutes=ttl_minutes)).timestamp()",
        "return time.mktime(datetime.utcnow().timetuple()) + ttl_minutes * 60",
    )


# -- 11. .gitignore does not untrack -----------------------------------------


def _git_check(repo: Path) -> Outcome:
    tracked = bool(run(["git", "ls-files", "config/local.env"], repo).stdout.strip())
    ignored = (
        run(["git", "check-ignore", "-q", "--no-index", "config/local.env"], repo).returncode == 0
    )
    exists = (repo / "config/local.env").exists()
    detail = f"tracked={tracked} ignored={ignored} exists={exists}"
    return Outcome(not tracked and ignored and exists, tracked, detail)


def _git_solve(repo: Path) -> None:
    _git_naive(repo)
    run(["git", "rm", "-q", "--cached", "config/local.env"], repo)


def _git_naive(repo: Path) -> None:
    write(repo, ".gitignore", read(repo, ".gitignore") + "config/local.env\n")


# -- 12. Makefile recipes indented with spaces --------------------------------


def _make_check(repo: Path) -> Outcome:
    if shutil.which("make"):
        proc = run(["make", "-n", "test"], repo)
        ok = proc.returncode == 0 and "pytest" in proc.stdout
        pitfall = "missing separator" in proc.stderr
        return Outcome(ok, pitfall, f"rc={proc.returncode}")
    recipes = re.findall(r"^(\s+)\S", read(repo, "Makefile"), re.MULTILINE)
    pitfall = any(not r.startswith("\t") for r in recipes)
    return Outcome(bool(recipes) and not pitfall, pitfall, "checked without make")


def _make_solve(repo: Path) -> None:
    write(repo, "Makefile", read(repo, "Makefile").replace("    ", "\t"))


def _make_naive(repo: Path) -> None:
    write(repo, "Makefile", read(repo, "Makefile").replace("    ", "        "))


# -- 13. locale-dependent sort -----------------------------------------------


def _sort_check(repo: Path) -> Outcome:
    script = read(repo, "gen_manifest.sh")
    pinned = re.search(r"\bLC_(ALL|COLLATE)=C\b", script)
    proc = run(["bash", "gen_manifest.sh"], repo)
    lines = read(repo, "MANIFEST.txt").splitlines()
    byte_sorted = bool(lines) and lines == sorted(lines, key=lambda s: s.encode())
    ok = proc.returncode == 0 and bool(pinned) and byte_sorted
    return Outcome(ok, not pinned, f"pinned={bool(pinned)} byte_sorted={byte_sorted}")


def _sort_solve(repo: Path) -> None:
    edit(repo, "gen_manifest.sh", "| sort >", "| LC_ALL=C sort >")


def _sort_naive(repo: Path) -> None:
    edit(repo, "gen_manifest.sh", "| sort >", "| sort -f >")


TASKS: list[Task] = [
    Task(
        id="crlf-shebang",
        prompt=(
            "In our Linux CI container, `./scripts/build.sh` fails with "
            "`/usr/bin/env: 'bash\\r': No such file or directory`. Fix it, and make sure it "
            "does not come back."
        ),
        files={"scripts/build.sh": "#!/usr/bin/env bash\r\nset -eu\r\necho build ok\r\n"},
        executable=("scripts/build.sh",),
        brain_ids=("shell-script-bad-interpreter-crlf", "git-autocrlf-rewrites-line-endings"),
        check=_crlf_check,
        solve=_crlf_solve,
        naive=_crlf_naive,
    ),
    Task(
        id="rg-glob-bat",
        prompt=(
            "`tools\\list_python.bat` should list the Python files under `src`, but on "
            "Windows it prints nothing. Fix the script."
        ),
        files={
            "tools/list_python.bat": "@echo off\r\nrg --files -g '*.py' src\r\n",
            "src/app.py": "print('hello')\n",
        },
        brain_ids=("ripgrep-glob-single-quotes-windows",),
        check=_rg_check,
        solve=_rg_solve,
        naive=_rg_naive,
    ),
    Task(
        id="npm-lockfile",
        prompt=(
            "CI fails at `npm ci` with `npm ci can only install packages when your "
            "package.json and package-lock.json are in sync` and "
            "`Missing: is-odd@^3.0.1 from lock file`. Fix the build."
        ),
        files={
            "package.json": json.dumps(
                {
                    "name": "shop-frontend",
                    "version": "1.0.0",
                    "dependencies": {"is-odd": "^3.0.1", "left-pad": "^1.3.0"},
                },
                indent=2,
            )
            + "\n",
            "package-lock.json": json.dumps(_NPM_LOCK, indent=2) + "\n",
            ".github/workflows/ci.yml": (
                "name: CI\non: [push]\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
                "    steps:\n      - uses: actions/checkout@v4\n      - run: npm ci\n"
                "      - run: npm test\n"
            ),
        },
        brain_ids=("npm-ci-lockfile-out-of-sync", "npm-ci-out-of-sync-lockfile"),
        check=_npm_check,
        solve=_npm_solve,
        naive=_npm_naive,
    ),
    Task(
        id="json-bigint",
        prompt=(
            "Our web frontend sometimes opens the wrong user's profile. User ids are 64-bit "
            "integers from the database. The API serializes users in `api/serialize.py`; "
            "fix the problem there."
        ),
        files={
            "api/__init__.py": "",
            "api/serialize.py": (
                "import json\n\n\ndef to_json(user: dict) -> str:\n"
                '    """Serialize a user record for the web client."""\n'
                '    return json.dumps({"id": user["id"], "name": user["name"]})\n'
            ),
        },
        brain_ids=("json-large-integers-lose-precision-in-javascript",),
        check=_json_check,
        solve=_json_solve,
        naive=_json_naive,
    ),
    Task(
        id="sqlite-locked",
        prompt=(
            "A background worker writes to our SQLite database while the web app reads from "
            "it, and reads intermittently fail with `sqlite3.OperationalError: database is "
            "locked`. Connections are opened in `app/db.py`. Fix it."
        ),
        files={
            "app/__init__.py": "",
            "app/db.py": (
                "import sqlite3\n\n\ndef connect(path: str) -> sqlite3.Connection:\n"
                "    return sqlite3.connect(path)\n"
            ),
        },
        brain_ids=("sqlite-database-is-locked", "sqlite-wal-mode-concurrency"),
        check=_sqlite_check,
        solve=_sqlite_solve,
        naive=_sqlite_naive,
    ),
    Task(
        id="venv-windows",
        prompt=(
            "`scripts/run_tests.py` cannot find the virtual environment's interpreter on "
            "Windows. Fix `venv_python` in `scripts/venv_python.py` and keep its signature."
        ),
        files={
            "scripts/__init__.py": "",
            "scripts/venv_python.py": (
                "from pathlib import Path\n\n\n"
                "def venv_python(venv: Path, os_name: str) -> Path:\n"
                '    """The interpreter inside ``venv`` for ``os.name`` ("posix" or "nt")."""\n'
                '    return venv / "bin" / "python"\n'
            ),
            "scripts/run_tests.py": (
                "import os\nimport subprocess\nfrom pathlib import Path\n\n"
                "from venv_python import venv_python\n\n"
                'subprocess.run([venv_python(Path(".venv"), os.name), "-m", "pytest"], '
                "check=True)\n"
            ),
        },
        brain_ids=("python-venv-layout-differs-on-windows",),
        check=_venv_check,
        solve=_venv_solve,
        naive=_venv_naive,
    ),
    Task(
        id="yaml-norway",
        prompt=(
            "The shipping service says Norway is not in the list of countries we ship to, "
            "but it is in `config/countries.yaml`. The service loads that file with PyYAML. "
            "Fix it."
        ),
        files={
            "config/countries.yaml": (
                "# ISO 3166 codes of the countries we ship to\n"
                "countries:\n  - SE\n  - NO\n  - DK\n  - FI\ndefault: SE\n"
            ),
        },
        brain_ids=("yaml-norway-problem",),
        check=_yaml_check,
        solve=_yaml_solve,
        naive=_yaml_naive,
    ),
    Task(
        id="docker-apt",
        prompt="Add `jq` next to `curl` in the packages installed by the Dockerfile.",
        files={
            "Dockerfile": (
                "FROM debian:bookworm-slim\nRUN apt-get update\nRUN apt-get install -y curl\n"
                'COPY . /app\nCMD ["/app/run.sh"]\n'
            ),
        },
        brain_ids=("docker-apt-get-update-cache",),
        check=_docker_check,
        solve=_docker_solve,
        naive=_docker_naive,
    ),
    Task(
        id="bash-pipefail",
        prompt=(
            "`deploy.sh` printed `deployed` even though downloading the release failed. Make "
            "the script stop with a non-zero exit code when the download fails."
        ),
        files={
            "deploy.sh": (
                "#!/usr/bin/env bash\nset -e\n\n"
                'fetch() { curl -fsS "$RELEASE_URL"; }\n\n'
                "fetch | tee release.tar.gz > /dev/null\n"
                'echo "deployed"\n'
            ),
        },
        executable=("deploy.sh",),
        brain_ids=("bash-pipeline-exit-status",),
        check=_pipefail_check,
        solve=_pipefail_solve,
        naive=_pipefail_naive,
    ),
    Task(
        id="utcnow-expiry",
        prompt=(
            "Tokens issued on developer laptops expire at the wrong time, but in CI they are "
            "fine. `auth/tokens.py` computes the expiry. Fix it."
        ),
        files={
            "auth/__init__.py": "",
            "auth/tokens.py": (
                "from datetime import datetime, timedelta\n\n\n"
                "def expires_at(ttl_minutes: int = 30) -> float:\n"
                '    """Unix timestamp at which a token issued now expires."""\n'
                "    return (datetime.utcnow() + timedelta(minutes=ttl_minutes)).timestamp()\n"
            ),
        },
        brain_ids=("token-expiry-wrong-outside-utc", "python-datetime-utcnow-naive"),
        check=_utc_check,
        solve=_utc_solve,
        naive=_utc_naive,
    ),
    Task(
        id="git-untrack",
        prompt=(
            "`config/local.env` holds per-developer settings and should not be in the "
            "repository, but everyone's edits to it keep showing up in `git status`. Fix that "
            "without deleting anyone's local copy."
        ),
        files={
            "config/local.env": "API_URL=http://localhost:8000\nDEBUG=1\n",
            "app.py": "print('app')\n",
            ".gitignore": "__pycache__/\n",
        },
        brain_ids=("gitignore-does-not-untrack-files",),
        check=_git_check,
        solve=_git_solve,
        naive=_git_naive,
    ),
    Task(
        id="makefile-tabs",
        prompt="`make test` fails with `Makefile:4: *** missing separator.  Stop.` Fix it.",
        files={
            "Makefile": (
                ".PHONY: lint test\n\nlint:\n    ruff check .\n\ntest:\n    python -m pytest -q\n"
            ),
        },
        brain_ids=("makefile-missing-separator",),
        check=_make_check,
        solve=_make_solve,
        naive=_make_naive,
    ),
    Task(
        id="sort-locale",
        prompt=(
            "`MANIFEST.txt` generated by `gen_manifest.sh` comes out in a different order on "
            "CI than on my laptop, so the CI diff check keeps failing. Make the order the same "
            "everywhere."
        ),
        files={
            "gen_manifest.sh": (
                "#!/usr/bin/env bash\nset -euo pipefail\n"
                "find assets -type f | sort > MANIFEST.txt\n"
            ),
            "assets/Banner.png": "",
            "assets/about.txt": "",
            "assets/_draft.md": "",
            "assets/zeta.css": "",
        },
        executable=("gen_manifest.sh",),
        brain_ids=("sort-order-depends-on-locale",),
        check=_sort_check,
        solve=_sort_solve,
        naive=_sort_naive,
    ),
]


def get(task_id: str) -> Task:
    for task in TASKS:
        if task.id == task_id:
            return task
    raise KeyError(task_id)
