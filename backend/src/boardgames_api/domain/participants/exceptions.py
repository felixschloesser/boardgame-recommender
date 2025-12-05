class ParticipantNotFoundError(Exception):
    """Raised when a participant id cannot be found."""


class ParticipantAlreadyExistsError(Exception):
    """Raised when creating a participant that already exists."""


class ParticipantValidationError(Exception):
    """Raised when participant input is invalid."""
