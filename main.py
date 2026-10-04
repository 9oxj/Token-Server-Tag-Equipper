import argparse
import inspect
import sys

import discord
from colorama import init


# ============================================================
# CONFIG
# ============================================================

TOKEN = ""

# Used when you run:
#   python main.py equip
#
# You can override it with:
#   python main.py equip 123456789012345678
DEFAULT_GUILD_ID = 1452847491086291018


# ============================================================
# COLOR / UI
# ============================================================

init(autoreset=True)

RESET = "\033[0m"
BOLD = "\033[1m"


def rgb(r: int, g: int, b: int) -> str:
    """Return an ANSI true-color escape sequence."""
    return f"\033[38;2;{r};{g};{b}m"


def gradient(
    text: str,
    start=(90, 120, 255),
    end=(210, 80, 255),
) -> str:
    """Apply a smooth RGB gradient across text."""
    if not text:
        return ""

    result = []
    length = max(len(text) - 1, 1)

    for i, char in enumerate(text):
        ratio = i / length

        r = int(start[0] + (end[0] - start[0]) * ratio)
        g = int(start[1] + (end[1] - start[1]) * ratio)
        b = int(start[2] + (end[2] - start[2]) * ratio)

        result.append(f"{rgb(r, g, b)}{char}")

    return "".join(result) + RESET


def success(message: str):
    print(
        f"{rgb(80, 255, 160)}{BOLD}✓{RESET} "
        f"{rgb(190, 255, 220)}{message}{RESET}"
    )


def info(message: str):
    print(
        f"{rgb(100, 180, 255)}{BOLD}●{RESET} "
        f"{rgb(190, 220, 255)}{message}{RESET}"
    )


def warning(message: str):
    print(
        f"{rgb(255, 195, 70)}{BOLD}!{RESET} "
        f"{rgb(255, 220, 150)}{message}{RESET}"
    )


def error(message: str):
    print(
        f"{rgb(255, 75, 100)}{BOLD}✗{RESET} "
        f"{rgb(255, 175, 185)}{message}{RESET}"
    )


def print_banner():
    banner = r"""
╭──────────────────────────────────────╮
│          DISCORD TAG MANAGER         │
╰──────────────────────────────────────╯
"""

    print(
        gradient(
            banner,
            start=(70, 140, 255),
            end=(220, 70, 255),
        )
    )


# ============================================================
# ARGUMENTS
# ============================================================

parser = argparse.ArgumentParser(
    description="Equip or remove a Discord server tag."
)

subparsers = parser.add_subparsers(
    dest="command",
    required=True,
)


equip_parser = subparsers.add_parser(
    "equip",
    help="Equip a server tag.",
)

equip_parser.add_argument(
    "guild_id",
    nargs="?",
    type=int,
    default=DEFAULT_GUILD_ID,
    help="Guild ID whose server tag should be equipped.",
)


subparsers.add_parser(
    "remove",
    help="Remove the currently equipped server tag.",
)

args = parser.parse_args()


# ============================================================
# DISCORD
# ============================================================

client = discord.Client()

already_ran = False


def supports_primary_guild() -> bool:
    """
    Determine whether the installed discord.py-self build
    exposes ClientUser.edit(primary_guild=...).
    """

    try:
        parameters = inspect.signature(
            client.user.edit
        ).parameters

        return "primary_guild" in parameters

    except (TypeError, ValueError, AttributeError):
        return False


async def raw_set_tag(
    guild_id: int | None,
    enabled: bool,
):
    """Use Discord's clan/server-tag endpoint directly."""

    route = discord.http.Route(
        "PUT",
        "/users/@me/clan",
    )

    payload = {
        "identity_guild_id": (
            str(guild_id)
            if enabled and guild_id
            else None
        ),
        "identity_enabled": enabled,
    }

    return await client.http.request(
        route,
        json=payload,
    )


async def native_set_tag(
    guild_id: int | None,
    enabled: bool,
):
    """Use discord.py-self's native primary_guild implementation."""

    if enabled:
        guild = client.get_guild(guild_id)

        primary_guild = (
            guild
            if guild is not None
            else discord.Object(id=guild_id)
        )
    else:
        primary_guild = None

    await client.user.edit(
        primary_guild=primary_guild
    )


async def set_server_tag(
    guild_id: int | None,
    enabled: bool,
):
    """
    Prefer discord.py-self's native implementation.
    Fall back to the raw endpoint when unavailable.
    """

    if supports_primary_guild():
        info("Using native primary_guild support.")

        await native_set_tag(
            guild_id,
            enabled,
        )

        return "native"

    warning(
        "Native primary_guild support unavailable; "
        "using raw API endpoint."
    )

    await raw_set_tag(
        guild_id,
        enabled,
    )

    return "raw"


# ============================================================
# READY EVENT
# ============================================================

@client.event
async def on_ready():
    global already_ran

    # Discord can fire on_ready again after reconnecting.
    if already_ran:
        return

    already_ran = True

    print_banner()

    info(
        f"Logged in as {client.user} "
        f"({client.user.id})"
    )

    try:

        # ----------------------------------------------------
        # EQUIP
        # ----------------------------------------------------

        if args.command == "equip":

            guild_id = args.guild_id

            if guild_id <= 0:
                raise ValueError(
                    "Guild ID must be a positive integer."
                )

            info(f"Target guild ID: {guild_id}")

            guild = client.get_guild(guild_id)

            if guild:
                info(
                    f"Guild detected: {guild.name} "
                    f"({guild.id})"
                )
            else:
                warning(
                    "Guild isn't currently cached. "
                    "The ID will be used directly."
                )

            method = await set_server_tag(
                guild_id=guild_id,
                enabled=True,
            )

            print()

            success("Server tag equipped successfully.")
            info(f"Method used: {method}")

        # ----------------------------------------------------
        # REMOVE
        # ----------------------------------------------------

        elif args.command == "remove":

            info("Removing currently equipped server tag...")

            method = await set_server_tag(
                guild_id=None,
                enabled=False,
            )

            print()

            success("Server tag removed successfully.")
            info(f"Method used: {method}")

    # ========================================================
    # ERRORS
    # ========================================================

    except discord.Forbidden as exc:

        error("Discord denied the request.")

        if getattr(exc, "status", None):
            error(f"HTTP status: {exc.status}")

        if getattr(exc, "code", None):
            error(f"Discord code: {exc.code}")

        error(str(exc))

    except discord.NotFound as exc:

        error("Discord couldn't find the requested resource.")
        error(str(exc))

    except discord.HTTPException as exc:

        error("Discord API request failed.")

        error(
            f"HTTP status: "
            f"{getattr(exc, 'status', 'unknown')}"
        )

        error(
            f"Discord code: "
            f"{getattr(exc, 'code', 'unknown')}"
        )

        error(str(exc))

    except ValueError as exc:

        error(str(exc))

    except Exception as exc:

        error(
            f"{type(exc).__name__}: {exc}"
        )

    finally:

        print()
        info("Closing Discord connection...")

        await client.close()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    if TOKEN == "YOUR_USER_TOKEN":
        error(
            'Replace TOKEN = "YOUR_USER_TOKEN" '
            "with your actual token."
        )

        sys.exit(1)

    try:
        client.run(TOKEN)

    except KeyboardInterrupt:
        print()
        warning("Stopped by user.")

    except Exception as exc:
        error(
            f"Startup failed: "
            f"{type(exc).__name__}: {exc}"
        )
