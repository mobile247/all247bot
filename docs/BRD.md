# Business Requirements Document (BRD)

## Project Name

**all247**

---

# 1. Executive Summary

all247 is a privacy-first Telegram bot designed to provide an `@all`-style functionality for Telegram group chats.

The bot allows users within a Telegram group to trigger a command, such as `/all`, which causes the bot to mention all known members of the group.

The project is intended to:
- solve the lack of native `@all` support in Telegram,
- prioritize privacy and minimal data retention,
- operate with a single focused responsibility,
- remain lightweight and inexpensive to host,
- and be open-source from the beginning.

The initial release will target self-hosted deployments using Docker on Ubuntu-based servers.

---

# 2. Business Problem

Organizations migrating from platforms such as Viber lose the ability to efficiently notify all members in a group using a single command.

Telegram does not natively support:
- `@all`
- `@everyone`
- group-wide mentions

This creates operational inefficiencies in:
- urgent announcements,
- incident response,
- coordination,
- and internal communication.

The organization requires:
- a secure internal solution,
- minimal operational overhead,
- privacy-first behavior,
- and future open-source viability.

---

# 3. Project Objectives

## Primary Objectives

- Provide reliable `@all` functionality for Telegram groups.
- Maintain strong privacy and security posture.
- Avoid storing message contents.
- Keep the bot lightweight and low-cost.
- Support self-hosted deployment.
- Support open-source distribution.

## Secondary Objectives

- Allow future extensibility.
- Support future SaaS deployment.
- Support future advanced tagging groups.
- Support future administrative interfaces.

---

# 4. Scope

## In Scope

### Telegram Bot Capabilities
- Respond to `/all` command.
- Mention all known members of a Telegram group.
- Support configurable mention formatting.
- Support configurable response behavior.

### Group Management
- Group activation/setup workflow.
- Admin verification during setup.
- Group-specific configuration storage.

### Privacy & Security
- No storage of message contents.
- Minimal metadata retention only.
- Secure storage of configuration data.
- Audit logging for configuration changes only.
- Error logging without message contents.

### Deployment
- Docker-based deployment.
- Ubuntu VPS deployment support.
- Self-hosted operation.

### Open Source Readiness
- Public repository compatibility.
- Documentation readiness.
- Configurability for external adopters.

---

## Out of Scope (v1)

- Web admin interface
- SaaS hosting platform
- Analytics dashboards
- User activity tracking
- Cross-platform integrations
- AI or NLP capabilities
- Message moderation
- Content filtering
- Scheduled broadcasts
- Push notifications outside Telegram
- Enterprise SSO integration

---

# 5. Stakeholders

| Stakeholder | Role |
|---|---|
| Group Members | Use `/all` command |
| Group Admins | Configure and activate bot |
| Developers | Build and maintain system |
| Open Source Community | Future adopters/contributors |

---

# 6. User Roles

## Group Member
Can:
- use `/all` command by default,
- trigger group mention functionality.

Cannot:
- modify bot configuration,
- activate/deactivate groups,
- manage settings.

---

## Group Admin
Can:
- activate bot,
- configure settings,
- manage permissions,
- configure cooldowns/rate limits,
- manage mention behavior.

---

# 7. Functional Requirements

## 7.1 Group Activation

### Requirement
The bot must remain inactive when first added to a group.

### Activation Flow
1. Bot added to group
2. Bot detects addition
3. Bot waits for admin setup command
4. Admin executes setup command
5. Bot validates admin permissions
6. Group becomes active

### Acceptance Criteria
- Bot does not operate before activation.
- Only group admins can activate the bot.

---

## 7.2 Mention Trigger

### Requirement
The bot must support `/all` command.

### Default Behavior
- Any group member may use `/all`.

### Future Expandability
Architecture should support:
- role-based permissions,
- subgroup mentions,
- advanced commands.

### Acceptance Criteria
- `/all` triggers group mention behavior.
- Command works consistently in activated groups.

---

## 7.3 Mention Delivery

### Requirement
The bot must mention all known group members.

### Mention Style
Default:
- display-name mentions

Fallback:
- username mentions if required

### Configurable Options
- mention-only response
- mention + quoted original message
- mention + reposted message

### Acceptance Criteria
- Known users are tagged successfully.
- Mentions are human-readable.

---

## 7.4 Member Discovery

## Requirement
The bot must maintain a list of known group members.

### Member Discovery Methods

#### Passive Discovery
Bot captures metadata when users:
- send messages,
- join groups,
- interact with bot.

