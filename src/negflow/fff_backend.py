"""Replaceable backend boundary for Hasselblad 3F / .fff conversion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

SUPPORTED_FFF_EXTENSIONS = {".fff"}


class FffBackendUnavailable(RuntimeError):
    """Raised when .fff input is valid but no conversion backend is configured."""

    def __init__(
        self,
        message: str,
        *,
        task_dir: Path | None = None,
        sidecar_path: Path | None = None,
        log_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.task_dir = task_dir
        self.sidecar_path = sidecar_path
        self.log_path = log_path


class FffConversionError(RuntimeError):
    """Raised when an external converter is configured but conversion fails."""

    def __init__(
        self,
        message: str,
        *,
        command: str | None = None,
        returncode: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        super().__init__(message)
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@dataclass(frozen=True)
class FffBackendConfig:
    mode: str = "tiff_passthrough"
    keep_intermediate_tiff: bool = True
    external_converter_command: str | None = None


@dataclass(frozen=True)
class FffConversionRequest:
    input_path: Path
    output_tiff_path: Path
    backend_mode: str
    converter_command: str | None = None


@dataclass(frozen=True)
class FffConversionResult:
    output_tiff_path: Path
    backend_mode: str
    command_template: str
    expanded_command: str
    returncode: int
    stdout: str
    stderr: str


def load_backend_config(config_path: Path) -> FffBackendConfig:
    """Load just enough YAML to resolve backend settings without extra deps."""
    if not config_path.exists():
        return FffBackendConfig()

    config_data = _load_simple_yaml_mapping(config_path)
    backend_data = config_data.get("backend")
    if not isinstance(backend_data, dict):
        return FffBackendConfig()

    mode = str(backend_data.get("mode", "tiff_passthrough"))
    keep_intermediate_tiff = bool(backend_data.get("keep_intermediate_tiff", True))
    converter_command = backend_data.get("external_converter_command")
    if converter_command is None:
        converter_command = backend_data.get("converter_command")
    if converter_command is not None:
        converter_command = str(converter_command)

    return FffBackendConfig(
        mode=mode,
        keep_intermediate_tiff=keep_intermediate_tiff,
        external_converter_command=converter_command,
    )


def convert_fff_to_tiff(request: FffConversionRequest) -> FffConversionResult:
    """Convert .fff to TIFF through a configured external converter command."""
    if request.backend_mode != "external_converter" or not request.converter_command:
        raise FffBackendUnavailable(
            "FFF conversion requires an external converter backend. Configure a converter command before processing .fff files."
        )

    request.output_tiff_path.parent.mkdir(parents=True, exist_ok=True)
    expanded_command = request.converter_command.format(
        input_path=str(request.input_path),
        output_tiff_path=str(request.output_tiff_path),
        input_path_quoted=subprocess.list2cmdline([str(request.input_path)]),
        output_tiff_path_quoted=subprocess.list2cmdline([str(request.output_tiff_path)]),
        input_stem=request.input_path.stem,
        output_tiff_stem=request.output_tiff_path.stem,
    )
    completed = subprocess.run(
        expanded_command,
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise FffConversionError(
            f"External converter failed with exit code {completed.returncode}.",
            command=expanded_command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    if not request.output_tiff_path.exists():
        raise FffConversionError(
            "External converter completed without creating the expected TIFF output.",
            command=expanded_command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    return FffConversionResult(
        output_tiff_path=request.output_tiff_path,
        backend_mode=request.backend_mode,
        command_template=request.converter_command,
        expanded_command=expanded_command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _load_simple_yaml_mapping(config_path: Path) -> dict[str, object]:
    root: dict[str, object] = {}
    stack: list[tuple[int, dict[str, object]]] = [(-1, root)]

    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = line.lstrip(" ")
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        while indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]

        if value == "":
            child: dict[str, object] = {}
            current[key] = child
            stack.append((indent, child))
            continue

        current[key] = _parse_yaml_scalar(value)

    return root


def _parse_yaml_scalar(value: str) -> object:
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
