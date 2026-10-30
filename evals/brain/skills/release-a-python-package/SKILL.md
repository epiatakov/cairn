---
id: release-a-python-package
type: skill
title: Release a Python package to PyPI
tags: [python, packaging, release, pypi]
status: active
created: 2026-03-22
updated: 2026-03-22
---

1. Bump the version and update the changelog.
2. Build: `python -m build`, then `twine check dist/*`.
3. Upload to TestPyPI and install from there in a clean virtual environment.
4. Publish to PyPI, preferably with trusted publishing from CI.
5. Tag the release commit and push the tag.
