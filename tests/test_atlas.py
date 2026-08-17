from pathlib import Path

import pandas as pd
import pytest

from lane_drill.episodes import atlas, null_episode, resolve_episode
from lane_drill.errors import UnknownEpisodeError

EXAMPLES = Path(__file__).parent.parent / "src" / "lane_drill" / "examples"


def test_detector_rediscovers_the_ever_given():
    ep = resolve_episode("ever-given", EXAMPLES)
    assert ep.chokepoint == "suez"
    assert pd.Timestamp("2021-03-20") <= ep.start <= pd.Timestamp("2021-03-31")
    assert ep.depth < 0.15
    assert 4 <= ep.duration_days <= 21
    assert ep.surge > 1.1


def test_detector_rediscovers_the_red_sea_crisis():
    ep = resolve_episode("red-sea", EXAMPLES)
    assert ep.chokepoint == "bab_el_mandeb"
    assert ep.start >= pd.Timestamp("2023-11-15")
    assert ep.depth < 0.7
    assert ep.duration_days > 30


def test_detector_rediscovers_the_panama_drought():
    ep = resolve_episode("panama-drought", EXAMPLES)
    assert ep.chokepoint == "panama"
    assert ep.depth < 0.75
    assert ep.duration_days > 60


def test_atlas_is_not_just_the_famous_three():
    catalog = atlas(EXAMPLES)
    assert len(catalog) >= 3
    assert all(ep.duration_days >= 5 for ep in catalog)


def test_unknown_episode_lists_the_catalog():
    with pytest.raises(UnknownEpisodeError, match="ever-given"):
        resolve_episode("krakatoa", EXAMPLES)


def test_chokepoint_month_form_resolves():
    ep = resolve_episode("suez:2021-03", EXAMPLES)
    assert ep.start.year == 2021 and ep.start.month == 3


def test_null_profile_is_all_ones():
    ep = null_episode(days=30)
    assert (ep.profile == 1.0).all()
    assert ep.depth == 1.0
