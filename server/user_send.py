"""Messages from a human user, sent through a tool with the user token.

The sender is always "User:<name>": the tool passes the name, the Bridge
sets the prefix, and peers may not take a name with it. So no agent can
pose as the user, and the instruction rule for agents can rely on it.
"""

import re

USER_PREFIX = "User:"
_USER_NAME = re.compile(r"[A-Za-z0-9_.-]+")


def is_user_name(peer_name: str) -> bool:
    return peer_name.startswith(USER_PREFIX)


def user_sender(as_name: object) -> str | None:
    """"User:<as_name>", or None if as_name is not a valid name."""
    if not isinstance(as_name, str) or not _USER_NAME.fullmatch(as_name):
        return None
    return USER_PREFIX + as_name


def valid_recipients(recipients: object) -> list[str] | None:
    """The recipient names, or None unless a non-empty list of peer names (or "*")."""
    if not isinstance(recipients, list) or not recipients:
        return None
    if not all(isinstance(name, str) and name and not is_user_name(name) for name in recipients):
        return None
    return recipients
