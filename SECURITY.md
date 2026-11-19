# Security policy

## What counts as a vulnerability

Mock-Box is a testing tool and is deliberately permissive. These are **features, not bugs**:

- any Basic username and password is accepted;
- anyone can issue API keys, JWTs and OAuth tokens;
- custom routes and payment webhooks do what their configuration says.

Please do report anything that matters even for a local testing tool, for example:

- running code or reading/writing files on the host through an HTTP request or a mocks file;
- bypassing the admin API key;
- leaking the configured `secret_key` or admin keys;
- a crash or hang that one request can cause (beyond the documented `?delay` limits).

## Supported versions

Only the latest release receives fixes.

## Reporting

Report vulnerabilities privately through GitHub:
**[Report a vulnerability](https://github.com/TgkCapture/mock-box/security/advisories/new)**
(the *Security* tab, then *Report a vulnerability*). Please don't open a public issue.

Include the Mock-Box version, how you run it (pip or Docker) and steps to reproduce. You should
get a reply within a week. Once a fix is released you'll be credited in the advisory unless you
prefer otherwise.
