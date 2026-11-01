# Security policy

## Supported versions

Only the latest release of cairn receives fixes.

## Reporting a vulnerability

Please report security problems privately through GitHub's
[private vulnerability reporting](https://github.com/epiatakov/cairn/security/advisories/new)
rather than in a public issue. Include the cairn version, your OS, and steps to reproduce.
You should get a reply within a week.

Things that count as security issues here include: a hook command that can be made to run
something other than `cairn`, `cairn install`/`uninstall`/`skills` writing or deleting files
outside the files they document, and path traversal from entry ids or skill names.

cairn reads and writes local files only and makes no network calls. Treat a brain like code:
its entries are injected into agent prompts, so only use brains you trust.
