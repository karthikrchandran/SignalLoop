"""Tests for ``app.initial_data`` seed script."""
from unittest.mock import MagicMock, patch

import pytest

from app.initial_data import init, logger, main


@pytest.fixture(scope="module", autouse=True)
def db():  # type: ignore[override]
    """No-op override of the parent autouse ``db`` fixture — these tests are pure unit tests."""
    yield None


def test_init_opens_session_and_calls_init_db() -> None:
    """``init`` must open a Session bound to the engine and invoke ``init_db``."""
    session_mock = MagicMock()
    session_mock.__enter__.return_value = session_mock
    session_mock.__exit__.return_value = None

    with (
        patch("app.initial_data.Session", return_value=session_mock) as session_cls,
        patch("app.initial_data.init_db") as init_db_mock,
        patch("app.initial_data.engine") as engine_mock,
    ):
        init()

        session_cls.assert_called_once_with(engine_mock)
        init_db_mock.assert_called_once_with(session_mock)


def test_main_logs_and_calls_init() -> None:
    """``main`` must log start/end markers and call ``init`` exactly once."""
    with (
        patch("app.initial_data.init") as init_mock,
        patch.object(logger, "info") as info_mock,
    ):
        main()

        init_mock.assert_called_once_with()
        assert info_mock.call_count == 2
        info_mock.assert_any_call("Creating initial data")
        info_mock.assert_any_call("Initial data created")
