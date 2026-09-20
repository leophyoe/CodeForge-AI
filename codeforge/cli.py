"""CodeForge AI CLI entry point."""

from __future__ import annotations

import sys

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
def runtime() -> None:
    """Display runtime environment information."""
    from codeforge.packages.runtime import RuntimeManager

    manager = RuntimeManager()
    info = manager.detect()

    table = Table(title="CodeForge Runtime")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Python", info.python.version)
    table.add_row("Python Executable", info.python.executable)
    table.add_row("Environment", info.environment.env_type.value)
    if info.environment.env_name:
        table.add_row("Environment Name", info.environment.env_name)
    table.add_row("PyTorch", info.pytorch.version if info.pytorch.installed else "Not installed")
    table.add_row("Backend", info.backend_name)
    table.add_row("Device", f"{info.selected_device.device_type.value}")
    table.add_row("Device Name", info.selected_device.name)
    table.add_row("CUDA Available", str(info.pytorch.cuda_available))
    table.add_row("CUDA Version", info.pytorch.cuda_version or "N/A")
    table.add_row("ROCm Available", str(info.pytorch.rocm_available))
    table.add_row("MPS Available", str(info.pytorch.mps_available))
    table.add_row("Status", info.backend_status.value)

    if info.error_message:
        table.add_row("Note", info.error_message)

    console.print(table)

    console.print("\n[bold]Running tensor smoke test...[/bold]")
    result = manager.run_smoke_test()
    if result["success"]:
        console.print(f"[green]PASS[/green] - Tensor operation on {result['device']}")
    else:
        console.print(f"[red]FAIL[/red] - {result.get('error', 'Unknown error')}")

    manager.shutdown()


