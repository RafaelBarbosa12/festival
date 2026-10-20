"""Family of festival errors: catch them all, or one of them."""


class FestivalError(Exception):
    """Every error of the festival."""


class NotFoundError(FestivalError):
    """Unknown venue, artist or performance."""


class ConflictError(FestivalError):
    """A rule of the schedule or of a workshop was broken."""


class InvalidError(FestivalError):
    """A value that cannot be a show, an artist, or a day."""
