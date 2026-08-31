"""Shared pytest fixtures for the whole test suite."""

import shutil
from collections.abc import Iterator

import pytest

from docmind.core.config import settings


@pytest.fixture(autouse=True, scope="session")
def isolate_upload_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Redirect uploaded-file storage to a throwaway directory for the
    whole test session.

    Without this, running the suite writes real files into the same
    uploads/ directory used by local dev (docmind.core.storage reads
    settings.upload_dir at call time), leaving clutter behind on every
    test run.
    """
    original = settings.upload_dir
    test_dir = tmp_path_factory.mktemp("uploads")
    settings.upload_dir = str(test_dir)
    yield
    settings.upload_dir = original
    shutil.rmtree(test_dir, ignore_errors=True)
