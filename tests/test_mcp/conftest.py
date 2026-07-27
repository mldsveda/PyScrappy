import pytest


@pytest.fixture
def anyio_backend():
    # Run @pytest.mark.anyio tests on asyncio only (avoids needing trio).
    return "asyncio"
