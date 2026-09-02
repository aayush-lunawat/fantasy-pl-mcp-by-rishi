# Fantasy Premier League for your AI

Your AI assistant knows a lot about football and nothing about *this* gameweek. Ask it whether to captain Haaland and it will guess — confidently, from data that stopped being true months ago.

This connects it to the live Fantasy Premier League API. Every player's real form, expected goals, price, ownership and fixture run. Your squad, your mini-league, your rivals' transfers. Then you can actually argue with it about your team.

> **No login required.** Public FPL data needs nothing but a team ID — and a team ID isn't a secret. Connecting your actual FPL account is optional, and covered separately below.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://badge.fury.io/py/fpl-mcp.svg)](https://badge.fury.io/py/fpl-mcp)
[![Python](https://img.shields.io/pypi/pyversions/fpl-mcp)](https://pypi.org/project/fpl-mcp/)

---

## What you can ask it

- *"Is Mbeumo's form real, or has he just had easy fixtures?"*
- *"Find me a midfielder under £7.0m with better underlying numbers than the one I own."*
- *"Who in my mini-league is closest to me, and what do they own that I don't?"*
- *"I have a wildcard and two free transfers. Talk me through the next four gameweeks."*
- *"Which defenders take set pieces and have three good fixtures coming?"*

The point isn't that it answers. It's that it answers *with the numbers*, inside your own assistant, which remembers what you told it last week.

[![Demo](https://img.youtube.com/vi/QfOOOQ_jeMA/0.jpg)](https://youtu.be/QfOOOQ_jeMA)

---

## What it can see

![What it can see](docs/what-it-knows.svg)

---

## How to connect

![Two ways to connect](docs/how-it-connects.svg)

Pick the row that matches you.

### A · I just want to ask questions (2 minutes, no install)

Best for phones, and for anyone who doesn't want to install anything. You'll need the URL of a running server — either one someone shared with you, or your own from section B.

**Claude** — works on the free plan.

1. Open [claude.ai](https://claude.ai) in a browser on a computer
2. **Settings → Connectors → Add custom connector**
3. Paste the server URL, click **Add**
4. Open Claude on your phone — it's there too

**ChatGPT** — needs a paid plan, and **does not work in the ChatGPT mobile app**. On desktop web: Settings → enable Developer Mode → add a connector pointing at the same URL.

### B · I want to run it myself

Needed for your own live squad data, and for anyone hosting a server for others.

**Requirements:** Python 3.10+.

```bash
pip install fpl-mcp
```

**For a desktop assistant** (Claude Desktop, Cursor, Hermes) — it runs on demand, with no server to keep alive. Add this to your client's MCP configuration:

```json
{
  "mcpServers": {
    "fantasy-pl": {
      "command": "python",
      "args": ["-m", "fpl_mcp"]
    }
  }
}
```

For Claude Desktop that file lives at:
- macOS — `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows — `%APPDATA%\Claude\claude_desktop_config.json`

Restart the client afterwards. If it can't start the server, see Troubleshooting — it's almost always PATH.

**To host it over HTTP** so phones and ChatGPT can reach it:

```bash
fpl-mcp --transport streamable-http --port 8000
```

That listens on `127.0.0.1:8000/mcp` — local only, deliberately. To let the outside world in, put a reverse proxy with HTTPS in front. Both Claude and ChatGPT require HTTPS and will not connect to a plain `http://` address.

| Flag | Default | What it does |
|---|---|---|
| `--transport` | `stdio` | `stdio` for desktop clients, `streamable-http` for hosting, `sse` for older clients |
| `--host` | `127.0.0.1` | Bind address. Change only if nothing is proxying in front |
| `--port` | `8000` | Port for HTTP transports |
| `--path` | `/mcp` | URL path the endpoint is served on |

Environment equivalents: `FPL_MCP_TRANSPORT`, `FPL_MCP_HOST`, `FPL_MCP_PORT`, `FPL_MCP_PATH`.

> **Setting this up with an AI agent instead of by hand?** Point it at [AGENTS.md](AGENTS.md), written for exactly that.

---

## Finding your team ID

**It is not in the Premier League mobile app** — no screen shows it. Use a browser:

1. Sign in at [fantasy.premierleague.com](https://fantasy.premierleague.com)
2. Click **Points**
3. Read the address bar:

```
fantasy.premierleague.com/entry/1234567/event/3
                                ^^^^^^^
                                your team ID
```

Works the same in a phone browser — tap the address bar to see the full URL, and make sure it's a real browser rather than one embedded in another app, which often hides the address.

**Is it safe to share?** Yes. Your team ID already appears in the URL whenever anyone in your mini-league clicks your name. With it, someone can see your points, rank, past squads, transfer history and leagues. They cannot log in, make transfers, or change anything.

One thing worth knowing: your registered first and last name are public alongside it. That's how FPL works generally, not something this adds.

---

## Connecting your own FPL account (optional)

Only needed for your *current* gameweek squad before the deadline, your selling prices, your bank, or your remaining chips. Everything else works without it.

**Only ever do this on a server you run yourself.** Never give your FPL credentials to someone else's hosted endpoint — including one a friend sent you.

```bash
fpl-mcp-config setup
```

You'll be asked for your team ID and a refresh token, copied from `oidc.user` in your browser's Local Storage while signed in to FPL. Credentials are encrypted at rest in `~/.fpl-mcp/credentials.enc`, tied to your machine.

Two things to expect: authenticating retires the token your browser holds, so you'll be signed out of FPL on the web once. And tokens expire periodically, so this isn't quite set-and-forget.

---

## Tools

23 tools. Those marked 🔒 need your own credentials; everything else works with just a team ID.

**Players** — `analyze_players`, `compare_players`, `get_player_information`, `search_fpl_players`, `get_price_changes`

**Fixtures and gameweeks** — `analyze_fixtures`, `analyze_player_fixtures`, `get_gameweek_status`, `get_blank_gameweeks`, `get_double_gameweeks`

**Live** — `get_gameweek_live_scores`, `get_dream_team`

**Teams and leagues** — `get_team`, `get_manager`, `get_manager_info`, `get_manager_transfer_history`, `get_league_standings`, `get_league_analytics`

**Your account** — 🔒 `get_my_team`, 🔒 `get_my_current_team`, 🔒 `suggest_captain`, 🔒 `check_fpl_authentication`, 🔒 `update_fpl_credentials`

Plus 5 prompts (transfer advice, player analysis, team rating, differentials, chip strategy) and resources at `fpl://static/players`, `fpl://static/players/{name}`, `fpl://static/teams`, `fpl://static/teams/{name}`, `fpl://gameweeks/current` and `fpl://gameweeks/all`.

---

## Troubleshooting

**Client can't find `fpl-mcp` / `spawn fpl-mcp ENOENT`** — the install directory isn't on the PATH your client sees, because desktop clients launch the server without loading your shell profile. Run `which fpl-mcp` (`where` on Windows) and use that full path in the config, or use the `python -m fpl_mcp` form above. This is the most common setup failure by a distance.

**"No team ID specified"** — pass your team ID explicitly. See above for finding it.

**Claude or ChatGPT won't connect to a hosted URL** — it must be HTTPS and reachable from the public internet. Neither connects to `http://`, to `localhost`, or to anything behind a VPN.

**Authentication errors on tools that shouldn't need them** — you're on an older version. Public data no longer requires credentials. Upgrade with `pip install -U fpl-mcp`.

---

## Development

```bash
git clone https://github.com/rishijatia/fantasy-pl-mcp.git
cd fantasy-pl-mcp
pip install -e ".[dev]"
pytest
```

Inspect the server interactively with `mcp dev -m fpl_mcp`, or `npx @modelcontextprotocol/inspector python -m fpl_mcp`.

---

## Credits and licence

Built on [rishijatia/fantasy-pl-mcp](https://github.com/rishijatia/fantasy-pl-mcp) by **Rishi Jatia**. The server, its tools and the FPL authentication flow are his work. MIT licensed — © 2025 Fantasy PL MCP Contributors.

This fork adds HTTP transport for hosting, and removes the credential requirement from FPL endpoints that were always public.

Not affiliated with the Premier League or Fantasy Premier League. It reads the same public API your browser does.
