class GameNotFoundError(Exception):
    """Raised when a boardgame cannot be located in persistence or fallback data."""
