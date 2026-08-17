class LaneDrillError(Exception):
    """Base class for all lane-drill errors."""


class MissingColumnError(LaneDrillError):
    """A required column could not be found or mapped."""


class InvalidDataError(LaneDrillError):
    """A row or value failed validation."""


class InsufficientDataError(LaneDrillError):
    """Not enough usable observations to run a drill."""


class UnknownEpisodeError(LaneDrillError):
    """The requested episode is not in the atlas."""
