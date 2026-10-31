"""Attempt records for repair runs."""

from dataclasses import dataclass

FIXED_FAKE_PATCH = (
    "--- a/src/example.py\n"
    "+++ b/src/example.py\n"
    "@@ -1,3 +1,4 @@\n"
    " def calculate() -> int:\n"
    "-    return 1\n"
    "+    return 2\n"
)


@dataclass(frozen=True, slots=True)
class Attempt:
    attempt_id: str
    run_id: str
    n: int
    patch_sha256: str
    patch_diff: str = FIXED_FAKE_PATCH
