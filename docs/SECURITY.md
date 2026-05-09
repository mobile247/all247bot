# Security Policy — all247

## Supported Versions

| Version | Supported |
|---|---|
| latest (main branch) | Yes |

---

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

To report a vulnerability, open a [GitHub Security Advisory](https://github.com/your-org/all247/security/advisories/new) on this repository. This keeps the report private until a fix is available.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested mitigations

We aim to acknowledge reports within 48 hours and provide a fix timeline within 7 days for critical issues.

---

## Security Design

- No message content is ever stored or logged.
- All secrets are passed via environment variables — never hardcoded.
- Bot runs as a non-root user inside Docker.
- Minimal Telegram bot permissions requested.
- SQLite database stored in a Docker volume (not in the image).
- No external service dependencies.

---

## Bot Token Compromise

If your `BOT_TOKEN` is compromised (e.g., accidentally committed to git):

**1. Revoke immediately via BotFather:**
```
/mybots → select your bot → API Token → Revoke current token
```
This invalidates the old token instantly. The bot will stop responding to the old token within seconds.

**2. Rotate the token:**
BotFather will issue a new token. Update your `.env` file and redeploy.

**3. If committed to git:**
- Revoke the token *before* anything else — assume it is already compromised.
- Remove it from git history using `git filter-repo` or BFG Repo Cleaner.
- Force-push the cleaned history (coordinate with any collaborators).
- Audit git logs and any CI/CD systems that may have cached the token.

**4. Pre-commit protection:**
Consider using [`git-secrets`](https://github.com/awslabs/git-secrets) or [`truffleHog`](https://github.com/trufflesecurity/trufflehog) to scan for accidental secret commits before they happen.

---

## Known Limitations

- The bot requires Privacy Mode to be disabled in BotFather to function correctly.
  This means the bot can read all group messages (but discards content immediately).
  Group members should be informed that a bot with these permissions is present.
- The member registry contains display names and usernames.
  Operators are responsible for securing their deployment environment.
