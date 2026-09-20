"""Tests for runtime environment detection."""

from __future__ import annotations

import sys

from codeforge.packages.runtime.environment import (
    detect_environment,
    detect_python,
    get_available_ml_packages,
    get_missing_dependencies,
)
from codeforge.packages.runtime.models import EnvironmentType, PythonInfo


class TestPythonDetection:
    def test_detect_python_returns_valid(self) -> None:
        info = detect_python()
        assert isinstance(info, PythonInfo)
        assert info.version != "Unknown"
        assert info.version_major == sys.version_info.major
        assert info.version_minor == sys.version_info.minor

    def test_detect_python_has_executable(self) -> None:
        info = detect_python()
        assert info.executable != "Unknown"
        assert len(info.executable) > 0

    def test_detect_python_implementation(self) -> None:
        info = detect_python()
        assert info.implementation in ("CPython", "PyPy", "Jython", "IronPython")


class TestEnvironmentDetection:
    def test_detect_environment_returns_valid(self) -> None:
        info = detect_environment()
        assert isinstance(info.env_type, EnvironmentType)

    def test_detect_environment_has_type(self) -> None:
        info = detect_environment()
        assert info.env_type in (
            EnvironmentType.CONDA,
            EnvironmentType.VENV,
            EnvironmentType.VIRTUALENV,
            EnvironmentType.SYSTEM,
            EnvironmentType.UNKNOWN,
        )

    def test_conda_detection(self) -> None:
        import os

        # Save original
        orig = os.environ.get("CONDA_DEFAULT_ENV")
        try:
            os.environ["CONDA_DEFAULT_ENV"] = "test-env"
            os.environ["CONDA_PREFIX"] = "/tmp/test"
            info = detect_environment()
            assert info.env_type == EnvironmentType.CONDA
            assert info.conda_env_name == "test-env"
        finally:
            # Restore
            if orig is not None:
                os.environ["CONDA_DEFAULT_ENV"] = orig
            else:
                os.environ.pop("CONDA_DEFAULT_ENV", None)
            os.environ.pop("CONDA_PREFIX", None)

    def test_virtualenv_detection(self) -> None:
        import os
        import sys

        # Skip if running inside conda (sys.prefix contains conda)
        if "conda" in sys.prefix.lower() or "miniconda" in sys.prefix.lower():
            return

        orig_venv = os.environ.get("VIRTUAL_ENV")
        orig_conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        orig_conda_prefix = os.environ.get("CONDA_PREFIX")
        try:
            # Remove conda env vars so virtualenv detection takes priority
            os.environ.pop("CONDA_DEFAULT_ENV", None)
            os.environ.pop("CONDA_PREFIX", None)
            os.environ["VIRTUAL_ENV"] = "/tmp/test-venv"
            info = detect_environment()
            assert info.env_type == EnvironmentType.VIRTUALENV
            assert info.virtual_env == "/tmp/test-venv"
        finally:
            if orig_venv is not None:
                os.environ["VIRTUAL_ENV"] = orig_venv
            else:
                os.environ.pop("VIRTUAL_ENV", None)
            if orig_conda_env is not None:
                os.environ["CONDA_DEFAULT_ENV"] = orig_conda_env
            if orig_conda_prefix is not None:
                os.environ["CONDA_PREFIX"] = orig_conda_prefix


class TestMLPackages:
    def test_get_available_ml_packages(self) -> None:
        packages = get_available_ml_packages()
        assert isinstance(packages, dict)
        assert "torch" in packages
        assert "numpy" in packages

    def test_get_available_values_are_str_or_none(self) -> None:
        packages = get_available_ml_packages()
        for name, version in packages.items():
            assert version is None or isinstance(version, str), f"{name}: {version}"


class TestMissingDependencies:
    def test_get_missing_dependencies(self) -> None:
        missing = get_missing_dependencies()
        assert isinstance(missing, list)
        # On a working install, should have few or no missing
        for pkg in missing:
            assert isinstance(pkg, str)
