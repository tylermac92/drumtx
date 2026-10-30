import pytest
from build_corpus import grid_beats, reference_score

BPM = 120  # one beat = 0.5 s


def at(*beats: float) -> list[tuple[float, str, int]]:
    return [(b * 60 / BPM, "snare", 100) for b in beats]


def test_grid_beats_start_on_a_downbeat() -> None:
    assert grid_beats(BPM, 4, 2.0) == [(0.0, 1), (0.5, 2), (1.0, 3), (1.5, 4), (2.0, 1)]


@pytest.mark.parametrize(
    ("beat", "expected"),
    [
        (0.0, (1, 1, "16th", 1)),
        (0.5, (1, 1, "16th", 3)),
        (0.97, (1, 2, "16th", 1)),  # slightly early hit belongs to the next beat
        (1 + 1 / 3, (1, 2, "triplet", 2)),
        (5.75, (2, 2, "16th", 4)),  # bar wraps after four beats
    ],
)
def test_reference_score_places_hits(beat: float, expected: tuple[int, int, str, int]) -> None:
    [(_, *position)] = reference_score(at(beat), BPM, 4)
    assert tuple(position) == expected


def test_reference_score_leaves_ambiguous_hits_unscored() -> None:
    # A 32nd note between straight 8ths fits neither grid closely enough.
    rows = reference_score(at(1.0, 1.125, 1.5), BPM, 4)
    assert [r[1:] for r in rows] == [
        (1, 2, "16th", 1),
        (None, None, None, None),
        (1, 2, "16th", 3),
    ]
