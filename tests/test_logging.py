import structlog

from docmind.core.config import settings
from docmind.core.logging import configure_logging


def test_configure_logging_uses_json_renderer_in_production() -> None:
    # structlog.configure() is global process state, so this test must
    # restore both settings.environment and the logging config afterward
    # to avoid leaking JSON-formatted logs into every other test.
    original_environment = settings.environment
    try:
        settings.environment = "production"
        configure_logging()

        config = structlog.get_config()
        renderer = config["processors"][-1]

        assert isinstance(renderer, structlog.processors.JSONRenderer)
    finally:
        settings.environment = original_environment
        configure_logging()
