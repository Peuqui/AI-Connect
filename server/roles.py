"""Roles of the Bridge: which token may send which message types.

A connection gets its role from the token it shows in the handshake. The
peer token is the shared bridge.token; the observer token is only known to
the Bridge by its SHA-256 (bridge.observer_token_sha256), so the config that
every agent can read does not give it away.
"""

import hashlib
import hmac

PEER = "peer"
OBSERVER = "observer"

# The single truth on what each role may do; anything else is refused
ALLOWED_MESSAGE_TYPES: dict[str, frozenset[str]] = {
    PEER: frozenset({
        "register", "ping", "watch", "list_peers", "message",
        "set_state", "set_status", "notify_when_idle", "history",
    }),
    # Reads only: no register, so an observer can neither send nor hold a name
    OBSERVER: frozenset({"observe", "history_all", "list_peers", "ping"}),
}


def token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Roles:
    """Maps the token of a handshake to its role."""

    def __init__(self, peer_token: str, observer_token_sha256: str):
        self._role_by_hash = {
            token_sha256(peer_token): PEER,
            observer_token_sha256: OBSERVER,
        }

    def role_for(self, authorization: str) -> str | None:
        """The role of an "Authorization: Bearer <token>" header, None if unknown."""
        scheme, _, token = authorization.partition(" ")
        if scheme != "Bearer" or not token:
            return None
        sent = token_sha256(token)
        role = None
        # Compare against every entry, so the time taken does not tell which matched
        for known, known_role in self._role_by_hash.items():
            if hmac.compare_digest(sent, known):
                role = known_role
        return role

    @staticmethod
    def allows(role: str, message_type: str | None) -> bool:
        return message_type in ALLOWED_MESSAGE_TYPES[role]