#### Bootstrap Sync
Admin may trigger:
`/syncmembers`

### Stored Metadata
Allowed:
- Telegram user ID
- display name
- username
- group ID

Prohibited:
- message contents
- message history
- attachments
- reactions history
- behavioral analytics

### Acceptance Criteria
- Bot can build and maintain member registry.
- No message content is stored.

---

## 7.5 Rate Limiting & Cooldowns

### Requirement
The bot must support configurable:
- cooldowns,
- rate limits,
- mention batching.

### Default
Disabled by default.

### Purpose
- reduce abuse,
- reduce Telegram flood-limit risks,
- improve reliability.

### Acceptance Criteria
- Admin can enable limits if desired.
- System can safely batch mentions.

---

## 7.6 Telegram Flood Protection Handling

### Requirement
The bot must gracefully handle Telegram API limits.

### Required Behaviors
- batching support,
- retry handling,
- partial-send recovery,
- error reporting.

### Acceptance Criteria
- System remains stable during large mention operations.

---

## 7.7 Message Cleanup

### Requirement
Original trigger handling must be configurable.

### Modes
- keep original message (default)
- delete original message
- mention-only response

### Acceptance Criteria
- Group admins can configure behavior.

---

# 8. Privacy Requirements

## Core Principle

all247 is a privacy-first system.

---

## 8.1 Prohibited Data Storage

The system must NOT store:
- message contents,
- chat history,
- attachments,
- media,
- links,
- reactions,
- behavioral analytics.

---

## 8.2 Allowed Storage

The system MAY store:
- Telegram user IDs,
- usernames,
- display names,
- group IDs,
- configuration settings,
- audit records,
- operational errors.

---

## 8.3 Logging Policy

### Allowed Logs
- setup events,
- configuration changes,
- system errors,
- activation/deactivation events.

### Forbidden Logs
- message contents,
- command payloads,
- mention text contents.

---

## 8.4 Telemetry

### Default Requirement
No telemetry by default.

### Open Source Requirement
Any future telemetry features must be:
- opt-in,
- documented,
- disabled by default.

---

# 9. Security Requirements

## 9.1 Secure Storage

Configuration and metadata must be securely stored.

Recommended:
- encrypted database storage,
- secrets management,
- environment-based credentials.

---

## 9.2 Principle of Minimal Access

The bot should request only permissions necessary for:
- reading commands,
- mentioning users,
- optional message deletion.

---

## 9.3 Open Source Security

The project should:
- avoid hardcoded secrets,
- support environment variable configuration,
- provide secure deployment guidance.

---

# 10. Non-Functional Requirements

## Reliability
- lightweight operation,
- resilient handling of Telegram API errors.

## Performance
- fast response to `/all`,
- efficient batching.

## Cost Efficiency
- capable of running on low-cost VPS infrastructure.

## Maintainability
- modular architecture,
- future extensibility.

## Portability
- Docker-first deployment support.

---

# 11. Technical Direction (High-Level)

## Recommended Stack

### Runtime
- Python recommended

### Deployment
- Docker Compose
- Ubuntu VPS

### Storage
- lightweight relational database preferred

### API
- Telegram Bot API

---

# 12. Future Enhancements

Potential future features:
- web admin panel,
- hosted SaaS version,
- subgroup mentions,
- role-based tagging,
- analytics,
- advanced moderation,
- multiple trigger types,
- organization management,
- enterprise integrations.

---

# 13. Risks & Constraints

| Risk | Impact |
|---|---|
| Telegram API limitations | Partial member visibility |
| Telegram flood controls | Delayed/failed mentions |
| Large groups | Message batching complexity |
| Privacy expectations | Strict storage limitations |
| Open-source exposure | Increased security scrutiny |

---

# 14. Success Criteria

The project is considered successful if:

- Users can reliably trigger `/all`
- Group members are successfully mentioned
- No message content is stored
- Bot remains lightweight and stable
- Deployment is simple for self-hosting
- Privacy requirements are maintained
- Open-source adoption is feasible

---

# 15. Initial Deployment Recommendation

## Recommended v1 Deployment

### Infrastructure
- Ubuntu VPS
- Docker Compose

### Reasoning
- lowest cost,
- simplest deployment,
- easy open-source adoption,
- low operational complexity.

---

# 16. Open Source Philosophy

The project should prioritize:
- transparency,
- auditability,
- simplicity,
- privacy-first operation,
- minimal data retention,
- self-hostability.

The project should avoid:
- unnecessary complexity,
- invasive telemetry,
- vendor lock-in,
- centralized dependencies.
