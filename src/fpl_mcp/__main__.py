#!/usr/bin/env python3

import argparse
import logging
import asyncio
import atexit
import os
from typing import List, Dict, Any, Optional

# Import MCP
from mcp.server.fastmcp import FastMCP

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fpl-mcp-server")

# Create MCP server
mcp = FastMCP(
    name="Fantasy Premier League",
    instructions="Access Fantasy Premier League data and tools",
    dependencies=["httpx", "diskcache", "jsonschema"],
)

# Import modules that use the mcp variable
from .fpl.resources import players, teams, gameweeks, fixtures
from .fpl.tools import (
    register_advice_tools,
    register_analysis_tools,
    register_fixture_tools,
    register_gameweek_tools,
    register_league_tools,
    register_live_tools,
    register_manager_tools,
    register_player_tools,
    register_team_tools,
)

# Register resources
@mcp.resource("fpl://static/players")
async def get_all_players() -> List[Dict[str, Any]]:
    """Get a formatted list of all players with comprehensive statistics"""
    logger.info("Resource requested: fpl://static/players")
    players_data = await players.get_players_resource()
    return players_data

@mcp.resource("fpl://static/players/{name}")
async def get_player_by_name(name: str) -> Dict[str, Any]:
    """Get player information by searching for their name"""
    logger.info(f"Resource requested: fpl://static/players/{name}")
    player_matches = await players.find_players_by_name(name)
    if not player_matches:
        return {"error": f"No player found matching '{name}'"}
    return player_matches[0]

@mcp.resource("fpl://static/teams")
async def get_all_teams() -> List[Dict[str, Any]]:
    """Get a formatted list of all Premier League teams with strength ratings"""
    logger.info("Resource requested: fpl://static/teams")
    teams_data = await teams.get_teams_resource()
    return teams_data

@mcp.resource("fpl://static/teams/{name}")
async def get_team_by_name(name: str) -> Dict[str, Any]:
    """Get team information by searching for their name"""
    logger.info(f"Resource requested: fpl://static/teams/{name}")
    team = await teams.get_team_by_name(name)
    if not team:
        return {"error": f"No team found matching '{name}'"}
    return team

@mcp.resource("fpl://gameweeks/current")
async def get_current_gameweek() -> Dict[str, Any]:
    """Get information about the current gameweek"""
    logger.info("Resource requested: fpl://gameweeks/current")
    gameweek_data = await gameweeks.get_current_gameweek_resource()
    return gameweek_data

@mcp.resource("fpl://gameweeks/all")
async def get_all_gameweeks() -> List[Dict[str, Any]]:
    """Get information about all gameweeks"""
    logger.info("Resource requested: fpl://gameweeks/all")
    gameweeks_data = await gameweeks.get_gameweeks_resource()
    return gameweeks_data

@mcp.resource("fpl://fixtures")
async def get_all_fixtures() -> List[Dict[str, Any]]:
    """Get all fixtures for the current Premier League season"""
    logger.info("Resource requested: fpl://fixtures")
    fixtures_data = await fixtures.get_fixtures_resource()
    return fixtures_data

@mcp.resource("fpl://fixtures/gameweek/{gameweek_id}")
async def get_gameweek_fixtures(gameweek_id: int) -> List[Dict[str, Any]]:
    """Get fixtures for a specific gameweek"""
    logger.info(f"Resource requested: fpl://fixtures/gameweek/{gameweek_id}")
    fixtures_data = await fixtures.get_fixtures_resource(gameweek_id=gameweek_id)
    return fixtures_data

@mcp.resource("fpl://fixtures/team/{team_name}")
async def get_team_fixtures(team_name: str) -> List[Dict[str, Any]]:
    """Get fixtures for a specific team"""
    logger.info(f"Resource requested: fpl://fixtures/team/{team_name}")
    fixtures_data = await fixtures.get_fixtures_resource(team_name=team_name)
    return fixtures_data

