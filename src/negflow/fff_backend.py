"""Replaceable backend boundary for Hasselblad 3F / .fff conversion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class FffConversionRequest:
    input_path: Path
    output_tiff_path: Path
    backend_mode: str
    converter_command: str | None = None


def convert_fff_to_tiff(request: FffConversionRequest) -> Path:
    """Convert .fff to TIFF once a concrete backend is configured."""
    if request.backend_mode != "external_converter" or not request.converter_command:
        raise FffBackendUnavailable(
            "FFF conversion requires an external converter backend. Configure a converter command before processing .fff files."
        )

    raise FffBackendUnavailable(
        "External converter execution is not implemented yet; this step only defines the backend boundary."
    )
