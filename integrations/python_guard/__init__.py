"""Source-authoritative Python patch verification; no agent or ALVA runtime."""

from .guard import Guard, GuardError, policy_identity

__all__ = ["Guard", "GuardError", "policy_identity"]
