from typing import Dict, Set


class ConsentError(Exception):
    """Raised when required consent is missing."""


class ConsentManager:
    """Simple consent management for health data processing."""

    def __init__(self):
        self._consent_registry: Dict[str, Set[str]] = {}

    def grant_consent(self, user_id: str, purpose: str) -> None:
        if user_id not in self._consent_registry:
            self._consent_registry[user_id] = set()
        self._consent_registry[user_id].add(purpose)

    def revoke_consent(self, user_id: str, purpose: str) -> None:
        if user_id in self._consent_registry:
            self._consent_registry[user_id].discard(purpose)

    def has_consent(self, user_id: str, purpose: str) -> bool:
        return purpose in self._consent_registry.get(user_id, set())

    def require_consent(self, user_id: str, purpose: str) -> None:
        if not self.has_consent(user_id, purpose):
            raise ConsentError(
                f"Consent not granted for user {user_id} for purpose '{purpose}'"
            )
