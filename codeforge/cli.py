"""CodeForge AI CLI entry point."""

from __future__ import annotations

import sys
from typing import Sequence

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="codeforge")
def main() -> None:
    """CodeForge AI - Local-first AI coding assistant."""


@main.command()
def hardware() -> None:
    """Display detected hardware information."""
    from codeforge.packages.hardware import HardwareManager

    manager = HardwareManager()
    info = manager.detect()

    table = Table(title="CodeForge AI - Hardware Detection")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("OS", info.os_name)
    table.add_row("OS Version", info.os_version)
    table.add_row("Architecture", info.architecture)
    table.add_row("CPU", info.cpu_model)
    table.add_row("CPU Cores (physical)", str(info.cpu_cores_physical))
    table.add_row("CPU Cores (logical)", str(info.cpu_cores_logical))
    table.add_row("CPU Threads", str(info.cpu_threads))
    table.add_row("RAM (total)", f"{info.ram_total_gb:.1f} GB")
    table.add_row("RAM (available)", f"{info.ram_available_gb:.1f} GB")
    table.add_row("GPU", info.gpu_name or "Not detected")
    table.add_row("GPU Vendor", info.gpu_vendor or "N/A")
    table.add_row("VRAM", f"{info.vram_gb:.1f} GB" if info.vram_gb else "N/A")
    table.add_row("CUDA Available", str(info.cuda_available))
    table.add_row("ROCm Available", str(info.rocm_available))
    table.add_row("MPS Available", str(info.mps_available))
    table.add_row("PyTorch Version", info.pytorch_version or "Not installed")
    table.add_row("PyTorch CUDA", info.pytorch_cuda_version or "N/A")
    table.add_row("Acceleration Backend", info.acceleration_backend)
    table.add_row("Disk (total)", f"{info.disk_total_gb:.1f} GB")
    table.add_row("Disk (free)", f"{info.disk_free_gb:.1f} GB")
    table.add_row("Python Version", info.python_version)

    console.print(table)


@main.command()
def doctor() -> None:
    """Run diagnostic checks on the CodeForge environment."""
    from codeforge.packages.hardware import HardwareManager

    console.print("[bold]CodeForge AI - Environment Diagnostics[/bold]\n")

    checks: list[tuple[str, str, str]] = []

    # Python version
    v = sys.version_info
    if v >= (3, 10):
        checks.append(("Python version", "PASS", f"{v.major}.{v.minor}.{v.micro}"))
    else:
        checks.append(("Python version", "FAIL", f"{v.major}.{v.minor}.{v.micro} (need >= 3.10)"))

    # PyTorch
    try:
        import torch
        checks.append(("PyTorch", "PASS", torch.__version__))
    except ImportError:
        checks.append(("PyTorch", "WARN", "Not installed (optional for Phase 1)"))

    # Hardware detection
    try:
        manager = HardwareManager()
        info = manager.detect()
        checks.append(("Hardware detection", "PASS", info.os_name))
    except Exception as e:
        checks.append(("Hardware detection", "FAIL", str(e)))

    # Database directory
    from pathlib import Path

    data_dir = Path("./data")
    if data_dir.exists():
        checks.append(("Data directory", "PASS", str(data_dir.resolve())))
    else:
        checks.append(("Data directory", "WARN", "Does not exist (will be created)"))

    # Display results
    table = Table(title="Diagnostics Results")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    for name, status, detail in checks:
        style = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}.get(status, "white")
        table.add_row(name, f"[{style}]{status}[/{style}]", detail)

    console.print(table)


@main.command()
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Maximum number of results")
def search(query: str, limit: int) -> None:
    """Search the codebase (Phase 11+)."""
    console.print("[yellow]Search is not yet implemented. Coming in Phase 11.[/yellow]")


@main.command()
@click.argument("prompt")
def chat(prompt: str) -> None:
    """Chat with CodeForge AI (Phase 9+)."""
    console.print("[yellow]Chat is not yet implemented. Coming in Phase 9.[/yellow]")


if __name__ == "__main__":
    main()
