from stats.mean import mean


def test_mean_simple():
    assert mean([1, 2, 3]) == 2


def test_mean_last():
    assert mean([2, 4]) == 3
