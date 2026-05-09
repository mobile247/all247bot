# Technical Specification

## Project: all247

**Version:** 1.2.0  
**Status:** Implementation-ready  
**Based on:** BRD v1 (all247)  
**Date:** 2026-05-08

---

## 1. Overview

`all247` is a single-purpose, privacy-first Telegram bot that implements `@all` (mention-everyone) functionality for Telegram group chats. It is designed for self-hosted deployment via Docker on Ubuntu VPS infrastructure, and is intended for open-source distribution.

> **Important scope note:** The bot can only mention members known to its local registry. It does not have access to Telegram's full group member list at will. Registry coverage depends on passive discovery (members who have sent messages since the bot was added) and manual `/syncmembers` runs. This is a Telegram API constraint, not a bug, and should be communicated clearly to end users.

---

## 2. System Architecture

### 2.1 High-Level Diagram

```
Telegram API
     │
     ▼
┌─────────────────────────────────┐
│           all247 Bot            │
│                                 │
│  ┌─────────────┐                │
│  │  Event      │                │
│  │  Handler    │ ◄── Webhook / Long Polling
│  └──────┬──────┘                │
│         │                       │
│  ┌──────▼──────┐                │
│  │  Command    │                │
│  │  Router     │                │
│  └──────┬──────┘                │
│         │                       │
│  ┌──────▼──────────────────┐    │
│  │  Core Services           │    │
│  │  - GroupService          │    │
│  │  - MemberService         │    │
│  │  - MentionService        │    │
│  │  - RateLimitService      │    │
│  └──────┬───────────────────┘    │
│         │                       │
│  ┌──────▼──────┐                │
│  │  Repository │                │
│  │  Layer      │                │
│  └──────┬──────┘                │
│         │                       │
│  ┌──────▼──────┐                │
│  │   SQLite    │                │
│  └─────────────┘                │
└─────────────────────────────────┘
```

### 2.2 Design Principles

- **Single responsibility** — The bot does one thing: mention all known group members.
- **Privacy-first** — No message content is persisted, logged, or retransmitted outside of Telegram delivery requirements. Content received transiently from the Telegram API is discarded immediately after metadata extraction.
- **No conversational state** — Commands are processed independently without conversational session state. The bot maintains persistent data (groups, members, config, rate limits) but does not track multi-turn interactions or user sessions.
- **Minimal footprint** — Runs on low-spec VPS hardware; no external service dependencies.

---

## 3. Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Rapid development, strong Telegram library ecosystem |
| Bot Framework | `python-telegram-bot` v20+ (async) | Actively maintained, async-native, well-documented |
| Database | SQLite | Zero-config, file-based, suitable for small to medium groups (up to ~a few hundred members, single-server deployment). PostgreSQL migration path reserved for a future high-scale or SaaS release. |
| ORM / Query | `aiosqlite` + raw SQL | Lightweight, no heavy ORM overhead |
| Deployment | Docker + Docker Compose | Consistent, reproducible, self-hostable |
| Base Image | `python:3.11-slim` | Minimal attack surface |
| Config | Environment variables + `.env` | 12-factor app compliant, no hardcoded secrets |

---

## 4. Project Structure

```
all247/
├── bot/
│   ├── __init__.py
│   ├── main.py                  # Entry point, bot init
│   ├── config.py                # Config loader (env vars)
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── command_handlers.py  # /all, /setup, /syncmembers
│   │   └── event_handlers.py    # member join/leave, message events
│   ├── services/
│   │   ├── __init__.py
│   │   ├── group_service.py     # Group activation/config
│   │   ├── member_service.py    # Member registry management
│   │   ├── mention_service.py   # Mention generation + delivery
│   │   └── rate_limit_service.py
│   ├── repository/
│   │   ├── __init__.py
│   │   ├── db.py                # DB connection + migration runner
│   │   ├── group_repo.py
│   │   └── member_repo.py
│   └── utils/
│       ├── __init__.py
│       └── telegram_helpers.py
├── migrations/
│   ├── 001_initial_schema.sql
│   └── 002_rate_limits.sql
├── tests/
│   ├── unit/
│   └── integration/
├── docker/
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── ARCHITECTURE.md
├── PRIVACY.md
└── requirements.txt
```

---

## 5. Database Schema

SQLite is used as the sole persistence layer. No message content is ever written to the database.

