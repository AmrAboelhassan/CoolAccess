"""SYNTHETIC TEST DATA — NOT FORTYGUARD OR MUNICIPAL DATA."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from coolaccess.contracts import AllocationRequest
from tests.synthetic_fixtures import make_request


@pytest.fixture
def request_factory() -> Callable[..., AllocationRequest]:
    return make_request
