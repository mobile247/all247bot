# all247 — Task List

Token-efficient chunking: work one phase per session. Mark tasks [x] as done.

---

## Phase 1 — Scaffolding [COMPLETE]
> Goal: project structure, stubs, config, migrations, docker, doc skeletons, task list

- [x] Create TASKS.md
- [x] Create .gitignore
- [x] Create .env.example
- [x] Create requirements.txt
- [x] Create LICENSE (MIT)
- [x] Create migrations/001_initial_schema.sql
- [x] Create migrations/002_rate_limits.sql
- [x] Create docker/Dockerfile (TODO comment added: pin to digest in Phase 5)
- [x] Create docker-compose.yml
- [x] Create bot/__init__.py
- [x] Create bot/config.py (full — env var loader)
- [x] Create bot/main.py (stub — entry point)
- [x] Create bot/handlers/__init__.py
- [x] Create bot/handlers/command_handlers.py (stub)
- [x] Create bot/handlers/event_handlers.py (stub)
- [x] Create bot/services/__init__.py
- [x] Create bot/services/group_service.py (stub)
- [x] Create bot/services/member_service.py (stub)
- [x] Create bot/services/mention_service.py (stub)
- [x] Create bot/services/rate_limit_service.py (stub)
- [x] Create bot/repository/__init__.py
- [x] Create bot/repository/db.py (full — migration runner)
- [x] Create bot/repository/group_repo.py (stub)
- [x] Create bot/repository/member_repo.py (stub)
- [x] Create bot/utils/__init__.py
- [x] Create bot/utils/telegram_helpers.py (stub)
- [x] Create tests/unit/.gitkeep
- [x] Create tests/integration/.gitkeep
- [x] Create README.md (skeleton)
- [x] Create ARCHITECTURE.md (skeleton)
- [x] Create PRIVACY.md (skeleton)
- [x] Create SECURITY.md (skeleton)
- [x] Save project memory

---

## Phase 2 — Data Layer
> Goal: implement repos + services for group and member management
> Files: group_repo.py, member_repo.py, group_service.py, member_service.py

- [ ] Implement `group_repo.py`
  - `upsert_group(group_id)`
  - `get_group(group_id)`
  - `activate_group(group_id, activated_by)`
  - `deactivate_group(group_id)`
  - `update_group_config(group_id, key, value)`
- [ ] Implement `member_repo.py`
  - `upsert_member(group_id, user_id, display_name, username)`
  - `get_active_members(group_id)` — ordered COLLATE NOCASE
  - `set_member_active(group_id, user_id, is_active)`
  - `prune_stale_members(group_id, days)` — sets is_active=0
  - `hard_delete_stale_members(group_id, days)` — explicit opt-in
- [ ] Implement `group_service.py`
  - `activate(group_id, activated_by)` — validate not already active
  - `deactivate(group_id, deactivated_by)`
  - `is_active(group_id)` -> bool
  - `get_config(group_id)` -> dict
  - `update_config(group_id, key, value, changed_by)` — validate key/value; raise ValueError listing valid options on invalid key or value
  - Support `restrict_all_to_admins` as a valid config key (on/off, default off)
- [ ] Implement `member_service.py`
  - `discover_member(group_id, user)` — upsert, skip bots
  - `mark_left(group_id, user_id)`
  - `mark_rejoined(group_id, user_id)`
  - `sync_admins(group_id, bot)` — getChatAdministrators upsert
  - `get_mentionable_members(group_id)` -> list
  - `prune_stale_if_configured(group_id, days)` — no-op when days=0; sets is_active=0 beyond threshold
- [ ] Write unit tests for group_service
- [ ] Write unit tests for member_service

---

## Phase 3 — Bot Logic
> Goal: mention delivery, rate limiting, flood protection, helpers
> Files: mention_service.py, rate_limit_service.py, telegram_helpers.py

- [ ] Implement `telegram_helpers.py`
  - `is_group_admin(bot, chat_id, user_id)` -> bool
  - `html_mention(user_id, display_name)` -> str
  - `username_mention(username, user_id, display_name)` -> str
- [ ] Implement `rate_limit_service.py`
  - `check_cooldown(group_id)` -> (allowed: bool, seconds_remaining: int)
  - `record_invocation(group_id, user_id)`
  - `purge_old_entries(days)` — rate_limit_log cleanup
  - Hard limits: 3s minimum inter-invocation per group
- [ ] Implement `mention_service.py`
  - `build_mention_strings(members, mention_mode)` -> list[str]
  - `batch_mentions(mention_strings)` -> list[str] (4000 char limit)
  - `send_mentions(bot, chat_id, batches, reply_to)` — with retry + delay
  - `send_with_retry(bot, chat_id, text, max_retries=3)` — RetryAfter handling
  - Hard limits: MAX_MENTIONABLE_MEMBERS=1000 (default), MAX_BATCHES=10
  - Verify `config.max_mentionable_members` wired into MentionService constructor (done in main.py stub; confirm in tests)
