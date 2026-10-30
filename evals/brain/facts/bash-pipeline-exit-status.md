---
id: bash-pipeline-exit-status
type: fact
title: A bash pipeline's exit status is the last command's unless pipefail is set
tags: [bash, shell, pipefail, errors]
status: active
created: 2026-02-18
updated: 2026-02-18
---

`set -e` stops a script when a command fails, but a pipeline only reports the status of its
last command. In `curl -fsS "$URL" | tee release.tar.gz`, a failed download is hidden because
`tee` succeeds, and the script carries on.

Start scripts with `set -euo pipefail`. Inside a script, `${PIPESTATUS[@]}` holds the status
of every command of the last pipeline.