### 5.1 `groups` table

```sql
CREATE TABLE IF NOT EXISTS groups (
    group_id        INTEGER PRIMARY KEY,   -- Telegram chat ID
    is_active       INTEGER NOT NULL DEFAULT 0,
    activated_by    INTEGER,               -- Telegram user ID of activating admin
    activated_at    TEXT,                  -- ISO 8601 datetime
    mention_mode    TEXT NOT NULL DEFAULT 'display_name',
    cooldown_seconds INTEGER NOT NULL DEFAULT 0,
    delete_trigger  INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 5.2 `members` table

```sql
CREATE TABLE IF NOT EXISTS members (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        INTEGER NOT NULL REFERENCES groups(group_id),
    user_id         INTEGER NOT NULL,
    display_name    TEXT,
    username        TEXT,
    last_seen_at    TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(group_id, user_id)
);
```

### 5.3 `rate_limit_log` table

```sql
CREATE TABLE IF NOT EXISTS rate_limit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id        INTEGER NOT NULL,
    triggered_by    INTEGER NOT NULL,    -- user_id
    triggered_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Retained only for cooldown enforcement, purged on schedule
```

### 5.4 Explicitly NOT stored

- Message content of any kind
- Command arguments or payloads
- Mention text as sent
- Message IDs beyond transient handling
- Any personally identifiable information beyond Telegram-native user metadata

---

## 6. Bot Commands & Handlers

### 6.1 Command Reference

| Command | Who Can Use | Description |
|---|---|---|
| `/setup` | Group admins only | Activates the bot in the group |
| `/all` | Any group member (configurable) | Mentions all known group members |
| `/syncmembers` | Group admins only | Triggers manual member discovery sync |
| `/config` | Group admins only | View or update group configuration (see §6.6) |
| `/deactivate` | Group admins only | Deactivates the bot in the group |

### 6.2 `/setup` Flow

```
1. Admin sends /setup in group
2. Bot verifies sender is a Telegram group admin (via getChatAdministrators)
3. Bot checks if group already activated
   - If yes: reply "Group already activated."
   - If no: proceed
4. Bot inserts group record with is_active = 1
5. Bot replies with confirmation and brief usage summary
6. No message content from /setup is stored
```

### 6.3 `/all` Flow

```
1. User sends /all in group
2. Bot checks if group is active
   - If not: silently ignore (or reply once, configurable)
3. Bot checks rate limit / cooldown
   - If in cooldown: reply with time remaining, exit