@mcp.resource("fpl://players/{player_name}/fixtures")
async def get_player_fixtures_by_name(player_name: str) -> Dict[str, Any]:
    """Get upcoming fixtures for a specific player"""
    logger.info(f"Resource requested: fpl://players/{player_name}/fixtures")

    # Find the player
    player_matches = await players.find_players_by_name(player_name)
    if not player_matches:
        return {"error": f"No player found matching '{player_name}'"}

    player = player_matches[0]
    player_fixtures = await fixtures.get_player_fixtures(player["id"])

    return {
        "player": {
            "name": player["name"],
            "team": player["team"],
            "position": player["position"]
        },
        "fixtures": player_fixtures
    }

@mcp.resource("fpl://gameweeks/blank")
async def get_blank_gameweeks_resource() -> List[Dict[str, Any]]:
    """Get information about upcoming blank gameweeks"""
    logger.info("Resource requested: fpl://gameweeks/blank")
    blank_gameweeks = await fixtures.get_blank_gameweeks()
    return blank_gameweeks

@mcp.resource("fpl://gameweeks/double")
async def get_double_gameweeks_resource() -> List[Dict[str, Any]]:
    """Get information about upcoming double gameweeks"""
    logger.info("Resource requested: fpl://gameweeks/double")
    double_gameweeks = await fixtures.get_double_gameweeks()
    return double_gameweeks

# Register all tools
register_team_tools(mcp)
register_manager_tools(mcp)
register_league_tools(mcp)
register_player_tools(mcp)
register_gameweek_tools(mcp)
register_fixture_tools(mcp)
register_analysis_tools(mcp)
register_live_tools(mcp)
register_advice_tools(mcp)

# Register prompts
@mcp.prompt()
def transfer_advice_prompt(budget: float, position: str = None, team_to_sell: str = None) -> str:
    """Create a prompt for getting detailed FPL transfer advice

    Args:
        budget: Available budget in millions (e.g., 8.5)
        position: Optional position to target (e.g., MID, FWD, DEF, GKP)
        team_to_sell: Optional team name if selling a player from that team
    """
    position_text = f"a {position}" if position else "any position"
    team_text = f" to replace a player from {team_to_sell}" if team_to_sell else ""

    return (
        f"I need transfer advice for my Fantasy Premier League team. "
        f"I have £{budget}m to spend on {position_text}{team_text}. "
        f"\n\nPlease recommend the best options considering:"
        f"\n1. Current form and consistency"
        f"\n2. Upcoming fixture difficulty"
        f"\n3. Value for money compared to similar players"
        f"\n4. Blank/double gameweeks that might affect performance"
        f"\n5. Expected returns based on xG, xA, and other advanced metrics"
        f"\n\nFor each recommendation, please explain your reasoning and any potential risks."
    )

@mcp.prompt()
def player_analysis_prompt(player_name: str, include_comparisons: bool = True) -> str:
    """Create a prompt for analyzing an FPL player in depth

    Args:
        player_name: Name of the player to analyze
        include_comparisons: Whether to compare with similar players
    """
    comparison_text = (
        "\n5. How they compare to similar players in their position and price range"
        if include_comparisons else ""
    )

    return (
        f"Please provide a comprehensive analysis of {player_name} as an FPL asset. "
        f"I'd like to understand:"
        f"\n\n1. Recent form, performance statistics, and underlying metrics (xG, xA)"
        f"\n2. Upcoming fixtures and their difficulty ratings"
        f"\n3. Value for money compared to their price point"
        f"\n4. Consistency of returns and minutes played (rotation risks) {comparison_text}"
        f"\n5. Consider other similar players in the same position and price range"
        f"\n6. Any potential blank or double gameweeks that might affect their performance"
        f"\n7. Any injury concerns or fitness issues"
        f"\n8. Any other relevant factors that could impact their performance"
        f"\n\nBased on this analysis, would you recommend buying, holding, or selling this player for the upcoming gameweeks?"
    )


