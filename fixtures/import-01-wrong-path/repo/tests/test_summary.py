from stats.summary import summarise


def test_summarise_adds_values():
    assert summarise([10, 20, 30]) == 60


def test_summarise_clamps_to_high():
    assert summarise([60, 60]) == 100
