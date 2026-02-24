# Blog Automation

A structured blog automation workspace using a 3-layer architecture:
**Directive (Skills) → Orchestration (Agent) → Execution (Python Scripts)**.

Designed for Google Antigravity with full support for Claude, Gemini, and other AI
environments via shared agent instruction files (`CLAUDE.md`, `AGENTS.md`).

---

## Architecture

| Layer | Location | Purpose |
|-------|----------|---------|
| Layer 1: Directive | `.agent/skills/` | Skill specs — goals, inputs, outputs, routing conditions |
| Layer 2: Orchestration | Agent (Manager View) | Intelligent routing, error handling, artifact generation |
| Layer 3: Execution | `execution/` | Deterministic Python scripts for bulk/repeatable operations |

**The 100x Rule:** If something needs to happen 100 times, write a script. If it
needs to happen once (checking a UI, verifying a deployment), do it via the browser.

---

## Getting Started

### 1. Prerequisites

- Python 3.10+
- Git
- A Google Cloud project with relevant APIs enabled (Sheets, Docs, Drive)
- `credentials.json` downloaded from Google Cloud Console (OAuth 2.0 Desktop Client)

### 2. Configure Environment

Fill in your API keys and project IDs in `.env`. Every variable has an inline
comment explaining where to find the value.

### 3. Run a skill

Open the workspace in your AI agent environment (Antigravity, Claude Code, etc.).
The agent reads `CLAUDE.md` / `AGENTS.md` on startup and routes your requests to
the appropriate skill in `.agent/skills/`.

---

## Project Structure

```
.agent/
├── skills/          # Workspace-scoped skill specs (add per feature)
├── rules/           # Governance and compliance rules
├── workflows/       # Multi-step orchestration flows
└── config/
    └── user-preferences.yaml   # Agent behavior and security settings

execution/           # Shared Python execution scripts (Layer 3)
.tmp/                # Intermediate files — never committed, always regenerated
.env                 # Secrets — never commit (protected by .gitignore)
CLAUDE.md            # Agent instructions for Claude environments
AGENTS.md            # Agent instructions (universal)
Project SetUp Agent.md  # Source of truth — CLAUDE.md and AGENTS.md mirror this
```

---

## Adding Skills

Each skill lives in `.agent/skills/<skill-name>/` and requires at minimum:

- **`SKILL.md`** — YAML frontmatter (`name`, `description`, `tags`, `inputs`) +
  identity, routing conditions, core rules, edge cases (~40 lines max)
- **`references/`** — detailed protocols, examples, error playbooks (loaded on-demand)
- **`scripts/`** _(optional)_ — skill-local scripts for portability
- **`assets/`** _(optional)_ — templates, static files

See the "Skill Format" section in `CLAUDE.md` for the full template.

---

## Security

- `.env`, `credentials.json`, and `token.json` are in `.gitignore` — never committed.
- All secrets must be read from `.env` by execution scripts — never hardcoded.
- Delete operations outside `.tmp/` require explicit user confirmation.
- See `CLAUDE.md` → Security and Permissions for the full policy.
- Agent settings (security posture, auto-execute rules) are in `.agent/config/user-preferences.yaml`.
