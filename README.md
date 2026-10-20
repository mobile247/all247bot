# all247

Privacy-first Telegram bot that adds `@all` (mention-everyone) functionality to group chats.

> **Before you do anything else:**
> Telegram bots run with **Privacy Mode enabled by default**. In this mode the bot cannot see
> regular group messages, which means passive member discovery will **silently fail** — the bot
> will work but will only mention a fraction of the group.
>
> **You must disable Privacy Mode in BotFather before adding the bot to any group.**
>
> ```
> 1. Open Telegram → @BotFather
> 2. Send: /mybots
> 3. Select your all247 bot
> 4. Bot Settings → Group Privacy → Turn off
> ```

---

## What it does

When any group member sends `/all`, the bot mentions all known members of the group.
That's it. One job. Done well.

---

## Privacy

- No message content is ever stored or logged.
- Only Telegram-native metadata is retained: user IDs, display names, usernames, group IDs.
- No telemetry. No analytics. No behavioral tracking.
- See [PRIVACY.md](docs/PRIVACY.md) for the full data handling policy.

---

## Quick Start

_Setup guide coming in Phase 5. See [docs/TASKS.md](docs/TASKS.md) for current development status._

### Prerequisites

- Docker + Docker Compose
- A Telegram Bot token from [@BotFather](https://t.me/BotFather)

### Critical: Disable Privacy Mode in BotFather

> **Warning:** Telegram bots run with Privacy Mode enabled by default.
> In this mode, the bot cannot see regular group messages, which means
> passive member discovery will silently fail.
>
> You MUST disable Privacy Mode for all247 to work correctly.
>
> ```
> 1. Open Telegram → @BotFather
> 2. Send: /mybots
> 3. Select your all247 bot
> 4. Bot Settings → Group Privacy → Turn off
> ```

### Configuration

Copy `.env.example` to `.env` and set your `BOT_TOKEN`:

```bash
cp .env.example .env
# Edit .env and set BOT_TOKEN=your-token-here
```

### Run

```bash
docker compose up -d
```

### Bot Commands

| Command | Where | Who | Description |
|---|---|---|---|
| `/setup` | Group | Admin | Activate bot in group (also registers current admins) |
| `/all` | Group | Anyone* | Mention all known members |
| `/registermembers` | Group | Admin | Bulk-register members picked via the @ mention list |
| `/invite` | Group | Admin | Post a self-registration link for members |
| `/start <token>` | Private chat | Anyone | Register via an `/invite` link |
| `/syncmembers` | Group | Admin | Sync current admins into member registry |
| `/prunemembers` | Group | Admin | Remove members who left the group from `/all` (bot needs no admin rights) |
| `/members` | Group | Admin | List registered members |
| `/config` | Group | Admin | View or update group settings |
| `/migrate` | Private chat | Admin | Import members from an old group ID into a new one |
| `/deactivate` | Group | Admin | Deactivate bot (keeps data) |
| `/leave` | Group | Admin | Purge all data and remove bot from group |

\* Admins only when `restrict_all_to_admins` is enabled.

Admin commands sent by non-admins are silently ignored (no reply), so members tapping a
command link in chat don't generate noise.

---

## Command Guide

### Recommended onboarding for an existing group

1. Add the bot and disable Privacy Mode in BotFather (see above).
2. Run `/setup` — activates the bot and registers current admins.
3. Run `/invite` and pin the link so members can self-register.
4. Use `/registermembers` for members without a username who won't tap the link.
5. Check coverage with `/members`.

From then on, anyone who sends a message in the group is registered automatically.

### `/all`

```
/all
```

- Mentions every registered member, alphabetically. The sender is not tagged.
- Long lists are split across multiple messages.
- If a `cooldown` is set, early repeats get: `Please wait 12s before using /all again.`
- With `delete_trigger on`, the `/all` message is deleted afterwards. This requires the bot
  to be an admin with delete permission; otherwise it posts a warning instead.

### `/registermembers`

Bulk-registers members the bot hasn't seen yet. Type the command, then select each person
**from the @ autocomplete list**, all in one message:

```
/registermembers @Alice @Bob @Carlos
```

Reply: `Registered 3 member(s).`

Important limitation — the bot can only register mentions that carry a Telegram user ID:

| Member | What the @ picker inserts | Result |
|---|---|---|
| Has **no** username | A name link (text mention) | ✅ Registered |
| **Has** a username | Plain `@username` text | ❌ Skipped — Telegram provides no user ID |

Skipped mentions are reported, e.g.:

```
Registered 2 member(s).

1 @username mention(s) skipped — Telegram does not provide user IDs for plain @username text. ...
```

Tips:

- Names typed by hand (not picked from the list) are not mentions and are ignored.
- Bots are skipped automatically.
- Re-registering someone is harmless.
- For large groups, split into several messages.
- For members **with** usernames, use `/invite` or ask them to send any message.

### `/invite` and `/start`

```
/invite
```

Posts a "Tap here to register" deep link (`https://t.me/<bot>?start=<token>`), plus a manual
fallback: open a private chat with the bot and send `/start <token>`.

- The link is multi-use until it expires (default 24 hours; change with
  `/config invite_expiry 72`).
- Members who tap it get a private confirmation: `You've been registered in <group>...`
- Works for every member, with or without a username — the best option for members who
  rarely post.

### `/syncmembers`, `/prunemembers`, `/members`

- `/syncmembers` — adds current group **admins**. The Telegram API cannot list regular members.
- `/prunemembers` — checks every registered member against Telegram and removes anyone who
  left. Useful when *Hide join/leave messages* is enabled. No bot admin rights needed.
  Reply: `Removed 2 member(s) who are no longer in this group.`
- `/members` — lists registered members, e.g. `• Alice (@alice)`. Use it to check who `/all`
  will reach.

### `/config`

```
/config                              # show current settings
/config cooldown 60                  # /all at most once per 60 seconds
/config delete_trigger on            # delete the /all message after sending
/config invite_expiry 48             # invite links last 48 hours
/config mention_mode username        # @username (falls back to name link if none)
/config restrict_all_to_admins on    # only admins may use /all
```

| Key | Values | Default |
|---|---|---|
| `cooldown` | integer ≥ 0 (seconds) | `0` |
| `delete_trigger` | `on` / `off` | `off` |
| `invite_expiry` | integer ≥ 1 (hours) | `24` |
| `mention_mode` | `display_name` / `username` | `display_name` |
| `restrict_all_to_admins` | `on` / `off` | `off` |

### `/migrate` (private chat only)

For when a group was upgraded to a supergroup (new chat ID) and lost its setup:

1. Run `/setup` in the new group.
2. In a private chat with the bot, send `/migrate` to list the groups you administer:
   ```
   • -100111… — Family Chat [inactive]
   • -100222… — Family Chat [active]
   ```
3. Send `/migrate <old_group_id> <new_group_id>`, e.g.
   `/migrate -100111… -100222…` → `Imported 34 member(s) into the target group.`

You must be an admin of the target group, and it must be active.

### `/deactivate` vs `/leave`

- `/deactivate` — pauses the bot. Member data is kept; `/setup` reactivates.
- `/leave` — **irreversible**: deletes this group's member registry and invite links, then
  the bot leaves. To use it again, re-add the bot and run `/setup`.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | **Yes** | — | Telegram Bot token from @BotFather |
| `DB_PATH` | No | `./data/all247.db` | Path to SQLite database file |
| `LOG_LEVEL` | No | `INFO` | Logging level (`INFO`, `WARNING`, `ERROR`) |
| `WEBHOOK_URL` | No | — | Enable webhook mode (leave unset for long polling) |
| `WEBHOOK_PORT` | No | `8443` | Port for webhook listener |
| `DEFAULT_COOLDOWN_SECONDS` | No | `0` | Default `/all` cooldown for new groups (seconds) |
| `RATE_LIMIT_PURGE_DAYS` | No | `7` | Days to retain rate limit log entries |
| `STALE_MEMBER_PRUNE_DAYS` | No | `0` | Mark inactive members after N days without activity (0 = disabled) |
| `MAX_MENTIONABLE_MEMBERS` | No | `1000` | Hard cap on members per `/all` (increase at your own risk) |

---

## Telegram API Limitation

The bot can only mention members it knows about. It builds its registry through:

1. **Passive discovery** — any message sent in the group after the bot is added
2. **`/syncmembers`** — syncs current group admins on demand
3. **`/invite`** — members self-register via a deep link
4. **`/registermembers`** — admins bulk-register members via @ mentions (members without usernames only)

Non-admin members who have not sent any message, used an invite link, or been registered by
an admin will not appear in `/all` output. This is a Telegram Bot API constraint, not a bug.

Members who leave or are removed are dropped from `/all` automatically. The bot detects this
from the group's "left the group" service message, and no admin rights are needed. If removals
are missed (for example, because *Hide join/leave messages* is enabled), a group admin can run
**`/prunemembers`**. It checks every registered member against Telegram and drops anyone no
longer in the group. This command also works without giving the bot admin rights.

---

## Self-Hosting

Designed for self-hosted deployment on a Ubuntu VPS with Docker Compose.
No external service dependencies. Runs on low-spec hardware.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Security

Found a vulnerability? See [SECURITY.md](docs/SECURITY.md).
