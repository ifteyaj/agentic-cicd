import pytest


def test_happy_path_reaches_completed() -> None:
    from app.domain.status import RunStatus, transition

    status = RunStatus.QUEUED
    for nxt in [
        RunStatus.TRIAGING,
        RunStatus.REPAIRING,
        RunStatus.VALIDATING,
        RunStatus.AWAITING_APPROVAL,
        RunStatus.PUBLISHING,
        RunStatus.COMPLETED,
    ]:
        status = transition(status, nxt)
    assert status is RunStatus.COMPLETED


def test_validation_can_loop_back_to_repair() -> None:
    from app.domain.status import RunStatus, transition

    assert transition(RunStatus.VALIDATING, RunStatus.REPAIRING) is RunStatus.REPAIRING


def test_skipping_validation_is_illegal() -> None:
    from app.domain.status import IllegalTransition, RunStatus, transition

    with pytest.raises(IllegalTransition):
        transition(RunStatus.REPAIRING, RunStatus.AWAITING_APPROVAL)


def test_terminal_states_cannot_move() -> None:
    from app.domain.status import IllegalTransition, RunStatus, transition

    with pytest.raises(IllegalTransition):
        transition(RunStatus.COMPLETED, RunStatus.QUEUED)
