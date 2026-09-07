"""VoxFlow command-line bootstrap for Phase 0."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from loguru import logger

from voxflow import __version__
from voxflow.config import load_config
from voxflow.diagnostics import run_check
from voxflow.logging_config import configure_logging
from voxflow.paths import get_app_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="voxflow")
    parser.add_argument("--check", action="store_true", help="valida configuração e microfone")
    parser.add_argument("--version", action="version", version=f"VoxFlow {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths = get_app_paths()
    paths.ensure_directories()
    configure_logging(paths.log_dir, console=args.check)
    try:
        config = load_config(paths)
    except Exception:
        logger.exception("Falha ao carregar a configuração")
        return 2
    if args.check:
        result = run_check(config, paths)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    logger.info("VoxFlow {} iniciou na fundação da Fase 0", __version__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

