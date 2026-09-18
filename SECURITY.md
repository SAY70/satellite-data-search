# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report privately through GitHub's [private vulnerability reporting](https://github.com/SAY70/satellite-data-search/security/advisories/new) (Security tab → Report a vulnerability). If that isn't available to you, contact the maintainer directly through their GitHub profile.

Please include what the issue is, how to reproduce it, and what an attacker could do with it. You can expect an initial response within a couple of weeks — this is a research tool maintained by one person, not a commercial product with an on-call rotation.

## Supported versions

Only the current `main` branch is maintained. There are no long-term support branches.

## How this project handles your credentials

This toolkit talks to three services that require credentials. None of them are ever written to disk by this code:

| Credential | How it's collected | Where it lives |
|---|---|---|
| **Google Earth Engine** | Browser OAuth (`auth_mode="localhost"`) | Cached by the `earthengine-api` library in its own credentials file, outside this repo |
| **NASA Earthdata** | `getpass` prompt in notebooks, masked field in the app | In memory for that run only |
| **GitHub token** | `getpass` prompt, masked field, or `GITHUB_TOKEN` env var | In memory for that run only |

Specific measures worth knowing about:

- **The GitHub token is never written to `.git/config`.** The `origin` remote is stored without credentials; the token is passed as a one-off argument to a single `git push` call.
- **Git command output is scrubbed.** If a push fails, the error message has the token replaced with `***` before it's displayed or raised, so it can't end up saved in notebook output.
- **`downloads/` is gitignored** and never pushed. A manifest of filenames and sizes is committed instead.

## If you're contributing or forking

- Never hardcode credentials in a notebook cell. Notebook outputs are saved to disk and committed — a password typed into a cell will end up in git history.
- If you accidentally commit a credential, **rotate it immediately** (revoke the token, change the password). Removing it from git history is not sufficient on its own, since the value may already have been fetched, cached, or indexed.
- Be aware that your AOI files (`output/*.geojson`, `.kml`, `.kmz`) contain real-world coordinates. If your study site is sensitive, don't commit them to a public repository.

## Scope

Vulnerabilities in this project's own code are in scope. Issues in upstream dependencies (`earthengine-api`, `asf_search`, `streamlit`, `folium`, etc.) should be reported to those projects directly, though we're glad to hear about them so we can pin or work around affected versions.
