class GameNotFoundError(Exception):
    """Raised when a boardgame cannot be located in persistence or fallback data."""


class GameValidationError(Exception):
    """Raised when game input parameters are invalid (e.g., out-of-range ids)."""


class GameUnavailableError(Exception):
    """Raised when game data is unavailable (e.g., missing seed data)."""
