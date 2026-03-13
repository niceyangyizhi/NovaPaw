# CLI

`novapaw` is the command-line tool for NovaPaw. This page is organized from
"get-up-and-running" to "advanced management" — read from top to bottom if
you're new, or jump to the section you need.

> Not sure what "channels", "heartbeat", or "cron" mean? See
> [Introduction](./intro) first.

---

## Getting started

These are the commands you'll use on day one.

### novapaw init

First-time setup. Walks you through configuration interactively.

```bash
novapaw init              # Interactive setup (recommended for first time)
novapaw init --defaults   # Non-interactive, use all defaults (good for scripts)
novapaw init --force      # Overwrite existing config files
```

**What the interactive flow covers (in order):**

1. **Heartbeat** — interval (e.g. `30m`), target (`main` / `last`), optional
   active hours.
2. **Show tool details** — whether tool call details appear in channel messages.
3. **Language** — `zh` / `en` / `ru` for agent persona files (SOUL.md, etc.).
4. **Channels** — optionally configure iMessage / Discord / DingTalk / Feishu /
   QQ / Console.
5. **LLM provider** — select provider, enter API key, choose model (**required**).
6. **Skills** — enable all / none / custom selection.
7. **Environment variables** — optionally add key-value pairs for tools.
8. **HEARTBEAT.md** — edit the heartbeat checklist in your default editor.

### novapaw app

Start the NovaPaw server. Everything else — channels, cron jobs, the Console
UI — depends on this.

```bash
novapaw app                             # Start on 127.0.0.1:8088
novapaw app --host 0.0.0.0 --port 9090 # Custom address
novapaw app --reload                    # Auto-reload on code change (dev)
novapaw app --workers 4                 # Multi-worker mode
novapaw app --log-level debug           # Verbose logging
```

| Option        | Default     | Description                                                   |
| ------------- | ----------- | ------------------------------------------------------------- |
| `--host`      | `127.0.0.1` | Bind host                                                     |
| `--port`      | `8088`      | Bind port                                                     |
| `--reload`    | off         | Auto-reload on file changes (dev only)                        |
| `--workers`   | `1`         | Number of worker processes                                    |
| `--log-level` | `info`      | `critical` / `error` / `warning` / `info` / `debug` / `trace` |

### Console

Once `novapaw app` is running, open `http://127.0.0.1:8088/` in your browser to
access the **Console** — a web UI for chat, channels, cron, skills, models,
and more. See [Console](./console) for a full walkthrough.

If the frontend was not built, the root URL returns a JSON message like `{"message": "NovaPaw Web Console is not available."}` but the API still works.

**To build the frontend:** in the project's `console/` directory run
`npm ci && npm run build`, then copy the output to the package directory:
`mkdir -p src/novapaw/console && cp -R console/dist/. src/novapaw/console/`.
Docker images and pip packages already include the Console.

### novapaw daemon

Inspect status, version, and recent logs without starting a conversation. Same
behavior as sending `/daemon status` etc. in chat (CLI can show local info when
the app is not running).

| Command                        | Description                                                                               |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| `novapaw daemon status`        | Status (config, working dir, memory manager)                                              |
| `novapaw daemon restart`       | Print instructions (in-chat /daemon restart does in-process reload)                       |
| `novapaw daemon reload-config` | Re-read and validate config (channel/MCP changes need /daemon restart or process restart) |
| `novapaw daemon version`       | Version and paths                                                                         |
| `novapaw daemon logs [-n N]`   | Last N lines of log (default 100; from `novapaw.log` in working dir)                      |

```bash
novapaw daemon status
novapaw daemon version
novapaw daemon logs -n 50
```

---

## Models & environment variables

Before using NovaPaw you need at least one LLM provider configured. Environment
variables power many built-in tools (e.g. web search).

### novapaw models

Manage LLM providers and the active model.

| Command                                  | What it does                                         |
| ---------------------------------------- | ---------------------------------------------------- |
| `novapaw models list`                    | Show all providers, API key status, and active model |
| `novapaw models config`                  | Full interactive setup: API keys → active model      |
| `novapaw models config-key [provider]`   | Configure a single provider's API key                |
| `novapaw models set-llm`                 | Switch the active model (API keys unchanged)         |
| `novapaw models download <repo_id>`      | Download a local model (llama.cpp / MLX)             |
| `novapaw models local`                   | List downloaded local models                         |
| `novapaw models remove-local <model_id>` | Delete a downloaded local model                      |
| `novapaw models ollama-pull <model>`     | Download an Ollama model                             |
| `novapaw models ollama-list`             | List Ollama models                                   |
| `novapaw models ollama-remove <model>`   | Delete an Ollama model                               |

