"""M5-5: the correction guide's example recording has the hits the guide describes."""

from make_guide_sample import hits


def test_guide_sample() -> None:
    h = hits()
    assert len(h) == 96  # 4 in the fill, 15 in each of six bars, the final kick and crash
    assert h[:4] == [
        (2.25, "snare", 90),
        (2.562, "snare", 95),
        (2.875, "tom", 100),
        (3.188, "tom", 105),
    ]
    assert (3.5, "kick", 110) in h  # bar 1, after the fill
    assert sum(v == 25 for _, _, v in h) == 12  # ghost notes
