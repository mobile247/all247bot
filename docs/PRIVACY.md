# Privacy Policy — all247

all247 is designed with privacy as a core requirement, not an afterthought.

---

## What We Store

| Data | Stored | Purpose |
|---|---|---|
| Telegram user ID | Yes | Identify members for mention |
| Display name | Yes | Build mention strings |
| Username | Yes (nullable) | Alternative mention format |
| Group (chat) ID | Yes | Scope member registry per group |
| Group configuration | Yes | Admin-configured settings |
| Who activated the group | Yes (user_id only) | Audit trail |
| Who triggered /all | **No** — stdout log only, not persisted | Cooldown is per-group; storing user_id would be over-collection |
| When /all was triggered | Yes (group_id + timestamp) | Cooldown enforcement |

---

## What We Never Store

- Message content of any kind
- Command arguments or payloads
- Chat history
- Attachments, media, links, or reactions
- Behavioral analytics
- Message IDs beyond transient delivery

---

## Logging

Logs are written to stdout/stderr only. No log files are written to disk by the bot.

**Logged events:** bot startup, group activation/deactivation, /all invocations (group_id, user_id, member count, timestamp), rate limit hits, config changes, Telegram API errors.

**Never logged:** message content, command arguments, display names or usernames in free-form log lines, anything that could reconstruct a conversation.

---

## Telemetry

None. No telemetry is collected. Any future telemetry will be opt-in, disabled by default, and documented.

---

## Rate Limit Log — Design Decision

The `rate_limit_log` table stores only `group_id` and `triggered_at`. It does **not** store who triggered `/all`.

Rationale: the cooldown is enforced per-group, not per-user. Storing `triggered_by` (user_id) would create a timestamped record of individual user behaviour with no functional benefit. The triggering user's ID is logged to stdout at invocation time (ephemeral, not persisted to disk by default) but is not written to the database.

---

## Data Retention

- Member registry: retained while the bot is active in the group. Members who leave are marked inactive (not deleted by default).
- Rate limit log: purged on a configurable schedule (default: 7 days).
- Stale member pruning: disabled by default; configurable via `STALE_MEMBER_PRUNE_DAYS`.

---

## Your Rights

If you are a group member and wish to have your metadata removed from the bot's registry, ask a group admin to remove you manually or deactivate the bot.

---

## Open Source Auditability

all247 is open source. You can inspect every line of code to verify these claims.
