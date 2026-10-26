from geometry.area import area_of_square


def test_area_of_square():
    assert area_of_square(3) == 9


def test_area_of_unit_square():
    assert area_of_square(1) == 1
