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

Two configurations. Ask if it isn't clear from context:

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

```bash
python3 -m pip install fpl-mcp
```

Verify:

```bash
python3 -m fpl_mcp --help
```

Expect usage text listing `--transport`, `--host`, `--port`, `--path`. If you get `No module named fpl_mcp`, the install went to a different interpreter than the one you're invoking — use the same `python3` for both, or a virtual environment.

Record the absolute path for later:

```bash
python3 -c "import shutil; print(shutil.which('fpl-mcp'))"
```

If that prints `None`, use the `python -m fpl_mcp` form in configuration instead. Do not put a bare `fpl-mcp` command in any config file — see Failure modes.

---

## Step 3 — Local setup (stdio)

Add the server to the client's MCP configuration. Use the module form, which survives PATH problems:

```json
{
  "mcpServers": {
    "fantasy-pl": {
      "command": "python3",
      "args": ["-m", "fpl_mcp"]
    }
  }
}
```

Replace `python3` with the absolute interpreter path from `python3 -c "import sys; print(sys.executable)"` if the client runs in a different environment.

Config locations:
- Claude Desktop, macOS — `~/Library/Application Support/Claude/claude_desktop_config.json`
- Claude Desktop, Windows — `%APPDATA%\Claude\claude_desktop_config.json`
- Other clients — consult their documentation; do not guess a path

**Merge into the existing file. Never overwrite it** — it may hold other servers the person depends on. Read it, add your key under `mcpServers`, write it back, and confirm the result is valid JSON.

🛑 **Stop here.** The client must be restarted, and only the person can do that. Ask them to restart it and confirm the FPL tools appear.

Then verify with a real call — ask them to try *"What's the current FPL gameweek status?"* A correct answer means the whole chain works.

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
| `spawn fpl-mcp ENOENT` | Client launched the server without your shell's PATH | Use `python3 -m fpl_mcp`, or the absolute path from `shutil.which` |
| `No module named fpl_mcp` | Installed into a different interpreter | Use one interpreter for install and run; check `sys.executable` |
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
