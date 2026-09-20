"""Python environment detection for CodeForge AI."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from .models import EnvironmentInfo, EnvironmentType, PythonInfo


def detect_python() -> PythonInfo:
    """Detect Python interpreter information.

    Returns:
        PythonInfo with version, executable, and platform details.
    """
    v = sys.version_info
    version = f"{v.major}.{v.minor}.{v.micro}"

    return PythonInfo(
        version=version,
        version_major=v.major,
        version_minor=v.minor,
        version_micro=v.micro,
        executable=sys.executable,
        implementation=platform.python_implementation(),
        compiler=platform.python_compiler(),
        architecture=platform.architecture()[0],
    )


def detect_environment() -> EnvironmentInfo:
    """Detect the current Python environment type.

    Checks for:
    1. Conda (CONDA_DEFAULT_ENV, CONDA_PREFIX)
    2. Virtual environment (VIRTUAL_ENV)
    3. venv detection via sys.prefix != sys.base_prefix
    4. System Python

    Returns:
        EnvironmentInfo with detected environment details.
    """
    # Check Conda first
    conda_info = _detect_conda()
    if conda_info is not None:
        return conda_info

    # Check virtualenv / VIRTUAL_ENV
    venv_info = _detect_virtualenv()
    if venv_info is not None:
        return venv_info

    # Check if running inside a venv (sys.prefix != sys.base_prefix)
    if sys.prefix != sys.base_prefix:
        return EnvironmentInfo(
            env_type=EnvironmentType.VENV,
            env_name=Path(sys.prefix).name,
            env_path=sys.prefix,
            site_packages=_find_site_packages(sys.prefix),
        )

    # System Python
    return EnvironmentInfo(
        env_type=EnvironmentType.SYSTEM,
        env_name="system",
        env_path=sys.prefix,
        site_packages=_find_site_packages(sys.prefix),
    )


def _detect_conda() -> EnvironmentInfo | None:
    """Detect Conda environment."""
    conda_env = os.environ.get("CONDA_DEFAULT_ENV")
    conda_prefix = os.environ.get("CONDA_PREFIX")

    if conda_env or conda_prefix:
        env_name = conda_env or Path(conda_prefix or "").name
        prefix = conda_prefix or ""

        return EnvironmentInfo(
            env_type=EnvironmentType.CONDA,
            env_name=env_name,
            env_path=prefix,
            conda_env_name=env_name,
            conda_prefix=prefix,
            site_packages=_find_site_packages(prefix),
        )

    # Check if conda is the active Python by looking at sys.prefix path
    prefix = sys.prefix
    if "conda" in prefix.lower() or "anaconda" in prefix.lower() or "miniconda" in prefix.lower():
        return EnvironmentInfo(
            env_type=EnvironmentType.CONDA,
            env_name=Path(prefix).name,
            env_path=prefix,
            conda_env_name=Path(prefix).name,
            conda_prefix=prefix,
            site_packages=_find_site_packages(prefix),
        )

    return None


def _detect_virtualenv() -> EnvironmentInfo | None:
    """Detect virtualenv (not stdlib venv)."""
    venv_path = os.environ.get("VIRTUAL_ENV")
    if venv_path:
        return EnvironmentInfo(
            env_type=EnvironmentType.VIRTUALENV,
            env_name=Path(venv_path).name,
            env_path=venv_path,
            virtual_env=venv_path,
            site_packages=_find_site_packages(venv_path),
        )
    return None


def _find_site_packages(prefix: str) -> str:
    """Find site-packages directory within a prefix."""
    if not prefix:
        return ""

    prefix_path = Path(prefix)

    # Standard locations
    for candidate in [
        prefix_path / "lib",
        prefix_path / "Lib" if platform.system() == "Windows" else prefix_path / "lib",
    ]:
        if candidate.exists():
            for item in candidate.iterdir():
                if item.is_dir() and item.name.startswith("python"):
                    site_pkgs = item / "site-packages"
                    if site_pkgs.exists():
                        return str(site_pkgs)

    return ""


def get_available_ml_packages() -> dict[str, str | None]:
    """Detect available machine learning packages and their versions.

    Returns:
        Dictionary mapping package names to their versions (None if not installed).
    """
    packages = [
        "torch",
        "torchvision",
        "torchaudio",
        "transformers",
        "accelerate",
        "bitsandbytes",
        "flash_attn",
        "xformers",
        "triton",
        "safetensors",
        "sentencepiece",
        "tokenizers",
        "numpy",
        "scipy",
        "scikit-learn",
    ]

    result: dict[str, str | None] = {}
    for pkg_name in packages:
        try:
            mod = __import__(pkg_name)
            version = getattr(mod, "__version__", "unknown")
            result[pkg_name] = str(version)
        except ImportError:
            result[pkg_name] = None

    return result


def get_missing_dependencies() -> list[str]:
    """Check for required and recommended dependencies.

    Returns:
        List of missing package names.
    """
    required = ["click", "rich", "psutil", "fastapi", "uvicorn", "pydantic"]
    missing: list[str] = []

    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    return missing
