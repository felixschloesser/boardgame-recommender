class RecommenderUnavailableException(Exception):
    """
    Exception raised when the recommender system is unavailable.
    """

    def __init__(
        self, message: str = "The recommender system is currently unavailable."
    ):
        super().__init__(message)