@mcp.prompt()
def team_rating_prompt(player_list: str, budget_remaining: float = 0.0) -> str:
    """Create a prompt for rating and analyzing an FPL team

    Args:
        player_list: Comma-separated list of players in the team
        budget_remaining: Remaining budget in millions
    """
    return (
        f"Please rate and analyze my Fantasy Premier League team consisting of the following players:\n\n{player_list}"
        f"\n\nI have £{budget_remaining}m remaining in my budget."
        f"\n\nPlease provide:"
        f"\n1. An overall rating of my team (1-10)"
        f"\n2. Strengths and weaknesses in my team structure"
        f"\n3. Analysis of fixture coverage for the upcoming gameweeks"
        f"\n4. Suggested improvements or transfers to consider based on player form, fixtures and value"
        f"\n5. Players who might be rotation risks (based on minutes played) or have challenging fixtures"
        f"\n6. Any players I should consider captaining in the upcoming gameweek"
        f"\n7. Any injury concerns or fitness issues that might affect my players"
        f"\n\nFor each recommendation, please explain your reasoning and any potential risks."
    )


@mcp.prompt()
def differential_players_prompt(max_ownership: float = 10.0, budget: float = None) -> str:
    """Create a prompt for finding differential players with low ownership

    Args:
        max_ownership: Maximum ownership percentage to consider
        budget: Optional maximum budget per player in millions
    """
    budget_text = f" with a maximum price of £{budget}m" if budget else ""

    return (
        f"I'm looking for differential players with less than {max_ownership}% ownership{budget_text} "
        f"who could provide good value in the coming gameweeks."
        f"\n\nPlease suggest differentials for each position (GKP, DEF, MID, FWD) considering:"
        f"\n1. Recent form and underlying performance statistics"
        f"\n2. Upcoming fixture difficulty"
        f"\n3. Expected minutes and rotation risk"
        f"\n4. Set-piece involvement and penalty duties"
        f"\n5. Team attacking/defensive strength"
        f"\n\nFor each player, please explain why they might outperform their ownership percentage."
    )

@mcp.prompt()
def chip_strategy_prompt(available_chips: str) -> str:
    """Create a prompt for chip strategy advice

    Args:
        available_chips: Comma-separated list of available chips (e.g., "Wildcard, Free Hit, Bench Boost")
    """
    return (
        f"I still have the following FPL chips available: {available_chips}."
        f"\n\nPlease advise on the optimal strategy for using these chips considering:"
        f"\n1. Upcoming blank and double gameweeks"
        f"\n2. Fixture difficulty swings for top teams"
        f"\n3. Potential injury crises or international breaks"
        f"\n4. The current stage of the season"
        f"\n\nFor each chip, suggest specific gameweeks or scenarios when I should consider using them, "
        f"and explain the reasoning behind your recommendations."
    )


# Add cleanup for auth manager
def cleanup_auth():
    """Clean up authentication resources"""
    try:
        from .fpl.auth_manager import get_auth_manager
        auth_manager = get_auth_manager()

        # Create an event loop if none exists
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run the close method
        if loop.is_running():
            loop.create_task(auth_manager.close())
        else:
            loop.run_until_complete(auth_manager.close())
    except Exception as e:
        logger.error(f"Error during authentication cleanup: {e}")

# Register cleanup
atexit.register(cleanup_auth)

