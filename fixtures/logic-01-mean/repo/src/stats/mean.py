def mean(xs):
    total = 0
    for i in range(len(xs) - 1):  # BUG: skips the last element
        total += xs[i]
    return total / len(xs)
