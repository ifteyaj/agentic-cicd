from stats.utils import clamp  # BUG: module is stats.mathutils
# Totals are clamped to a 0-100 range.


def summarise(values):
    return clamp(sum(values), 0, 100)