@main.command()
def device() -> None:
    """Display available compute devices."""
    from codeforge.packages.runtime import DeviceManager

    manager = DeviceManager()
    devices = manager.detect_available_devices()
    default = manager.get_default_device()

    table = Table(title="Available Devices")
    table.add_column("Device", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Memory", style="yellow")
    table.add_column("Status", style="bold")
    table.add_column("Default", style="magenta")

    for dev in devices:
        mem_str = f"{dev.total_memory_gb:.1f} GB" if dev.total_memory_gb else "N/A"
        is_default = (
            dev.device_type == default.device_type
            and dev.device_index == default.device_index
        )
        if dev.device_index > 0:
            device_str = f"{dev.device_type.value}:{dev.device_index}"
        else:
            device_str = dev.device_type.value

        table.add_row(
            device_str,
            dev.name,
            mem_str,
            "Available" if dev.is_available else "Unavailable",
            "*" if is_default else "",
        )

    console.print(table)


@main.command()
def doctor() -> None:
    """Run diagnostic checks on the CodeForge environment."""
    from codeforge.packages.hardware import HardwareManager

    console.print("[bold]CodeForge AI - Environment Diagnostics[/bold]\n")

    checks: list[tuple[str, str, str]] = []

    v = sys.version_info
    if v >= (3, 10):
        checks.append(("Python version", "PASS", f"{v.major}.{v.minor}.{v.micro}"))
    else:
        checks.append(("Python version", "FAIL", f"{v.major}.{v.minor}.{v.micro} (need >= 3.10)"))

    try:
        import torch
        checks.append(("PyTorch", "PASS", torch.__version__))
    except ImportError:
        checks.append(("PyTorch", "WARN", "Not installed"))

    try:
        from codeforge.packages.runtime import DeviceManager
        dm = DeviceManager()
        dm.detect_available_devices()
        default = dm.get_default_device()
        checks.append(("Device", "PASS", f"{default.device_type.value} - {default.name}"))
    except Exception as e:
        checks.append(("Device", "FAIL", str(e)))

    try:
        from codeforge.packages.runtime import run_tensor_smoke_test
        result = run_tensor_smoke_test()
        if result["success"]:
            checks.append(("Tensor operation", "PASS", f"on {result['device']}"))
        else:
            checks.append(("Tensor operation", "FAIL", result.get("error", "Unknown")))
    except Exception as e:
        checks.append(("Tensor operation", "FAIL", str(e)))

    try:
        manager = HardwareManager()
        info = manager.detect()
        checks.append(("Hardware detection", "PASS", info.os_name))
    except Exception as e:
        checks.append(("Hardware detection", "FAIL", str(e)))

    from pathlib import Path
    data_dir = Path("./data")
    if data_dir.exists():
        checks.append(("Data directory", "PASS", str(data_dir.resolve())))
    else:
        checks.append(("Data directory", "WARN", "Does not exist (will be created)"))

    try:
        from codeforge.packages.models import ModelManager
        mm = ModelManager()
        models = mm.list_models()
        checks.append(("Model registry", "PASS", f"{len(models)} models registered"))
    except Exception as e:
        checks.append(("Model registry", "FAIL", str(e)))

    table = Table(title="Diagnostics Results")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    for name, status, detail in checks:
        style = {"PASS": "green", "WARN": "yellow", "FAIL": "red"}.get(status, "white")
        table.add_row(name, f"[{style}]{status}[/{style}]", detail)

    console.print(table)


@main.group()
def model() -> None:
    """Model management commands."""


@main.command("models")
def models() -> None:
    """List all registered models (alias for 'model list')."""
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    model_list = mm.list_models()

    if not model_list:
        console.print("[yellow]No models registered.[/yellow]")
        console.print("Use 'codeforge model discover' to scan for models.")
        return

    table = Table(title="Registered Models")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Task", style="yellow")
    table.add_column("Format", style="blue")
    table.add_column("Status", style="bold")
    table.add_column("Path", style="dim")

    for m in model_list:
        table.add_row(
            m.get("model_id", ""),
            m.get("name", ""),
            m.get("task", "unknown"),
            m.get("format", "unknown"),
            m.get("status", "unknown"),
            m.get("path", ""),
        )

    console.print(table)


@model.command("list")
def model_list_cmd() -> None:
    """List all registered models."""
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    model_list = mm.list_models()

    if not model_list:
        console.print("[yellow]No models registered.[/yellow]")
        return

    table = Table(title="Registered Models")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Task", style="yellow")
    table.add_column("Format", style="blue")
    table.add_column("Status", style="bold")
    table.add_column("Path", style="dim")

    for m in model_list:
        table.add_row(
            m.get("model_id", ""),
            m.get("name", ""),
            m.get("task", "unknown"),
            m.get("format", "unknown"),
            m.get("status", "unknown"),
            m.get("path", ""),
        )

    console.print(table)


@model.command("inspect")
@click.argument("model_id")
def model_inspect(model_id: str) -> None:
    """Inspect a registered model."""
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    try:
        info = mm.inspect_model(model_id)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return

    table = Table(title=f"Model: {info.model_id}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Name", info.name)
    table.add_row("Provider", info.provider)
    table.add_row("Task", info.task)
    table.add_row("Architecture", info.architecture or "Unknown")
    table.add_row("Parameters", info.parameter_count_str)
    table.add_row("Dtype", info.dtype)
    table.add_row("Context Length", str(info.context_length) if info.context_length else "Unknown")
    table.add_row("Vocab Size", str(info.vocab_size) if info.vocab_size else "Unknown")
    table.add_row("Quantization", info.quantization)
    table.add_row("Tokenizer", info.tokenizer)
    table.add_row("Path", info.path)
    table.add_row("Format", info.format)
    table.add_row("Estimated RAM", f"{info.estimated_ram_gb:.2f} GB")
    table.add_row("Estimated VRAM", f"{info.estimated_vram_gb:.2f} GB")
    table.add_row("Compatibility", info.compatibility)
    table.add_row("Status", info.status)
    if info.weight_files:
        table.add_row("Weight Files", ", ".join(info.weight_files))

    console.print(table)


@model.command("load")
@click.argument("model_id")
@click.option("--device", "-d", default="auto", help="Device to load on (auto/cpu/cuda/mps)")
@click.option("--dtype", "-t", default="auto", help="Data type (auto/float32/float16/bfloat16)")
@click.option("--force", "-f", is_flag=True, help="Force reload even if loaded")
def model_load(model_id: str, device: str, dtype: str, force: bool) -> None:
    """Load a model into memory."""
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    console.print(f"[bold]Loading model '{model_id}'...[/bold]")

    try:
        result = mm.load_model(model_id, device=device, dtype=dtype, force=force)
        console.print("[green]Model loaded successfully![/green]")
        console.print(f"  Device: {result.get('device', 'unknown')}")
        console.print(f"  Dtype: {result.get('dtype', 'unknown')}")
        if "parameter_count_str" in result:
            console.print(f"  Parameters: {result['parameter_count_str']}")
    except Exception as e:
        console.print(f"[red]Failed to load model:[/red] {e}")


@model.command("unload")
@click.argument("model_id")
def model_unload(model_id: str) -> None:
    """Unload a model from memory."""
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    console.print(f"[bold]Unloading model '{model_id}'...[/bold]")

    try:
        mm.unload_model(model_id)
        console.print("[green]Model unloaded successfully![/green]")
    except Exception as e:
        console.print(f"[red]Failed to unload model:[/red] {e}")


@model.command("status")
def model_status() -> None:
    """Show status of all loaded models."""
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    loaded = mm.get_loaded_models()

    if not loaded:
        console.print("[yellow]No models currently loaded.[/yellow]")
        return

    table = Table(title="Loaded Models")
    table.add_column("Model ID", style="cyan")
    table.add_column("Status", style="green")

    for model_id in loaded:
        status = mm.get_model_status(model_id)
        table.add_row(model_id, status.value)

    console.print(table)


@model.command("discover")
def model_discover() -> None:
    """Scan the model directory for models."""
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    console.print(f"[bold]Scanning {mm.model_dir}...[/bold]")

    models = mm.discover_models()

    if not models:
        console.print("[yellow]No models found.[/yellow]")
        console.print(f"Place model directories in '{mm.model_dir}/'")
        return

    console.print(f"[green]Found {len(models)} model(s):[/green]")
    for m in models:
        console.print(f"  - {m.model_id} ({m.format.value})")


@main.command()
@click.argument("prompt")
@click.option("--model", "-m", required=True, help="Model ID to generate with")
@click.option("--max-tokens", "-n", default=256, help="Maximum tokens to generate")
@click.option("--temperature", "-t", default=0.7, help="Sampling temperature")
@click.option("--top-p", default=0.9, help="Top-p sampling")
@click.option("--stream/--no-stream", default=False, help="Stream tokens")
def generate(
    prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    stream: bool,
) -> None:
    """Generate text from a prompt."""
    from codeforge.packages.generation import (
        GenerationConfig,
        GenerationRequest,
        GenerationService,
    )
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    svc = GenerationService(model_manager=mm)

    config = GenerationConfig(
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
    )

    if stream:
        console.print(f"[bold]Streaming from {model}...[/bold]\n")
        request = GenerationRequest(prompt=prompt, model_id=model, config=config)
        events = svc.stream_generate(prompt, model, config)
        for event in events:
            if event.event_type.value == "token" and event.text:
                console.print(event.text, end="", highlight=False)
            elif event.event_type.value == "error":
                console.print(f"\n[red]Error:[/red] {event.error}")
                break
        console.print()
    else:
        console.print(f"[bold]Generating from {model}...[/bold]")
        request = GenerationRequest(prompt=prompt, model_id=model, config=config)
        try:
            response = svc.generate(request)
            console.print(f"\n[green]{response.text}[/green]")
            console.print(
                f"\n[dim]Tokens: {response.usage.prompt_tokens} prompt + "
                f"{response.usage.completion_tokens} completion = "
                f"{response.usage.total_tokens} total[/dim]"
            )
        except Exception as e:
            console.print(f"[red]Generation failed:[/red] {e}")


@main.command()
@click.option("--model", "-m", required=True, help="Model ID to chat with")
@click.option("--max-tokens", "-n", default=256, help="Maximum tokens to generate")
@click.option("--temperature", "-t", default=0.7, help="Sampling temperature")
@click.option("--stream/--no-stream", default=False, help="Stream tokens")
def chat(model: str, max_tokens: int, temperature: float, stream: bool) -> None:
    """Interactive chat with a model."""
    from codeforge.packages.generation import (
        ChatMessage,
        ChatRequest,
        GenerationConfig,
        GenerationService,
    )
    from codeforge.packages.models import ModelManager

    mm = ModelManager()
    svc = GenerationService(model_manager=mm)
    config = GenerationConfig(max_tokens=max_tokens, temperature=temperature)

    messages: list[ChatMessage] = []
    console.print(f"[bold]Chat with {model} (type 'quit' to exit)[/bold]\n")

    while True:
        try:
            user_input = console.input("[cyan]You:[/cyan] ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if user_input.strip().lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue

        messages.append(ChatMessage(role="user", content=user_input))

        if stream:
            console.print(f"[green]{model}:[/green] ", end="")
            events = svc.stream_chat(messages, model, config)
            for event in events:
                if event.event_type.value == "token" and event.text:
                    console.print(event.text, end="", highlight=False)
                elif event.event_type.value == "error":
                    console.print(f"\n[red]Error:[/red] {event.error}")
                    break
            console.print()
        else:
            request = ChatRequest(messages=messages, model_id=model, config=config)
            try:
                response = svc.chat(request)
                console.print(f"[green]{model}:[/green] {response.text}")
                messages.append(ChatMessage(role="assistant", content=response.text))
            except Exception as e:
                console.print(f"[red]Chat failed:[/red] {e}")
                messages.pop()


@main.command()
@click.option("--host", "-h", default="127.0.0.1", help="Bind host address")
@click.option("--port", "-p", default=8000, help="Bind port number")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
@click.option("--log-level", default="info", help="Log level (debug/info/warning/error)")
@click.option("--workers", default=1, help="Number of worker processes")
def serve(host: str, port: int, reload: bool, log_level: str, workers: int) -> None:
    """Start the CodeForge AI API server."""
    from codeforge.api.config import AppConfig, RateLimitConfig, ServerConfig

    console.print(f"[bold]Starting CodeForge AI server on {host}:{port}...[/bold]")

    config = AppConfig(
        server=ServerConfig(
            host=host, port=port, reload=reload, log_level=log_level, workers=workers
        ),
        rate_limit=RateLimitConfig(enabled=True),
    )

    try:
        import uvicorn

        from codeforge.api import create_app

        app = create_app(config)
        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
            workers=workers,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Server stopped.[/dim]")
    except Exception as e:
        console.print(f"[red]Server error:[/red] {e}")


if __name__ == "__main__":
    main()
