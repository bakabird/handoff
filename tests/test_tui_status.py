from cli.tui import INITIAL_STATUS_CHECK_DELAY, STATUS_COLUMN_WIDTH


def test_running_status_fits_and_initial_check_waits_three_seconds():
    assert INITIAL_STATUS_CHECK_DELAY == 3.0
    assert STATUS_COLUMN_WIDTH >= len("running")
