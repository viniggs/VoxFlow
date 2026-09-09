"""Chatterbox as a voice, through a process that keeps the model warm.

It cannot be imported: it lives in its own virtual environment with more than two
gigabytes of torch, which is neither importable from here nor shippable in a 108 MB
installer. So VoxFlow starts `packaging/chatterbox_worker.py` with *that* environment's
Python and talks to it over stdin and stdout.

The process is started once and kept: loading the model costs about ten seconds, while a
sentence costs one to three — measured 1.4 s for 3.1 s of audio, faster than real time.
Paying the ten seconds per sentence is what made this look unusable, and it is the reason
it stayed unimplemented until now.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from loguru import logger

from voxflow.fsprobe import is_dir, is_file

#: Loading the model. Ten seconds measured on an RTX 5070; the ceiling is for a cold
#: disk or a machine that falls back to the processor.
_STARTUP_TIMEOUT = 180.0
#: One sentence. Measured between 1.4 s and 2.9 s; the ceiling catches a hang.
_SENTENCE_TIMEOUT = 120.0


def worker_script() -> Path:
    """Where the worker lives, running from source or from the packaged application."""

    bundled = Path(getattr(sys, "_MEIPASS", "")) / "chatterbox_worker.py"
    if is_file(bundled):
        return bundled
    return Path(__file__).resolve().parents[3] / "packaging" / "chatterbox_worker.py"


def staged_worker() -> Path:
    """The worker, somewhere the other Python can safely run it from.

    Running a script file puts *its own directory* at the front of `sys.path`. Inside the
    packaged application that directory is full of extension modules built for VoxFlow's
    Python 3.12, and the worker's Python 3.11 dies importing them:

        ImportError: Module use of python312.dll conflicts with this version of Python.

    So when the script lives in the bundle it is copied out to VoxFlow's own data folder,
    which holds no binaries at all, and run from there.
    """

    source = worker_script()
    bundle = getattr(sys, "_MEIPASS", "")
    if not bundle or bundle not in str(source):
        return source
    staged = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "VoxFlow" / source.name
    try:
        staged.parent.mkdir(parents=True, exist_ok=True)
        if not is_file(staged) or staged.read_bytes() != source.read_bytes():
            shutil.copy2(source, staged)
    except OSError as exc:
        logger.warning("chatterbox_worker_stage_failed error={!s}", exc)
        return source
    return staged


def interpreter(root: str) -> Path:
    """The Python inside Chatterbox's own environment."""

    return Path(root) / ".venv" / "Scripts" / "python.exe"


def installed(root: str) -> tuple[bool, str]:
    """Whether this machine can run Chatterbox, and what is missing when it cannot."""

    if not root.strip():
        return False, "Pasta do Chatterbox não configurada."
    folder = Path(root)
    if not is_dir(folder):
        return False, f"Pasta não encontrada: {folder}"
    if not is_file(interpreter(root)):
        return False, f"Ambiente Python não encontrado em {folder / '.venv'}"
    if not is_dir(folder / "chatterbox" / "src"):
        return False, f"Código do Chatterbox não encontrado em {folder / 'chatterbox'}"
    if not is_file(worker_script()):
        return False, "O worker do Chatterbox não veio neste build."
    return True, "Pronto (processo próprio, modelo fica carregado)."


class ChatterboxSpeaker:
    """The worker process, shared by every sentence in the run."""

    _instance: ChatterboxSpeaker | None = None
    _guard = threading.Lock()

    def __init__(self, root: str, device: str = "cuda") -> None:
        self._root = root
        self._lock = threading.Lock()
        ready, detail = installed(root)
        if not ready:
            raise FileNotFoundError(detail)
        started = time.perf_counter()
        self._process = subprocess.Popen(  # noqa: S603 - our own script, our own paths
            [str(interpreter(root)), "-P", str(staged_worker()), root, device],
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            env=child_environment(),
        )
        hello = self._read(_STARTUP_TIMEOUT)
        if not hello.get("ready"):
            self.close()
            raise RuntimeError(hello.get("error") or "O Chatterbox não subiu.")
        self.sample_rate = int(hello.get("sample_rate", 24_000))
        logger.info(
            "chatterbox_worker_ready load_ms={:.0f} sample_rate={}",
            (time.perf_counter() - started) * 1000,
            self.sample_rate,
        )

    @classmethod
    def shared(cls, root: str, device: str = "cuda") -> ChatterboxSpeaker:
        """One worker per run. A second model would not fit beside the first."""

        with cls._guard:
            current = cls._instance
            if current is not None and current.alive and current._root == root:
                return current
            if current is not None:
                current.close()
            cls._instance = cls(root, device)
            return cls._instance

    @property
    def alive(self) -> bool:
        return self._process.poll() is None

    def say(self, sentence: str, path: Path, reference: str = "") -> None:
        """Write ``sentence`` to ``path``. Raises when the worker cannot."""

        request = {"text": sentence, "path": str(path), "language_id": "pt"}
        if reference.strip():
            request["audio_prompt_path"] = reference.strip()
        with self._lock:
            if not self.alive:
                raise RuntimeError("O processo do Chatterbox encerrou.")
            assert self._process.stdin is not None
            self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            self._process.stdin.flush()
            answer = self._read(_SENTENCE_TIMEOUT)
        if not answer.get("ok"):
            raise RuntimeError(answer.get("error") or "O Chatterbox não devolveu áudio.")

    def _read(self, timeout: float) -> dict[str, object]:
        """One reply line, or an explanation of why there is none.

        `readline` on a dead process returns empty rather than blocking, so the timeout
        is a ceiling on a *hung* worker, not the normal path.
        """

        assert self._process.stdout is not None
        deadline = time.perf_counter() + timeout
        while True:
            line = self._process.stdout.readline()
            if line:
                try:
                    parsed = json.loads(line)
                except ValueError:
                    continue  # a stray print from a library is not our reply
                if isinstance(parsed, dict):
                    return parsed
                continue
            if not self.alive:
                raise RuntimeError("O processo do Chatterbox morreu sem responder.")
            if time.perf_counter() > deadline:
                raise TimeoutError("O Chatterbox não respondeu a tempo.")

    def close(self) -> None:
        try:
            if self._process.poll() is None and self._process.stdin is not None:
                self._process.stdin.write(json.dumps({"stop": True}) + "\n")
                self._process.stdin.flush()
                self._process.wait(timeout=5)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        finally:
            if self._process.poll() is None:
                self._process.kill()


def child_environment() -> dict[str, str]:
    """An environment the other Python can start in.

    The worker runs Python 3.11 while the packaged VoxFlow is a frozen Python 3.12, and
    a child inherits the parent's environment. That was enough to break it: the child
    found `python312.dll` on the inherited PATH and refused to start with

        ImportError: Module use of python312.dll conflicts with this version of Python.

    Only visible in the packaged application — from source there is no bundled runtime
    to collide with, which is exactly why the voice check is run against the installed
    executable.
    """

    environment = dict(os.environ)
    for variable in ("PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONEXECUTABLE"):
        environment.pop(variable, None)
    ours = {str(Path(sys.executable).parent).casefold()}
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        ours.add(str(Path(bundle)).casefold())
    kept = [
        entry
        for entry in environment.get("PATH", "").split(os.pathsep)
        if entry and entry.strip().casefold().rstrip("\\/") not in ours
    ]
    environment["PATH"] = os.pathsep.join(kept)
    return environment


def default_device() -> str:
    """The processor is the honest fallback; the worker also drops to it on its own."""

    return "cpu" if os.environ.get("VOXFLOW_CHATTERBOX_CPU") else "cuda"
