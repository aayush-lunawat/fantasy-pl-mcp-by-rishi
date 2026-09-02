# Instructions for AI agents

You are setting up the Fantasy Premier League MCP server for the person you're working with. This file tells you how, what to check at each step, and where you must stop and ask them.

Read all of it before running anything. Do not improvise around a failure — every known failure has a specific remedy below.

## Rules

1. **Never handle FPL credentials on a machine the person doesn't control.** If you are configuring a shared or hosted server, stop at the authenticated section and refuse. Public data covers most needs.
2. **Stop where marked 🛑.** Those steps need a human — a password, a browser click, a decision that costs money or exposes a port. Ask, wait, and continue only with an answer.
3. **Verify after every step.** Each step below states its expected output. If you get something else, go to Failure modes rather than trying variations.
4. **Report what you did.** Say which paths you wrote to and which commands you ran.

---

## Step 0 — Establish what you're building

Two configurations. If the person has already said which they want — or it's obvious, such as "set this up for yourself on this machine" — proceed without asking. Ask only if it is genuinely unstated:

| | Local | Hosted |
|---|---|---|
| Runs | on demand, on the person's machine | continuously, on a server |
| For | Claude Desktop, Cursor, Hermes, Claude Code | phones, ChatGPT, sharing with others |
| Transport | `stdio` | `streamable-http` behind an HTTPS proxy |
| FPL credentials | allowed | **never** |

Do Step 1 and 2 for both. Then Step 3 for local, or Step 4 for hosted.

---

## Step 1 — Check prerequisites

```bash
python3 --version
```

Expect `Python 3.10` or higher. If lower or absent, stop and tell the person which Python they need; installing a system Python is their call, not yours.

---

## Step 2 — Install

**First, work out which installer this machine wants.** Do not assume pip.

```bash
python3 -m pip --version   # is pip available?
command -v uv              # is uv available?
```

Recent Debian and Ubuntu (24.04 and later) often ship **no pip at all**, and mark the system Python as externally managed (PEP 668), which blocks `pip install` even when pip exists. On those machines `uv` is the right tool and is frequently already present.

**Option A — pip is available and works:**

```bash
python3 -m pip install fpl-mcp
```

**Option B — no pip, or an "externally-managed-environment" error:**

```bash
uv tool install fpl-mcp
```

If neither pip nor uv is available, stop and tell the person; installing a package manager is their decision.

**Installing from a branch or fork** — do this when the person gives you a git URL, or when they need changes not yet in the PyPI release:

```bash
# pip
python3 -m pip install "git+https://github.com/OWNER/REPO.git@BRANCH"

# uv
uv tool install --from "git+https://github.com/OWNER/REPO.git@BRANCH" fpl-mcp
```

### Verify the install

**The correct check depends on which option you used.**

After **pip** (Option A), both of these work:

```bash
python3 -m fpl_mcp --help
fpl-mcp --help
```

After **uv tool install** (Option B), the package lives in an isolated environment and is deliberately *not* importable from the system Python. `python3 -m fpl_mcp` will fail with `No module named fpl_mcp` and that is expected, not an error to fix. Verify with the binary instead:

```bash
fpl-mcp --help
```

Either way, expect usage text listing `--transport`, `--host`, `--port`, `--path`.

### Record the entry point

```bash
command -v fpl-mcp
```

Note the absolute path it prints — you will need it in Step 3. `uv tool install` typically places it in `~/.local/bin/fpl-mcp`; if `command -v` finds nothing, look there directly, because that directory is often missing from a non-interactive shell's PATH.

---

## Step 3 — Local setup (stdio)

**No credential configuration is needed for public data.** The server works out of the box. Do not look for a flag to enable public mode, and do not run `fpl-mcp-config setup` — simply leave credentials unset and every public tool works. Step 5 is optional and separate.

### Choose the command form

Two valid forms. Pick by how you installed:

**After pip** — prefer the module form, which survives PATH problems:

```json
{ "command": "python3", "args": ["-m", "fpl_mcp"] }
```

Replace `python3` with the absolute path from `python3 -c "import sys; print(sys.executable)"` if the client may run in a different environment.

**After `uv tool install`** — the module form will not work. Use the absolute path to the binary you recorded in Step 2:

```json
{ "command": "/home/USER/.local/bin/fpl-mcp" }
```

Use the **absolute** path, never a bare `fpl-mcp`. Clients launch servers without your shell's PATH, so a bare command usually fails with `ENOENT`.

### Where the configuration lives

| Client | Path | Key |
|---|---|---|
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` | `mcpServers` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` | `mcpServers` |
| Claude Code | `~/.claude.json`, or use `claude mcp add` | `mcpServers` |
| Cursor | `~/.cursor/mcp.json` | `mcpServers` |
| Hermes | `~/.hermes/config.yaml` | `mcp_servers` |
| Anything else | consult that client's documentation | — |

