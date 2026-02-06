"""
AstraGuard AI - FastAPI Application Entry Point
For Vercel & production deployments
"""
import logging
logger=logging.getLogger(__name__)
try:
    from api.service import app
except ModuleNotFoundError as e:
    logger.critical(
        "Failed to import 'api.service.app' (Module not found)."
        "Verify project structure and deployment configuration.",
        exc_info=True,
    )
    raise
except ImportError as e:
    logger.critical(
        "ImportError occurred while importing FastAPI app."
        "This may be caused by missing dependencies or import-time side effects.",
        exc_info=True,
    )
    raise

__all__=["app"]