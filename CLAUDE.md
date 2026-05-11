# all247 — Claude Project Instructions

## What This Is

Privacy-first Telegram bot. Single job: `/all` mentions all known members in a group chat.
Viber → Telegram migration tool. Open source (MIT). Self-hosted via Docker on Ubuntu VPS.

---

## Session Start Protocol

**Do this at the start of every session before writing any code:**

1. Read `docs/TASKS.md` — find current phase, identify incomplete tasks
2. Read `docs/ARCHITECTURE.md` — understand decisions already made
3. Check memory file at `/Users/mobile247/.claude/projects/-Users-mobile247-projects-personal-telegram-all247/memory/MEMORY.md`
4. Work only on tasks in the current phase — do not jump ahead
5. Mark tasks `[x]` in `docs/TASKS.md` as you complete them
6. Record any new architectural decisions in `docs/ARCHITECTURE.md` ADR table AND `docs/TASKS.md` ADR log

---

## Mandatory Workflow Rules

- **One phase per session** — keeps token use manageable, avoids compaction
- **Update `docs/TASKS.md`** — mark tasks complete as you finish them
- **Update `docs/ARCHITECTURE.md`** — add ADR entries for every significant decision
- **Update `docs/PRIVACY.md`** — if any data handling changes
- **Never skip the phase** — if Phase 2 is next, do Phase 2, not Phase 3 bits
- **No speculative features** — only build what is in the current phase tasks

---

## Hard Privacy Rules — Non-Negotiable

These apply to every line of code, every log statement, every DB write:

- **NEVER** store message content in DB or logs
- **NEVER** log command arguments, mention text, or message payloads
- **NEVER** store `triggered_by` (user_id) in `rate_limit_log` — group_id + timestamp only
- Member upsert logs: **DEBUG level only** — not INFO (prevents log bloat in active groups)
- Log allowed: group_id, user_id (for activation/config events), event type, timestamp, error type
- Log forbidden: display names in free-form strings, usernames in free-form strings, any message content

---

## Hard Code Constants — Not Operator-Configurable

```python
MAX_MESSAGE_LENGTH = 4000          # conservative Telegram limit
BATCH_DELAY_SECONDS = 0.5          # between batch sends
MAX_BATCHES = 10                    # per /all invocation
MAX_RETRY_ATTEMPTS = 3             # on RetryAfter
MIN_INTER_INVOCATION_SECONDS = 3   # floor regardless of cooldown config
MAX_MENTIONABLE_MEMBERS = 1000     # default; env override: MAX_MENTIONABLE_MEMBERS
```

`MAX_MENTIONABLE_MEMBERS` is the only one overridable via env var (operators who accept the risk).

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Bot framework | `python-telegram-bot` v20+ (async) |
| DB | SQLite via `aiosqlite` + raw SQL (no ORM) |
| Config | Environment variables + `.env` (python-dotenv) |
| Deployment | Docker Compose, Ubuntu VPS |

---

## Project Structure

```
all247/
├── CLAUDE.md                    ← you are here
├── README.md                    ← stays in root (GitHub convention)
├── LICENSE
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── docker/Dockerfile
├── migrations/
│   ├── 001_initial_schema.sql   ← groups + members tables (FULL)
│   └── 002_rate_limits.sql      ← rate_limit_log table (FULL)
├── bot/
│   ├── config.py                ← FULL (env var loader, frozen dataclass)
│   ├── main.py                  ← FULL structure (stubs called until Phase 4)
│   ├── handlers/
│   │   ├── command_handlers.py  ← STUB (Phase 4)
│   │   └── event_handlers.py    ← STUB (Phase 4)
│   ├── services/
│   │   ├── group_service.py     ← STUB (Phase 2)
│   │   ├── member_service.py    ← STUB (Phase 2)
│   │   ├── mention_service.py   ← STUB (Phase 3)
│   │   └── rate_limit_service.py← STUB (Phase 4)
│   ├── repository/
│   │   ├── db.py                ← FULL (migration runner, WAL mode)
│   │   ├── group_repo.py        ← STUB (Phase 2)
│   │   └── member_repo.py       ← STUB (Phase 2)
│   └── utils/telegram_helpers.py← STUB (Phase 3)
├── tests/
│   ├── unit/                    ← Phase 2-3
│   └── integration/             ← Phase 5
└── docs/
    ├── BRD.md                   ← source of truth for requirements
    ├── TECHNICAL_SPEC.md        ← source of truth for implementation spec
    ├── TASKS.md                 ← phased task list + ADR log (keep updated)
    ├── ARCHITECTURE.md          ← architecture decisions + E2E test checklist
    ├── PRIVACY.md               ← data handling policy
    └── SECURITY.md              ← vulnerability reporting + token compromise guide
```

---

## Key Architecture Decisions (summary — full log in docs/ARCHITECTURE.md)

| ADR | Decision |
|---|---|
| ADR-001 | python-telegram-bot v20 async |
| ADR-002 | SQLite + aiosqlite + raw SQL |
| ADR-003 | Long polling default, webhook optional via WEBHOOK_URL env |
| ADR-004 | HTML parse mode only — html.escape() on all display names |
| ADR-005 | stdout/stderr logging only — no file logging |
| ADR-006 | MIT License |
| ADR-007 | Mentions alphabetical by display_name COLLATE NOCASE |
| ADR-008 | MAX_MENTIONABLE_MEMBERS=1000 hard cap |
| ADR-009 | rate_limit_log: no triggered_by — group_id + timestamp only |
| ADR-010 | restrict_all_to_admins config option (default: off) |
| ADR-011 | delete_trigger failure → reply with warning, not silent fail |
| ADR-012 | Docker HEALTHCHECK via /tmp/all247_heartbeat file touch |
| ADR-013 | SQLite WAL mode on every connection (already in db.py) |

---

## Per-Group Config Keys

Valid keys and values for `/config`:

| Key | Values | Default |
|---|---|---|
| `cooldown` | integer ≥ 0 (seconds) | 0 |
| `delete_trigger` | `on` / `off` | `off` |
| `invite_expiry` | integer ≥ 1 (hours) | 24 |
| `mention_mode` | `display_name` / `username` | `display_name` |
| `restrict_all_to_admins` | `on` / `off` | `off` |

These are defined in `bot/services/group_service.py` → `VALID_CONFIG_KEYS` / `VALID_CONFIG_VALUES`.

---

## Services in bot_data (dependency injection via Application.bot_data)

```python
app.bot_data = {
    "config": Config,
    "group_service": GroupService,
    "member_service": MemberService,
    "mention_service": MentionService,
    "rate_limit_service": RateLimitService,
}
```

Handlers access services via `context.bot_data["service_name"]`.

---

## Mention Delivery Rules

- Parse mode: `HTML` always — never MarkdownV2
- `html.escape()` on every display name — never manual escaping
- `display_name` mode: `<a href="tg://user?id=ID">Escaped Name</a>`
- `username` mode: `@username` — fallback to display_name HTML if no username
- Order: alphabetical by display_name, `ORDER BY display_name COLLATE NOCASE`

---

## BotFather Requirement (Critical)

Privacy Mode MUST be disabled or passive member discovery silently fails.
```
@BotFather → /mybots → your bot → Bot Settings → Group Privacy → Turn off
```
This is documented in README.md (top warning) and logged at WARNING level on every startup.

---

## Bot Exclusion Rule

Any user where `user.is_bot is True` MUST be excluded from the member registry.
Check applies in: passive discovery, `/syncmembers`, `chat_member_updated` events.
Bots must never appear in `/all` mention output.
