class RecommendationInputError(Exception):
    """Raised when a recommendation request is invalid."""


class RecommendationUnavailableError(Exception):
    """Raised when the recommender cannot serve results (e.g., no data available)."""


class RecommendationNotFoundError(Exception):
    """Raised when a stored recommendation cannot be located."""


class RecommendationUnauthorizedError(Exception):
    """Raised when a recommendation is requested by a different participant."""


class BoardgameMetadataMissing(RecommendationUnavailableError):
    """Raised when scored ids cannot be hydrated with boardgame metadata."""
