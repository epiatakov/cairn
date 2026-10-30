---
id: ssl-certificate-verify-failed-proxy
type: issue
title: CERTIFICATE_VERIFY_FAILED behind a TLS-intercepting proxy
tags: [tls, ssl, proxy, certificates, python, pip]
status: active
created: 2026-03-09
updated: 2026-03-09
---

**Symptom:** `pip`, `requests` or `curl` fail with `[SSL: CERTIFICATE_VERIFY_FAILED]
certificate verify failed: unable to get local issuer certificate`.

**Cause:** a proxy re-signs TLS traffic with its own CA, which is missing from the tool's CA
bundle (`requests` ships its own bundle via `certifi`).

**Workaround:** point each tool at a bundle that includes the proxy CA: `REQUESTS_CA_BUNDLE`,
`SSL_CERT_FILE`, `PIP_CERT`, `NODE_EXTRA_CA_CERTS`, `git config http.sslCAInfo`. Do not
turn verification off.
