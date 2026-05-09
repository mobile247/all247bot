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

_To be completed in Phase 4._

- [ ] Add bot to group → no action taken
- [ ] Non-admin sends /setup → rejected
- [ ] Admin sends /setup → activated
- [ ] /all in inactive group → silently ignored
- [ ] /all with no members → "No members found. Try /syncmembers first."
- [ ] /all with members → mentions sent
- [ ] /all within cooldown → time remaining reply
- [ ] /syncmembers → admins synced, count reported
- [ ] /config → shows current config
- [ ] /config cooldown 30 → updates cooldown
- [ ] /config delete_trigger on → deletes /all message after processing (bot must have admin rights; failure warns user)
- [ ] /config restrict_all_to_admins on → non-admins get rejected on /all
- [ ] /all by non-admin when restrict_all_to_admins=on → rejected
- [ ] Member leaves group → is_active=0
- [ ] Member rejoins → is_active=1
- [ ] Group with 1001+ members → cap error message
