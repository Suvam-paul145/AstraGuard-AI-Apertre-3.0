"""
AstraGuard AI - FastAPI Application Entry Point.

This module serves as the primary entry point for Vercel and production deployments.
It securely imports the main `app` instance from `api.service`, handling potential
import errors gracefully with detailed logging for debugging deployment issues.
"""
import logging
import sys
from typing import List, Tuple

logger: logging.Logger = logging.getLogger(__name__)

# Track import errors for better debugging
_import_errors: List[Tuple[str, str]] = []


def _log_import_error(error: Exception, error_type: str) -> None:
    """Log import error with comprehensive context."""
    logger.critical(
        f"Failed to import 'api.service.app': {error_type}",
        error_type=error_type,
        error_message=str(error),
        python_version=sys.version,
        sys_path=sys.path,
        exc_info=True,
    )


try:
    from api.service import app
except ModuleNotFoundError as e:
    _log_import_error(e, "ModuleNotFoundError")
    _import_errors.append(("ModuleNotFoundError", str(e)))
    raise
except ImportError as e:
    # Distinguish between different types of ImportError
    if "httpx" in str(e) or "fastapi" in str(e).lower():
        _log_import_error(e, "MissingHTTPDependency")
    elif "pydantic" in str(e).lower():
        _log_import_error(e, "MissingPydanticDependency")
    else:
        _log_import_error(e, "ImportError")
    _import_errors.append(("ImportError", str(e)))
    raise
except AttributeError as e:
    # Handle case where module exists but doesn't have 'app' attribute
    logger.critical(
        "Module 'api.service' found but 'app' attribute is missing. "
        "Verify that api.service module exports 'app' correctly.",
        error_type="AttributeError",
        error_message=str(e),
        exc_info=True,
    )
    _import_errors.append(("AttributeError", str(e)))
    raise
except Exception as e:
    # Catch-all for unexpected errors during import
    logger.critical(
        "Unexpected error during import of 'api.service.app'. "
        "This may indicate a configuration or environment issue.",
        error_type=type(e).__name__,
        error_message=str(e),
        exc_info=True,
    )
    _import_errors.append((type(e).__name__, str(e)))
    raise


def get_import_errors() -> List[Tuple[str, str]]:
    """Return list of import errors that occurred during module load."""
    return _import_errors.copy()


__all__ = ["app", "get_import_errors"]