```bash
novapaw models list                    # See what's configured
novapaw models config                  # Full interactive setup
novapaw models config-key modelscope   # Just set ModelScope's API key
novapaw models config-key dashscope    # Just set DashScope's API key
novapaw models config-key custom       # Set custom provider (Base URL + key)
novapaw models set-llm                 # Change active model only
```

#### Local models

NovaPaw can also run models locally via llama.cpp or MLX — no API key needed.
Install the backend first: `pip install 'novapaw[llamacpp]'` or
`pip install 'novapaw[mlx]'`.

```bash
# Download a model (auto-selects Q4_K_M GGUF)
novapaw models download Qwen/Qwen3-4B-GGUF

# Download an MLX model
novapaw models download Qwen/Qwen3-4B --backend mlx

# Download from ModelScope
novapaw models download Qwen/Qwen2-0.5B-Instruct-GGUF --source modelscope

# List downloaded models
novapaw models local
novapaw models local --backend mlx

# Delete a downloaded model
novapaw models remove-local <model_id>
novapaw models remove-local <model_id> --yes   # skip confirmation
```

| Option      | Short | Default       | Description                                                           |
| ----------- | ----- | ------------- | --------------------------------------------------------------------- |
| `--backend` | `-b`  | `llamacpp`    | Target backend (`llamacpp` or `mlx`)                                  |
| `--source`  | `-s`  | `huggingface` | Download source (`huggingface` or `modelscope`)                       |
| `--file`    | `-f`  | _(auto)_      | Specific filename. If omitted, auto-selects (prefers Q4_K_M for GGUF) |

#### Ollama models