# Main function for direct execution and entry point
def _build_arg_parser() -> "argparse.ArgumentParser":
    parser = argparse.ArgumentParser(
        prog="fpl-mcp",
        description="Fantasy Premier League MCP server.",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.environ.get("FPL_MCP_TRANSPORT", "stdio"),
        help=(
            "How clients connect. 'stdio' (default) is for desktop clients "
            "that launch this server themselves, such as Claude Desktop, "
            "Cursor and Hermes. 'streamable-http' serves over HTTP so the "
            "server can be hosted and reached by a URL, which is what "
            "ChatGPT and Claude's web and mobile apps require. 'sse' is the "
            "older HTTP transport, kept for older clients. "
            "Env: FPL_MCP_TRANSPORT"
        ),
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("FPL_MCP_HOST", "127.0.0.1"),
        help=(
            "Interface to bind for HTTP transports. Defaults to 127.0.0.1, "
            "which accepts connections only from the same machine — the "
            "right choice when a reverse proxy in front terminates TLS. "
            "Use 0.0.0.0 only if you intend to expose the server directly. "
            "Env: FPL_MCP_HOST"
        ),
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FPL_MCP_PORT", "8000")),
        help="Port for HTTP transports (default: 8000). Env: FPL_MCP_PORT",
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("FPL_MCP_PATH", "/mcp"),
        help=(
            "URL path the MCP endpoint is served on for streamable-http "
            "(default: /mcp). Env: FPL_MCP_PATH"
        ),
    )
    parser.add_argument(
        "--allowed-host",
        action="append",
        dest="allowed_hosts",
        default=None,
        metavar="HOST",
        help=(
            "Public hostname this server is reached at, e.g. "
            "fpl.example.com. REQUIRED when hosting behind a reverse proxy "
            "or a domain name: the MCP SDK rejects any request whose Host "
            "header it doesn't recognise, answering 'Invalid Host header', "
            "and by default it recognises only localhost. Repeat the flag "
            "for several names. Localhost is always kept. "
            "Env: FPL_MCP_ALLOWED_HOSTS (comma-separated)"
        ),
    )
    return parser


def _build_transport_security(hosts: List[str], port: int):
    """Build DNS-rebinding-protection settings that permit `hosts`.

    The SDK matches the Host header exactly, and a request arriving over
    HTTPS on 443 carries no port in that header while one on another port
    does. Accept both shapes, and keep the loopback entries so local
    testing and health checks continue to work.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    allowed_hosts: List[str] = [
        "127.0.0.1",
        f"127.0.0.1:{port}",
        "localhost",
        f"localhost:{port}",
    ]
    allowed_origins: List[str] = [
        f"http://127.0.0.1:{port}",
        f"http://localhost:{port}",
    ]

    for host in hosts:
        # Tolerate a scheme or a path being pasted in by mistake.
        cleaned = host.strip().removeprefix("https://").removeprefix("http://")
        cleaned = cleaned.split("/")[0]
        if not cleaned:
            continue
        allowed_hosts.extend([cleaned, f"{cleaned}:*"])
        allowed_origins.extend([f"https://{cleaned}", f"http://{cleaned}"])

    return TransportSecuritySettings(
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


def main(argv: Optional[List[str]] = None):
    """Run the Fantasy Premier League MCP server.

    Defaults to stdio so that existing desktop configurations keep working
    unchanged. HTTP transports are opt-in via --transport.
    """
    args = _build_arg_parser().parse_args(argv)

    if args.transport in ("sse", "streamable-http"):
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        if args.transport == "streamable-http":
            mcp.settings.streamable_http_path = args.path

        allowed_hosts = args.allowed_hosts
        if not allowed_hosts:
            env_hosts = os.environ.get("FPL_MCP_ALLOWED_HOSTS", "")
            allowed_hosts = [h for h in env_hosts.split(",") if h.strip()]
        if allowed_hosts:
            mcp.settings.transport_security = _build_transport_security(
                allowed_hosts, args.port
            )
            logger.info("Accepting requests for hosts: %s", ", ".join(allowed_hosts))
        else:
            logger.warning(
                "No --allowed-host given, so only localhost requests will be "
                "accepted. If this server sits behind a reverse proxy or a "
                "domain name, clients will get 'Invalid Host header' (HTTP "
                "421) until you pass --allowed-host YOUR.DOMAIN"
            )
        logger.info(
            "Starting Fantasy Premier League MCP Server on %s://%s:%s%s",
            args.transport,
            args.host,
            args.port,
            args.path if args.transport == "streamable-http" else "/sse",
        )
        if args.host == "0.0.0.0":
            logger.warning(
                "Binding to 0.0.0.0 exposes this server on every network "
                "interface with no authentication in front of it. Put a "
                "reverse proxy with TLS in front, or bind 127.0.0.1."
            )
    else:
        logger.info("Starting Fantasy Premier League MCP Server (stdio)")

    mcp.run(transport=args.transport)

# Run the server if executed directly
if __name__ == "__main__":
    main()
