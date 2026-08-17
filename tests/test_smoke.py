from lane_drill import __version__
from lane_drill.errors import LaneDrillError, UnknownEpisodeError


def test_version_is_exposed():
    assert __version__ == "0.1.0"


def test_unknown_episode_error_is_a_lane_drill_error():
    assert issubclass(UnknownEpisodeError, LaneDrillError)