4. Bot fetches active member list from members table
5. Bot generates mention message(s)
6. Bot sends mention message(s) in batches (respecting Telegram limits)
7. If delete_trigger is enabled: bot deletes original /all message
8. Rate limit log entry written (group_id, user_id, timestamp only)
9. Message content is NEVER stored at any point
```

### 6.4 Member Discovery

#### Passive (always on)

The bot registers a message handler that extracts user metadata from any message observed in an active group:

- `user_id` — from `message.from_user.id`
- `display_name` — from `message.from_user.full_name`
- `username` — from `message.from_user.username` (nullable)

This is an upsert operation on `members`. **The message content itself is discarded immediately and never stored.**

**Edited messages are ignored.** The bot does not handle `edited_message` updates and will not refresh `last_seen_at` or trigger any member update on message edits. Only new messages are observed for passive discovery.

**Bot exclusion (mandatory):** Any user with `is_bot = True` in the Telegram user object MUST be excluded from the member registry. Bots must never appear in mention output. This check applies to both passive discovery and `/syncmembers`.

#### Active (on demand)

`/syncmembers` — calls `getChatAdministrators` to enumerate and upsert all current group admins into the member registry. This is the only reliable Telegram Bot API method for proactive member discovery. Full group member enumeration is not available to bots via the Bot API; non-admin members can only be discovered passively through observed messages. Operators should be informed of this limitation so they set accurate expectations with their group.

### 6.5 Inactive Member Strategy

The member registry must not grow unboundedly. The following lifecycle rules apply:

| Event | Action |
|---|---|
| User leaves group (`chat_member` update, status → `left`/`kicked`) | Set `is_active = 0` |
| User rejoins group | Set `is_active = 1`, update `last_seen_at` |
| Deleted Telegram account (user object returns empty) | Set `is_active = 0` |
| Stale members (no activity beyond configurable threshold) | Prunable via admin command or background task |

Only members with `is_active = 1` are included in `/all` mention output.

A configurable `STALE_MEMBER_PRUNE_DAYS` environment variable (default: disabled) allows operators to hard-delete members with no `last_seen_at` activity beyond that threshold. Pruning is non-destructive by default (sets `is_active = 0`; hard delete requires explicit opt-in).

### 6.6 `/config` Command

`/config` uses a simple key-value text syntax. No interactive menus or inline buttons in v1.

**View current config:**
```
/config
```
Bot replies with a formatted summary of all current group settings.

**Update a setting:**
```
/config <key> <value>
```

**Supported keys and values:**

| Key | Valid Values | Default | Description |
|---|---|---|---|
| `cooldown` | Integer ≥ 0 (seconds) | `0` | Seconds between `/all` invocations (0 = disabled) |
| `delete_trigger` | `on` / `off` | `off` | Delete the `/all` message after processing |
| `mention_mode` | `display_name` / `username` | `display_name` | Mention format |

**Examples:**
```
/config cooldown 30
/config delete_trigger on
/config mention_mode username
```

Invalid keys or values receive an error reply listing valid options. Config changes are logged (setting name, old value, new value, changed_by user_id) but never include message content.

---

## 7. Mention Delivery

### 7.1 Mention Modes

| Mode | Format |
|---|---|
| `display_name` (default) | HTML anchor: `<a href="tg://user?id=USER_ID">Display Name</a>` |
| `username` | `@username` plain text (falls back to `display_name` HTML format if no username) |

**Parse mode: HTML is required for all mention messages.** Telegram's MarkdownV2 escaping rules are complex and error-prone, particularly for display names containing special characters. HTML parse mode is safer, more predictable, and easier to maintain.

All `send_message` calls from `MentionService` MUST include `parse_mode="HTML"`. Display names MUST be HTML-escaped before insertion — at minimum: `<` → `&lt;`, `>` → `&gt;`, `&` → `&amp;`. Skipping this step will cause malformed output or Telegram API errors for any user with special characters in their display name. Use Python's `html.escape()` — do not implement escaping manually.

### 7.2 Telegram Message Size & Batching

Telegram enforces a 4096-character message limit. The mention service must batch mentions to stay within this limit.

```python
MAX_MESSAGE_LENGTH = 4000  # conservative limit
BATCH_DELAY_SECONDS = 0.5  # delay between batch messages to avoid flood limits
```

Algorithm:
1. Fetch active members from DB, ordered alphabetically by `display_name` (case-insensitive, `COLLATE NOCASE`)
2. Build list of mention strings in that order
3. Greedily pack mentions into messages up to `MAX_MESSAGE_LENGTH`
4. Send each batch with a delay between sends
5. On `RetryAfter` error from Telegram: sleep for the specified duration and retry

**Mention ordering:** Alphabetical by display name is the defined and stable sort order. This is friendlier to users scanning output and produces consistent, reproducible results across invocations. Insertion order or DB row order must not be relied upon.

### 7.3 Flood Control Handling

```python
# Pseudocode
async def send_with_retry(bot, chat_id, text, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await bot.send_message(chat_id=chat_id, text=text)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramError as e:
            log_error(e)  # log error type only, no message content
            break
```

### 7.4 Internal Abuse Protection

The following hard limits apply at the bot level, independent of any admin-configured cooldown settings. These exist to protect bot stability and Telegram API standing regardless of group configuration.

| Guard | Value | Purpose |
|---|---|---|
| Minimum inter-invocation interval | 3 seconds per group | Prevents rapid-fire `/all` even with cooldown disabled |
| Maximum mention batches per invocation | 10 batches | Caps blast radius for very large registries |
| Maximum retry attempts on `RetryAfter` | 3 | Prevents indefinite retry loops |
| Inter-batch send delay | 500ms | Reduces flood limit risk |
| Active member hard cap | 1000 members | See below |

**Group size hard cap:** If a group's active member count exceeds **1000**, the bot MUST refuse the `/all` invocation and reply with an explanatory message (e.g., _"This group has too many members for /all. Contact your admin."_). This protects both Telegram API standing and bot stability. The cap is defined as a named constant (`MAX_MENTIONABLE_MEMBERS = 1000`) and overridable via environment variable for operators who explicitly accept the risk. The default must remain conservative. This guard applies regardless of admin cooldown settings.

These values are constants in code, not operator-configurable. They represent a safety floor, not a replacement for admin-level cooldown configuration.

---

## 8. Configuration

### 8.1 Environment Variables

All configuration is via environment variables. A `.env.example` is provided for reference.

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | Telegram Bot API token |
| `DB_PATH` | ❌ | `./data/all247.db` | Path to SQLite database file |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level (`INFO`, `WARNING`, `ERROR`) |
| `WEBHOOK_URL` | ❌ | — | If set, use webhook mode; otherwise long polling |
| `WEBHOOK_PORT` | ❌ | `8443` | Port for webhook listener |
| `DEFAULT_COOLDOWN_SECONDS` | ❌ | `0` | Default cooldown for new groups |
| `RATE_LIMIT_PURGE_DAYS` | ❌ | `7` | Days to retain rate limit log entries |

### 8.2 Per-Group Configuration (stored in DB)

| Setting | Type | Default | Description |
|---|---|---|---|
| `mention_mode` | string | `display_name` | Mention format |
| `cooldown_seconds` | integer | `0` | Cooldown between `/all` invocations (0 = disabled) |
| `delete_trigger` | boolean | `false` | Delete the `/all` trigger message after processing |

---

## 9. Logging Policy

This is a hard requirement derived from the BRD privacy mandate.

### 9.1 Allowed Log Events

| Event | Fields Logged |
|---|---|
| Bot startup | timestamp, version |
| Group activated | group_id, activated_by (user_id), timestamp |
| Group deactivated | group_id, deactivated_by (user_id), timestamp |
| `/all` triggered | group_id, triggered_by (user_id), member count, batch count, timestamp |
| Rate limit hit | group_id, triggered_by (user_id), cooldown remaining, timestamp |
| Member upserted | group_id, user_id, timestamp — **DEBUG level only**; disabled at INFO and above to avoid log bloat in active groups |
| Config changed | group_id, changed_by (user_id), setting name, old value, new value, timestamp |
| Telegram API error | error type, group_id, timestamp |
| Unhandled exception | exception class, timestamp (no stack frames containing message data) |

### 9.2 Explicitly Forbidden Log Content

- Message text of any kind
- Command arguments
- Usernames or display names in free-form log lines
- Message IDs beyond internal correlation
- Any content that could be used to reconstruct a conversation

### 9.3 Log Output

Logs are written to stdout/stderr only. No file logging by default. Log rotation is delegated to Docker or the host OS log driver.

---

## 10. Privacy & Security

### 10.1 Data Minimization

- Only Telegram-native identifiers and metadata are persisted.
- No behavioral analytics. No message history. No attachments.
- The rate limit log records only who triggered `/all` and when, for the purpose of enforcing cooldowns. It is purged on a configurable schedule.

### 10.2 Bot Permissions Required

The bot requires the following Telegram permissions in a group:

| Permission | Reason |
|---|---|
| Read messages | Passive member discovery |
| Send messages | Deliver mention responses |
| Delete messages | Optional: delete `/all` trigger message |
| Read group members | `/syncmembers` admin list enumeration |

The bot should **not** request administrator privileges unless necessary.

### 10.3 Secrets Management

- `BOT_TOKEN` and all secrets are passed via environment variables only.
- No secrets are ever committed to the repository.
- `.env` is listed in `.gitignore`.
- `.env.example` contains placeholder values only.

### 10.4 Telegram BotFather Configuration (Required)

By default, Telegram bots run with **Privacy Mode enabled**. In this mode, bots only receive messages that are direct commands (starting with `/`) or messages that explicitly mention the bot. This means:

- Passive member discovery **will fail** in privacy mode — the bot cannot see regular messages and thus cannot capture member metadata from ordinary group activity.
- Slash commands such as `/all` **will still be delivered** to the bot by Telegram even with privacy mode enabled. The member discovery failure is the critical issue, not command detection.

**Privacy Mode MUST be disabled** for `all247` to function correctly.

To configure this in BotFather:

```
1. Open Telegram → @BotFather
2. Send: /mybots
3. Select your all247 bot
4. Bot Settings → Group Privacy → Turn off
```

This must be documented prominently in the `README.md` and setup guide. Operators who skip this step will experience silent failures in member discovery with no obvious error message.

### 10.5 Open Source Considerations

- Repository must pass a secrets scan before publication.
- `SECURITY.md` should be included with responsible disclosure instructions.
- Docker image should be built from a pinned base image digest for reproducibility.
- **License:** MIT is the recommended default for maximum adoption. Apache 2.0 is an acceptable alternative if patent protection clauses are desired. GPL is discouraged as it restricts commercial self-hosted deployments. License must be decided and committed before public repository creation.

---

## 11. Deployment

### 11.1 Docker Compose (recommended)

```yaml
# docker-compose.yml
version: "3.9"

services:
  all247:
    build: .
    restart: unless-stopped
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - DB_PATH=/data/all247.db
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/data
    networks:
      - all247_net

networks:
  all247_net:
    driver: bridge
```

### 11.2 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY migrations/ ./migrations/

RUN useradd -m -u 1000 botuser
USER botuser

CMD ["python", "-m", "bot.main"]
```

### 11.3 Data Volume

The SQLite database file is stored in a Docker volume or host-mounted directory at `/data/`. This directory should be:

- Excluded from version control.
- Backed up at the operator's discretion.
- Writable by the container user.

### 11.4 Polling vs Webhook

| Mode | When to Use |
|---|---|
| Long polling (default) | Simpler setup, no public IP/domain required, suitable for most self-hosted deployments |
| Webhook | When behind a reverse proxy (e.g., nginx), lower latency, required for high-volume deployments |

Set `WEBHOOK_URL` to enable webhook mode.

---

## 12. Error Handling

| Scenario | Behavior |
|---|---|
| Bot not activated in group | Silently ignore `/all`; respond to `/setup` only |
| User not admin on `/setup` | Reply: "Only group administrators can activate this bot." |
| Cooldown active | Reply: "Please wait X seconds before using /all again." |
| No members in registry | Reply: "No members found. Try /syncmembers first." |
| Telegram `RetryAfter` | Sleep and retry up to 3 times with exponential backoff |
| DB write failure | Log error (no message content), reply: "An internal error occurred." |
| Unhandled exception | Log exception class and timestamp, do not expose details to users |

---

## 13. Testing Strategy

### 13.1 Unit Tests

- `MentionService` — batching logic, mention format generation
- `RateLimitService` — cooldown enforcement logic
- `MemberService` — upsert logic, deduplication
- `GroupService` — activation state transitions

### 13.2 Integration Tests

- Full `/setup` → `/all` flow against a test SQLite instance
- Member passive discovery pipeline
- Batch send simulation with mock Telegram API

### 13.3 Privacy Verification

- Automated log output scanning to assert no message content appears in any log line
- DB schema audit to assert no message content columns exist

---

## 14. Future Extensibility Points

The following are **not** in scope for v1 but the architecture should not preclude them:

- Role-based `/all` restrictions (allow only admins, or a defined role)
- Subgroup mentions (e.g., `/all @devs`)
- Multiple trigger commands per group
- Web admin interface
- SaaS multi-tenant hosting
- Telemetry (opt-in only, disabled by default)

---

## 15. Open Questions / Decisions Pending

| # | Question | Status |
|---|---|---|
| 1 | Webhook vs long polling as the default for Docker deployment? | Defaulting to long polling for simplicity |
| 2 | Should `/all` work in channels or only in groups? | Groups only for v1 |
| 3 | Rate limit log purge: cron job inside container or external? | Internal async task on bot startup |
| 4 | Should mention message be sent as a reply to the trigger message? | Configurable; default is reply |
| 5 | License selection: MIT vs Apache 2.0? | Pending decision before OSS publication |

---

## 16. Glossary

| Term | Definition |
|---|---|
| Activation | The process by which a group admin enables bot functionality for their group |
| Member registry | The set of known members for a group, built through passive and active discovery |
| Mention | A Telegram inline link or @username reference that notifies a user |
| Trigger message | The `/all` message sent by a user to invoke mention behavior |
| Cooldown | A minimum wait period between successive `/all` invocations |
| Passive discovery | Capturing user metadata from observed messages without storing message content |
| Flood protection | Handling Telegram API rate limits to ensure message delivery stability |

---

*This document is locked at v1.2.0 and is ready for implementation. Updates should reflect real-world discoveries during development.*
