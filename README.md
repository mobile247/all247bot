# all247

Privacy-first Telegram bot that adds `@all` (mention-everyone) functionality to group chats.

> **Status:** Under active development. Not yet ready for production use.

---

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

| Command | Who | Description |
|---|---|---|
| `/setup` | Admin | Activate bot in group |
| `/all` | Anyone | Mention all known members |
| `/syncmembers` | Admin | Sync admins into member registry |
| `/config` | Admin | View or update group settings |
| `/deactivate` | Admin | Deactivate bot in group |

---

## Telegram API Limitation

The bot can only mention members it knows about. It builds its registry through:

1. **Passive discovery** — any message sent in the group after the bot is added
2. **`/syncmembers`** — syncs current group admins on demand

Non-admin members who have not sent any message since the bot was added will not appear
in `/all` output. This is a Telegram Bot API constraint, not a bug.

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
