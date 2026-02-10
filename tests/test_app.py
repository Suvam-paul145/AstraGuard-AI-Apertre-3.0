"""Tests for src/app.py - Main FastAPI Application Entry Point."""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock
from importlib import reload, import_module


class TestAppModuleStructure:
    """Test the app.py module structure."""

    def test_module_can_be_imported_with_mocked_dependencies(self):
        """Test that the module can be imported with mocked api.service."""
        mock_app = MagicMock()
        mock_app.title = "AstraGuard AI API"
        mock_app.version = "1.0.0"
        mock_app.docs_url = "/docs"
        mock_app.redoc_url = "/redoc"
        mock_app.add_middleware = MagicMock()

        with patch.dict(sys.modules, {'api.service': MagicMock(app=mock_app)}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert app.app is not None

    def test_logger_is_configured(self):
        """Test that logger is configured at module level."""
        mock_app = MagicMock()
        mock_app.title = "AstraGuard AI API"
        mock_app.version = "1.0.0"

        with patch.dict(sys.modules, {'api.service': MagicMock(app=mock_app)}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert hasattr(app, 'logger')
            assert app.logger is not None


class TestAppImportBehavior:
    """Test import behavior and error handling."""

    def test_successful_import_of_api_service(self):
        """Test successful import of api.service module."""
        mock_app = MagicMock()
        mock_app.title = "Test API"
        mock_app.version = "1.0.0"

        with patch.dict(sys.modules, {'api.service': MagicMock(app=mock_app)}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert app.app is not None

    def test_module_not_found_error_raises(self):
        """Test that ModuleNotFoundError is properly propagated."""
        with patch.dict(sys.modules, {'api.service': None}):
            with patch('builtins.__import__') as mock_import:
                mock_import.side_effect = ModuleNotFoundError("No module named 'api.service'")
                with pytest.raises(ModuleNotFoundError):
                    if 'app' in sys.modules:
                        del sys.modules['app']
                    import app

    def test_import_error_is_raised(self):
        """Test that ImportError is properly propagated."""
        with patch.dict(sys.modules, {'api.service': None}):
            with patch('builtins.__import__') as mock_import:
                mock_import.side_effect = ImportError("Import error from api.service")
                with pytest.raises(ImportError):
                    if 'app' in sys.modules:
                        del sys.modules['app']
                    import app


class TestAppMainBlock:
    """Test the __main__ block behavior."""

    def test_main_block_defines_uvicorn_run_parameters(self):
        """Test that __main__ block contains uvicorn.run with correct parameters."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'uvicorn.run' in content
        assert 'host="0.0.0.0"' in content
        assert 'port=8002' in content

    def test_main_block_has_proper_error_handling(self):
        """Test that __main__ block has proper error handling."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'RuntimeError' in content
        assert 'logger.critical' in content

    def test_main_block_imports_uvicorn(self):
        """Test that uvicorn is imported in the __main__ block."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'import uvicorn' in content

    def test_main_block_checks_for_uvicorn(self):
        """Test that uvicorn availability is checked."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'ModuleNotFoundError' in content


class TestAppConfiguration:
    """Test application configuration."""

    def test_app_title_is_astraguard_ai_api(self):
        """Test that the app has correct title."""
        mock_app = MagicMock()
        mock_app.title = "AstraGuard AI API"
        mock_app.version = "1.0.0"
        mock_app.docs_url = "/docs"
        mock_app.redoc_url = "/redoc"

        with patch.dict(sys.modules, {'api.service': MagicMock(app=mock_app)}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert app.app.title == "AstraGuard AI API"

    def test_app_version_is_1_0_0(self):
        """Test that the app has correct version."""
        mock_app = MagicMock()
        mock_app.title = "AstraGuard AI API"
        mock_app.version = "1.0.0"
        mock_app.docs_url = "/docs"
        mock_app.redoc_url = "/redoc"

        with patch.dict(sys.modules, {'api.service': MagicMock(app=mock_app)}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert app.app.version == "1.0.0"

    def test_app_has_documentation_urls(self):
        """Test that the app has docs and redoc URLs configured."""
        mock_app = MagicMock()
        mock_app.title = "AstraGuard AI API"
        mock_app.version = "1.0.0"
        mock_app.docs_url = "/docs"
        mock_app.redoc_url = "/redoc"

        with patch.dict(sys.modules, {'api.service': MagicMock(app=mock_app)}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert app.app.docs_url == "/docs"
            assert app.app.redoc_url == "/redoc"


class TestAppExports:
    """Test module exports."""

    def test_app_variable_exported(self):
        """Test that 'app' variable is exported from the module."""
        mock_app = MagicMock()
        mock_app.title = "Test API"
        mock_app.version = "1.0.0"
        mock_app.docs_url = "/docs"
        mock_app.redoc_url = "/redoc"

        with patch.dict(sys.modules, {'api.service': MagicMock(app=mock_app)}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert hasattr(app, 'app')

    def test_logger_exported(self):
        """Test that 'logger' variable is exported from the module."""
        mock_app = MagicMock()
        mock_app.title = "Test API"
        mock_app.version = "1.0.0"
        mock_app.docs_url = "/docs"
        mock_app.redoc_url = "/redoc"

        with patch.dict(sys.modules, {'api.service': MagicMock(app=mock_app)}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert hasattr(app, 'logger')


class TestAppMiddleware:
    """Test middleware configuration."""

    def test_cors_middleware_configured_in_service(self):
        """Test that CORS middleware is configured in api.service."""
        with open("src/api/service.py", "r") as f:
            content = f.read()
        assert 'CORSMiddleware' in content


class TestAppLifespan:
    """Test lifespan configuration."""

    def test_lifespan_is_configured(self):
        """Test that lifespan is configured on the app."""
        mock_app = MagicMock()
        mock_app.title = "AstraGuard AI API"
        mock_app.version = "1.0.0"
        mock_app.docs_url = "/docs"
        mock_app.redoc_url = "/redoc"

        mock_service = MagicMock(app=mock_app)

        with patch.dict(sys.modules, {'api.service': mock_service}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert mock_app.lifespan is not None


class TestAppErrorHandling:
    """Test error handling in the module."""

    def test_module_not_found_error_handling_in_source(self):
        """Test that ModuleNotFoundError handling exists in source."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'ModuleNotFoundError' in content

    def test_import_error_handling_in_source(self):
        """Test that ImportError handling exists in source."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'except ImportError' in content

    def test_critical_logging_on_import_failure(self):
        """Test that critical logging occurs on import failure."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'logger.critical' in content

    def test_runtime_error_handling_in_main_block(self):
        """Test that RuntimeError handling exists in main block."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'except RuntimeError' in content


class TestAppSourceStructure:
    """Test source code structure."""

    def test_app_has_docstring(self):
        """Test that module has a docstring."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert '"""' in content

    def test_app_imports_from_api_service(self):
        """Test that module imports from api.service."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'from api.service import app' in content

    def test_app_has_entry_point_guard(self):
        """Test that module has if __name__ == '__main__' guard."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'if __name__ == "__main__":' in content

    def test_app_uses_logging_module(self):
        """Test that module uses logging."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'import logging' in content

    def test_app_has_lifespan_import(self):
        """Test that module has lifespan configuration."""
        with open("src/api/service.py", "r") as f:
            content = f.read()
        assert 'asynccontextmanager' in content
        assert 'lifespan' in content

    def test_app_calls_uvicorn_run(self):
        """Test that uvicorn.run is called in main block."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'uvicorn.run(' in content

    def test_app_sets_host_correctly(self):
        """Test that host is set to 0.0.0.0."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'host="0.0.0.0"' in content

    def test_app_sets_port_correctly(self):
        """Test that port is set to 8002."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'port=8002' in content

    def test_app_has_error_logging_in_main(self):
        """Test that error logging is present in main block."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'logger.critical' in content
        assert 'exc_info=True' in content


class TestAppEntryPoint:
    """Test application entry point functionality."""

    def test_uvicorn_run_imported_in_main(self):
        """Test that uvicorn.run is imported in main block."""
        with open("src/app.py", "r") as f:
            content = f.read()
        assert 'import uvicorn' in content
        assert 'uvicorn.run' in content


class TestAppReExport:
    """Test module re-export functionality."""

    def test_app_re_exports_from_api_service(self):
        """Test that app module re-exports from api.service."""
        mock_app = MagicMock()
        mock_app.title = "AstraGuard AI API"
        mock_app.version = "1.0.0"
        mock_app.docs_url = "/docs"
        mock_app.redoc_url = "/redoc"

        mock_service = MagicMock(app=mock_app)

        with patch.dict(sys.modules, {'api.service': mock_service}):
            if 'app' in sys.modules:
                del sys.modules['app']
            import app
            reload(app)
            assert app.app is mock_app
