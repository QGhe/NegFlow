"""Command-line entry point for NegFlow."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .fff_backend import FffBackendUnavailable
from .runner import process_fff, process_tiff


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="negflow",
        description="Traceable CLI workflow for Hasselblad X5 negative scan processing.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    process_tiff_parser = subparsers.add_parser(
        "process-tiff",
        help="Create a task folder from an existing TIFF working scan.",
    )
    process_tiff_parser.add_argument("input", type=Path, help="Input .tif or .tiff file")
    process_tiff_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Output root directory",
    )
    process_tiff_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/default.yaml"),
        help="Configuration file to snapshot for this task",
    )
    process_tiff_parser.add_argument(
        "--preset",
        default="neutral_archive",
        help="Preset name recorded in sidecar metadata",
    )

    process_parser = subparsers.add_parser(
        "process",
        help="Create a task from a .fff scan through the configured backend.",
    )
    process_parser.add_argument("input", type=Path, help="Input .fff file")
    process_parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Output root directory",
    )
    process_parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/default.yaml"),
        help="Configuration file to snapshot for this task",
    )
    process_parser.add_argument(
        "--preset",
        default="neutral_archive",
        help="Preset name recorded in sidecar metadata",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "process-tiff":
        result = process_tiff(
            input_path=args.input,
            output_root=args.output,
            config_path=args.config,
            preset=args.preset,
        )
        print(f"Created task: {result.task_id}")
        print(f"Task directory: {result.task_dir}")
        print(f"Sidecar: {result.sidecar_path}")
        return 0

    if args.command == "process":
        try:
            result = process_fff(
                input_path=args.input,
                output_root=args.output,
                config_path=args.config,
                preset=args.preset,
            )
        except FffBackendUnavailable as exc:
            print(f"FFF backend unavailable: {exc}", file=sys.stderr)
            if exc.sidecar_path:
                print(f"Sidecar: {exc.sidecar_path}", file=sys.stderr)
            if exc.log_path:
                print(f"Log: {exc.log_path}", file=sys.stderr)
            return 1

        print(f"Created task: {result.task_id}")
        print(f"Task directory: {result.task_dir}")
        print(f"Sidecar: {result.sidecar_path}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
