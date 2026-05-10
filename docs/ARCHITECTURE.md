# all247 — Architecture

## System Overview

```
Telegram API
     │
     ▼
┌─────────────────────────────────┐
│           all247 Bot            │
│                                 │
│  ┌─────────────┐                │
│  │  Event      │                │
│  │  Handler    │ ◄── Long Polling / Webhook
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

## Key Design Principles

- **Single responsibility** — one job: mention all known group members.
- **Privacy-first** — no message content persisted, logged, or retransmitted.
- **No conversational state** — commands processed independently.
- **Minimal footprint** — runs on low-spec VPS, no external dependencies.

## Component Responsibilities

| Component | Responsibility |
|---|---|
| `config.py` | Load and validate all configuration from environment variables |
| `repository/db.py` | DB connection, migration runner |
| `repository/group_repo.py` | SQL for groups table |
| `repository/member_repo.py` | SQL for members table |
| `services/group_service.py` | Group activation/config business logic |
| `services/member_service.py` | Member registry management |
| `services/mention_service.py` | Mention building, batching, delivery |
| `services/rate_limit_service.py` | Cooldown enforcement, rate_limit_log |
| `handlers/command_handlers.py` | /setup /all /syncmembers /config /deactivate |
| `handlers/event_handlers.py` | Passive discovery, join/leave events |
| `utils/telegram_helpers.py` | Admin check, mention string builders |

## Architecture Decisions

| ADR | Decision | Rationale |
|---|---|---|
| ADR-001 | Python 3.11 + python-telegram-bot v20 (async) | Async-native, actively maintained, strong ecosystem |
| ADR-002 | SQLite + aiosqlite + raw SQL | Zero-config, no ORM overhead, sufficient for v1 scale |
| ADR-003 | Long polling default, webhook optional | Simpler self-hosted setup, no public IP required |
| ADR-004 | HTML parse mode for mentions | Safer than MarkdownV2 for display names with special chars |
| ADR-005 | No file logging — stdout/stderr only | Delegate log rotation to Docker/host OS |
| ADR-006 | MIT License | Maximum adoption, no copyleft restrictions |
| ADR-007 | Alphabetical mention order (COLLATE NOCASE) | Consistent, reproducible, user-friendly |
| ADR-008 | Hard cap: MAX_MENTIONABLE_MEMBERS=1000 | Protect Telegram API standing + bot stability |
| ADR-009 | rate_limit_log stores group_id + timestamp only | Cooldown is per-group; triggered_by user_id would be over-collection |
| ADR-010 | restrict_all_to_admins config option (default: off) | Low-effort v1 addition; avoids breaking schema change later |
| ADR-011 | delete_trigger failure replies with warning, not silent fail | Detectable failure is better than invisible — BRD minimal-access preserved |
| ADR-012 | Docker HEALTHCHECK via heartbeat file | Catches stuck-but-alive process; no external deps |
| ADR-013 | SQLite WAL mode enabled on every connection | Eliminates database-is-locked under concurrent async writes |

## Hard Limits (not operator-configurable)

| Guard | Value | Purpose |
|---|---|---|
| Minimum inter-invocation interval | 3 seconds/group | Prevent rapid-fire /all |
| Maximum mention batches per invocation | 10 | Cap blast radius |
| Maximum retry attempts on RetryAfter | 3 | Prevent indefinite retry loops |
| Inter-batch send delay | 500ms | Reduce flood limit risk |
| Active member hard cap | 1000 | Protect API standing + stability |

## Database Schema

See `migrations/` for full SQL. Tables: `groups`, `members`, `rate_limit_log`.
No message content is ever written to the database.

## Deployment

Docker Compose on Ubuntu VPS. Long polling by default.
SQLite stored in a host-mounted volume at `/data/`.

## Manual E2E Test Checklist

Run these against a real Telegram test group before each release.
Check BotFather: Privacy Mode must be **DISABLED** before testing passive discovery.

- [ ] Add bot to group → no action taken, group remains inactive
- [ ] Non-admin sends /setup → "Only group admins can use /setup."
- [ ] Admin sends /setup → activated, admin count reported
- [ ] /setup again in same group → "Bot is already active in this group."
- [ ] /all in inactive group → "Bot not active in this group. Use /setup first."
- [ ] /all with no known members other than sender → "No members found yet. Send some messages first."
- [ ] /all sender is excluded from mention output
- [ ] Member sends a message → passively discovered (send /all after to verify)
- [ ] /all with members → mentions sent as reply to /all message
- [ ] /all within cooldown window → "Please wait Xs before using /all again."
- [ ] /syncmembers → admins synced, count reported + API limitation note shown
- [ ] /config (no args) → shows current config for group
- [ ] /config invalid_key foo → error listing valid keys
- [ ] /config cooldown foo → error listing valid values
- [ ] /config cooldown 30 → cooldown updated; /all then blocked for 30s
- [ ] /config delete_trigger on → /all message deleted after send (bot needs admin rights)
- [ ] /config delete_trigger on, bot not admin → warning reply instead of silent fail
- [ ] /config mention_mode username → /all uses @username; fallback to HTML mention if no username
- [ ] /config restrict_all_to_admins on → non-admin /all returns "Only group admins can use /all."
- [ ] /deactivate by non-admin → rejected
- [ ] /deactivate by admin → deactivated; /all returns inactive message
- [ ] Member leaves group → is_active=0; not mentioned in next /all
- [ ] Member rejoins → is_active=1; mentioned in next /all
- [ ] Bot removed from group → group auto-deactivated (is_active=0 in DB)
- [ ] Group with 1001+ known members → "Member count N exceeds maximum 1000" error reply