- [ ] Write unit tests for mention_service (batching, format generation)
- [ ] Write unit tests for rate_limit_service (cooldown enforcement)

---

## Phase 4 — Handlers & Entry Point
> Goal: wire all commands and events, complete main.py
> Files: command_handlers.py, event_handlers.py, main.py

- [ ] Implement `command_handlers.py`
  - `/setup` — admin verify → activate → confirm reply
  - `/all` — active check → rate limit → restrict_all_to_admins check → fetch members → send mentions → optional delete trigger
  - `/all` delete_trigger: if deletion fails (bot lacks admin rights), reply with one-time warning instead of silent fail
  - `/syncmembers` — admin only → sync_admins → reply count
  - `/config` — admin only → view or update config; on invalid key/value reply with error message listing valid options (sourced from ValueError raised by group_service)
  - `/deactivate` — admin only → deactivate → confirm
- [ ] Implement `event_handlers.py`
  - `on_message` — passive member discovery (skip bots, skip non-active groups)
  - `on_chat_member_updated` — track join/leave → set is_active
  - `on_bot_added_to_group` — log event, no action until /setup
  - `on_bot_removed_from_group` — automatically deactivate group record (set is_active=0) when bot is removed/kicked
- [ ] Implement `main.py`
  - Load config
  - Init DB (run migrations)
  - Build Application
  - Register all handlers
  - Schedule rate_limit_log purge task on startup
  - Schedule stale member pruning on startup (calls prune_stale_if_configured per group if STALE_MEMBER_PRUNE_DAYS > 0)
  - Write heartbeat file `/tmp/all247_heartbeat` on each processed update (enables Docker HEALTHCHECK)
  - Start polling or webhook based on WEBHOOK_URL
- [ ] Manual end-to-end test checklist (in ARCHITECTURE.md)

---

## Phase 5 — Tests, Docs & OSS Polish
> Goal: tests complete, docs finalized, ready for open source publication
> Files: tests/**, README.md, ARCHITECTURE.md, PRIVACY.md, SECURITY.md, LICENSE

- [ ] Integration test: /setup → /all flow against test SQLite
- [ ] Integration test: passive member discovery pipeline
- [ ] Integration test: batch send simulation with mock Telegram API
- [ ] Privacy verification test: log output scan (no message content)
- [ ] DB schema audit test (no message content columns)
- [ ] Complete README.md (setup guide, BotFather privacy mode warning, env vars)
- [ ] Complete ARCHITECTURE.md (decisions log, diagrams)
- [ ] Complete PRIVACY.md (data handling policy)
- [ ] Complete SECURITY.md (responsible disclosure instructions)
- [ ] Secrets scan (no hardcoded credentials)
- [ ] Pin Docker base image to digest for reproducibility (replace `python:3.11-slim` tag with `python:3.11-slim@sha256:<digest>`; TODO comment already in Dockerfile)
- [ ] Decide and commit license (MIT recommended)
- [ ] Tag v1.0.0

---

## Architecture Decisions Log

| # | Decision | Rationale | Date |
|---|---|---|---|
| ADR-001 | Python 3.11 + python-telegram-bot v20 (async) | Async-native, actively maintained, strong ecosystem | 2026-05-09 |
| ADR-002 | SQLite + aiosqlite + raw SQL | Zero-config, no ORM overhead, sufficient for v1 scale | 2026-05-09 |
| ADR-003 | Long polling default (webhook optional) | Simpler self-hosted setup, no public IP required | 2026-05-09 |
| ADR-004 | HTML parse mode for mentions | Safer than MarkdownV2 for display names with special chars | 2026-05-09 |
| ADR-005 | No file logging — stdout/stderr only | Delegate log rotation to Docker/host OS | 2026-05-09 |
| ADR-006 | MIT License | Maximum adoption, no copyleft restrictions | 2026-05-09 |
| ADR-007 | Alphabetical mention order (COLLATE NOCASE) | Consistent, reproducible, user-friendly | 2026-05-09 |
| ADR-008 | Hard cap: MAX_MENTIONABLE_MEMBERS=1000 | Protect Telegram API standing + bot stability | 2026-05-09 |
| ADR-009 | rate_limit_log stores group_id + timestamp only (no triggered_by) | Cooldown is per-group; storing user_id is over-collection for a privacy-first system | 2026-05-09 |
| ADR-010 | restrict_all_to_admins config option added (default: off) | Low-effort, prevents breaking schema change in v2, avoids BRD ambiguity | 2026-05-09 |
| ADR-011 | delete_trigger requires bot admin rights; failure replies with warning | BRD minimal-access principle preserved — admin rights optional, not default | 2026-05-09 |
| ADR-012 | Docker HEALTHCHECK via heartbeat file touch | No external deps, detects stuck-but-alive process that restart:unless-stopped misses | 2026-05-09 |