NovaPaw integrates with Ollama to run models locally. Models are dynamically loaded from your Ollama daemon — install Ollama first from [ollama.com](https://ollama.com).

Install the Ollama SDK: `pip install 'novapaw[ollama]'` (or re-run the installer with `--extras ollama`)

```bash
# Download an Ollama model
novapaw models ollama-pull mistral:7b
novapaw models ollama-pull qwen3:8b

# List Ollama models
novapaw models ollama-list

# Remove an Ollama model
novapaw models ollama-remove mistral:7b
novapaw models ollama-remove qwen3:8b --yes   # skip confirmation

# Use in config flow (auto-detects Ollama models)
novapaw models config           # Select Ollama → Choose from model list
novapaw models set-llm          # Switch to a different Ollama model
```

**Key differences from local models:**

- Models come from Ollama daemon (not downloaded by NovaPaw)
- Use `ollama-pull` / `ollama-remove` instead of `download` / `remove-local`
- Model list updates dynamically when you add/remove via Ollama CLI or NovaPaw

> **Note:** You are responsible for ensuring the API key is valid. NovaPaw does
> not verify key correctness. See [Config — LLM Providers](./config#llm-providers).

### novapaw env

Manage environment variables used by tools and skills at runtime.

| Command                     | What it does                  |
| --------------------------- | ----------------------------- |
| `novapaw env list`          | List all configured variables |
| `novapaw env set KEY VALUE` | Set or update a variable      |
| `novapaw env delete KEY`    | Delete a variable             |

```bash
novapaw env list
novapaw env set TAVILY_API_KEY "tvly-xxxxxxxx"
novapaw env set GITHUB_TOKEN "ghp_xxxxxxxx"
novapaw env delete TAVILY_API_KEY
```

> **Note:** NovaPaw only stores and loads these values; you are responsible for
> ensuring they are correct. See
> [Config — Environment Variables](./config#environment-variables).

---

## Channels

Connect NovaPaw to messaging platforms.

### novapaw channels

Manage channel configuration (iMessage, Discord, DingTalk, Feishu, QQ,
Console, etc.). **Note:** Use `config` for interactive setup (no `configure`
subcommand); use `remove` to uninstall custom channels (no `uninstall`).

| Command                          | What it does                                                                                                      |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `novapaw channels list`          | Show all channels and their status (secrets masked)                                                               |
| `novapaw channels install <key>` | Install a channel into `custom_channels/`: create stub or use `--path`/`--url`                                    |
| `novapaw channels add <key>`     | Install and add to config; built-in channels only get config entry; supports `--path`/`--url`                     |
| `novapaw channels remove <key>`  | Remove a custom channel from `custom_channels/` (built-ins cannot be removed); `--keep-config` keeps config entry |
| `novapaw channels config`        | Interactively enable/disable channels and fill in credentials                                                     |

```bash
novapaw channels list                    # See current status
novapaw channels install my_channel      # Create custom channel stub
novapaw channels install my_channel --path ./my_channel.py
novapaw channels add dingtalk            # Add DingTalk to config
novapaw channels remove my_channel       # Remove custom channel (and from config by default)
novapaw channels remove my_channel --keep-config   # Remove module only, keep config entry
novapaw channels config                 # Interactive configuration
```

The interactive `config` flow lets you pick a channel, enable/disable it, and enter credentials. It loops until you choose "Save and exit".

| Channel      | Fields to fill in                             |
| ------------ | --------------------------------------------- |
| **iMessage** | Bot prefix, database path, poll interval      |
| **Discord**  | Bot prefix, Bot Token, HTTP proxy, proxy auth |
| **DingTalk** | Bot prefix, Client ID, Client Secret          |
| **Feishu**   | Bot prefix, App ID, App Secret                |
| **QQ**       | Bot prefix, App ID, Client Secret             |
| **Console**  | Bot prefix                                    |

> For platform-specific credential setup, see [Channels](./channels).

---

## Cron (scheduled tasks)

Create jobs that run on a timed schedule — "every day at 9am", "every 2 hours
ask NovaPaw and send the reply". **Requires `novapaw app` to be running.**

### novapaw cron

| Command                        | What it does                                  |
| ------------------------------ | --------------------------------------------- |
| `novapaw cron list`            | List all jobs                                 |
| `novapaw cron get <job_id>`    | Show a job's spec                             |
| `novapaw cron state <job_id>`  | Show runtime state (next run, last run, etc.) |
| `novapaw cron create ...`      | Create a job                                  |
| `novapaw cron delete <job_id>` | Delete a job                                  |
| `novapaw cron pause <job_id>`  | Pause a job                                   |
| `novapaw cron resume <job_id>` | Resume a paused job                           |
| `novapaw cron run <job_id>`    | Run once immediately                          |

### Creating jobs

**Option 1 — CLI arguments (simple jobs)**

Two task types:

- **text** — send a fixed message to a channel on schedule.
- **agent** — ask NovaPaw a question on schedule and deliver the reply.

```bash
# Text: send "Good morning!" to DingTalk every day at 9:00
novapaw cron create \
  --type text \
  --name "Daily 9am" \
  --cron "0 9 * * *" \
  --channel dingtalk \
  --target-user "your_user_id" \
  --target-session "session_id" \
  --text "Good morning!"

# Agent: every 2 hours, ask NovaPaw and forward the reply
novapaw cron create \
  --type agent \
  --name "Check todos" \
  --cron "0 */2 * * *" \
  --channel dingtalk \
  --target-user "your_user_id" \
  --target-session "session_id" \
  --text "What are my todo items?"
```

Required: `--type`, `--name`, `--cron`, `--channel`, `--target-user`,
`--target-session`, `--text`.

**Option 2 — JSON file (complex or batch)**

```bash
novapaw cron create -f job_spec.json
```

JSON structure matches the output of `novapaw cron get <job_id>`.

### Additional options

| Option                       | Default | Description                                           |
| ---------------------------- | ------- | ----------------------------------------------------- |
| `--timezone`                 | `UTC`   | Timezone for the cron schedule                        |
| `--enabled` / `--no-enabled` | enabled | Create enabled or disabled                            |
| `--mode`                     | `final` | `stream` (incremental) or `final` (complete response) |
| `--base-url`                 | auto    | Override the API base URL                             |

### Cron expression cheat sheet

Five fields: **minute hour day month weekday** (no seconds).

| Expression     | Meaning                   |
| -------------- | ------------------------- |
| `0 9 * * *`    | Every day at 9:00         |
| `0 */2 * * *`  | Every 2 hours on the hour |
| `30 8 * * 1-5` | Weekdays at 8:30          |
| `0 0 * * 0`    | Sunday at midnight        |
| `*/15 * * * *` | Every 15 minutes          |

---

## Chats (sessions)

Manage chat sessions via the API. **Requires `novapaw app` to be running.**

### novapaw chats

| Command                                  | What it does                                                  |
| ---------------------------------------- | ------------------------------------------------------------- |
| `novapaw chats list`                     | List all sessions (supports `--user-id`, `--channel` filters) |
| `novapaw chats get <id>`                 | View a session's details and message history                  |
| `novapaw chats create ...`               | Create a new session                                          |
| `novapaw chats update <id> --name "..."` | Rename a session                                              |
| `novapaw chats delete <id>`              | Delete a session                                              |

```bash
novapaw chats list
novapaw chats list --user-id alice --channel dingtalk
novapaw chats get 823845fe-dd13-43c2-ab8b-d05870602fd8
novapaw chats create --session-id "discord:alice" --user-id alice --name "My Chat"
novapaw chats create -f chat.json
novapaw chats update <chat_id> --name "Renamed"
novapaw chats delete <chat_id>
```

---

## Skills

Extend NovaPaw's capabilities with skills (PDF reading, web search, etc.).

### novapaw skills

| Command                 | What it does                                      |
| ----------------------- | ------------------------------------------------- |
| `novapaw skills list`   | Show all skills and their enabled/disabled status |
| `novapaw skills config` | Interactively enable/disable skills (checkbox UI) |

```bash
novapaw skills list     # See what's available
novapaw skills config   # Toggle skills on/off interactively
```

In the interactive UI: ↑/↓ to navigate, Space to toggle, Enter to confirm.
A preview of changes is shown before applying.

> For built-in skill details and custom skill authoring, see [Skills](./skills).

---

## Maintenance

### novapaw clean

Remove everything under the working directory (default `~/.novapaw`).

```bash
novapaw clean             # Interactive confirmation
novapaw clean --yes       # No confirmation
novapaw clean --dry-run   # Only list what would be removed
```

---

## Global options

Every `novapaw` subcommand inherits:

| Option          | Default     | Description                                      |
| --------------- | ----------- | ------------------------------------------------ |
| `--host`        | `127.0.0.1` | API host (auto-detected from last `novapaw app`) |
| `--port`        | `8088`      | API port (auto-detected from last `novapaw app`) |
| `-h` / `--help` |             | Show help message                                |

If the server runs on a non-default address, pass these globally:

```bash
novapaw --host 0.0.0.0 --port 9090 cron list
```

## Working directory

All config and data live in `~/.novapaw` by default: `config.json`,
`HEARTBEAT.md`, `jobs.json`, `chats.json`, skills, memory, and agent persona
files.

| Variable              | Description                         |
| --------------------- | ----------------------------------- |
| `NOVAPAW_WORKING_DIR` | Override the working directory path |
| `NOVAPAW_CONFIG_FILE` | Override the config file path       |

See [Config & Working Directory](./config) for full details.

---

## Command overview

| Command            | Subcommands                                                                                                                            | Requires server? |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------- | :--------------: |
| `novapaw init`     | —                                                                                                                                      |        No        |
| `novapaw app`      | —                                                                                                                                      |  — (starts it)   |
| `novapaw models`   | `list` · `config` · `config-key` · `set-llm` · `download` · `local` · `remove-local` · `ollama-pull` · `ollama-list` · `ollama-remove` |        No        |
| `novapaw env`      | `list` · `set` · `delete`                                                                                                              |        No        |
| `novapaw channels` | `list` · `install` · `add` · `remove` · `config`                                                                                       |        No        |
| `novapaw cron`     | `list` · `get` · `state` · `create` · `delete` · `pause` · `resume` · `run`                                                            |     **Yes**      |
| `novapaw chats`    | `list` · `get` · `create` · `update` · `delete`                                                                                        |     **Yes**      |
| `novapaw skills`   | `list` · `config`                                                                                                                      |        No        |
| `novapaw clean`    | —                                                                                                                                      |        No        |

---

## Related pages

- [Introduction](./intro) — What NovaPaw can do
- [Console](./console) — Web-based management UI
- [Channels](./channels) — DingTalk, Feishu, iMessage, Discord, QQ setup
- [Heartbeat](./heartbeat) — Scheduled check-in / digest
- [Skills](./skills) — Built-in and custom skills
- [Config & Working Directory](./config) — Working directory and config.json