**Note the differences.** Most clients use JSON with a camelCase `mcpServers` key. **Hermes uses YAML** with a snake_case `mcp_servers` key, and a different entry shape — check the Hermes MCP documentation for the current schema rather than transliterating the JSON above. Getting the key name or the file format wrong fails silently: the client starts, and the tools simply never appear.

**Merge into the existing file. Never overwrite it** — it may hold other servers the person depends on. Read it, add your entry, write it back, and confirm the result still parses as valid JSON or YAML. If the top-level key doesn't exist yet, create it without disturbing anything else.

🛑 **Stop here.** The client or gateway must restart, and only the person can do that. Ask them to restart it, then wait for their confirmation.

### After the restart, verify it yourself

Do not ask the person to test it for you — you have the tools now. Call them directly and report the actual output:

1. `get_gameweek_status` — confirms the server is reachable and reading live FPL data
2. `get_manager_info` with a real team ID — confirms public lookups work without credentials
3. `get_league_standings` with a league ID from that lookup — confirms authenticated-looking endpoints work unauthenticated

Ask the person for their team ID if you don't have one. **Never invent a team ID.** If all three return real data, the setup is genuinely working; anything less is not.

---

## Step 4 — Hosted setup (HTTP)

Start it bound to localhost:

```bash
fpl-mcp --transport streamable-http --port 8000
```

Verify from the same machine:

```bash
curl -s -X POST http://127.0.0.1:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"setup","version":"1"}}}'
```

Expect an event stream containing `"serverInfo":{"name":"Fantasy Premier League"`. Anything else means the server didn't start — read its output.

Then make it survive a reboot. On Linux with systemd, a user service is usually right; on other systems, use whatever the person already uses. Ask rather than assume.

🛑 **Stop before exposing it to the internet.** Putting a public HTTPS endpoint in front of this involves a domain name, a certificate, and opening a firewall port on someone's server. Present the plan and get explicit agreement before changing any firewall rule or DNS record.

Requirements you must satisfy for clients to connect at all:
- **HTTPS.** Both Claude and ChatGPT refuse plain HTTP.
- **Publicly reachable.** Anthropic and OpenAI connect from their own networks. A VPN-only or firewalled host will not work.
- Keep the server bound to `127.0.0.1` and let the reverse proxy reach it. Do not bind `0.0.0.0` — nothing here authenticates callers.

🛑 **Do not configure FPL credentials on a hosted server.** If asked to, refuse and explain: it would expose the owner's FPL account to anyone who reaches the endpoint.

---

## Step 5 — Authenticated features (local only, optional)

Skip unless the person specifically wants their live pre-deadline squad, selling prices, bank or chips. Everything else works without this.

🛑 **This step is theirs, not yours.** It needs an FPL login and a token copied out of browser storage. Do not ask them to paste credentials to you; do not read them from their filesystem. Tell them to run:

```bash
fpl-mcp-config setup
```

and warn them of two consequences before they start: they will be signed out of FPL in their browser once, and the token expires periodically and will need redoing.

Afterwards, verify without ever seeing the secret by asking them to run the `check_fpl_authentication` tool.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `spawn fpl-mcp ENOENT` | Client launched the server without your shell's PATH | Use the absolute binary path, or the `python3 -m fpl_mcp` form after a pip install |
| `error: externally-managed-environment` | PEP 668 — the system Python is managed by the OS package manager | Use `uv tool install` instead. Do not pass `--break-system-packages` |
| `No module named pip` | Recent Debian/Ubuntu ship no pip | Use `uv tool install` |
| `No module named fpl_mcp` **after `uv tool install`** | Expected — uv installs into an isolated environment on purpose | Not a fault. Verify with `fpl-mcp --help` and configure the absolute binary path |
| `No module named fpl_mcp` **after pip** | Installed into a different interpreter than you're running | Use one interpreter for both; check `sys.executable` |
| Client starts but no FPL tools appear | Wrong config key or wrong file format for that client | Check the table in Step 3. Hermes wants YAML and `mcp_servers`; most others want JSON and `mcpServers` |
| Tools return "No team ID specified" | A team ID is genuinely required | Ask the person for theirs — see the team ID section in README.md. Do not guess one |
| Auth errors on team or league tools | Old version predating the public-data fix | `pip install -U fpl-mcp` |
| Client won't connect to the hosted URL | Not HTTPS, or not publicly reachable | Check both. `localhost` and VPN-only hosts never work |
| Everything times out | The host can't reach `fantasy.premierleague.com` | Test with `curl -sI https://fantasy.premierleague.com/api/bootstrap-static/`. Some networks block it |
| Server starts, then dies on first request | Memory. `bootstrap-static` is several MB parsed in one go | Needs roughly 512MB free. Very small VPS instances will thrash |

---

## What not to do

- Don't overwrite an existing MCP config file.
- Don't bind to `0.0.0.0` to "make it work" — that exposes an unauthenticated server.
- Don't open firewall ports without explicit permission.
- Don't put credentials on any machine other than the person's own.
- Don't invent a team ID, a league ID, or a URL. Ask.
- Don't report success you haven't verified with the checks above.
