"""Study mode: the commands the app answers itself, and the session's written record.

Two things live here, and neither of them talks to the network.

The commands are intercepted *before* a turn is sent. "modo ditado" must not become a
question about dictation, and "nova sessão" must not be answered with a polite offer to
start one. The app owns these words.

The log is the other half: a conversation that is only spoken leaves nothing to study
from afterwards. Every turn is appended to a Markdown file for the day, so the session
can be reread, and so the summary asked for at the end has something to be about.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from loguru import logger


class StudyCommand(Enum):
    """What the app does itself instead of sending it to Hermes."""

    NEW_SESSION = "new_session"
    SCREENSHOT = "screenshot"
    DICTATION_MODE = "dictation_mode"
    REPEAT = "repeat"
    SLOWER = "slower"
    FASTER = "faster"
    PAUSE = "pause"
    END_SESSION = "end_session"


@dataclass(frozen=True, slots=True)
class Recognised:
    """A command, and whatever the user said after it.

    ``remainder`` matters for the screenshot: "olha minha tela e explica esse slide" is
    one utterance, and the part after the command is the question that travels with the
    image. For every other command it is ignored.
    """

    command: StudyCommand
    remainder: str = ""


#: Longest first, so "encerra sessão" is never read as "encerra" plus noise, and so
#: "nova sessão" cannot be swallowed by a shorter phrase that happens to prefix it.
_PHRASES: tuple[tuple[str, StudyCommand], ...] = (
    ("nova sessao", StudyCommand.NEW_SESSION),
    ("comeca uma nova sessao", StudyCommand.NEW_SESSION),
    ("comecar nova sessao", StudyCommand.NEW_SESSION),
    ("encerra sessao", StudyCommand.END_SESSION),
    ("encerrar sessao", StudyCommand.END_SESSION),
    ("encerra a sessao", StudyCommand.END_SESSION),
    ("termina a sessao", StudyCommand.END_SESSION),
    ("fim de sessao", StudyCommand.END_SESSION),
    ("captura a tela", StudyCommand.SCREENSHOT),
    ("capture a tela", StudyCommand.SCREENSHOT),
    ("captura minha tela", StudyCommand.SCREENSHOT),
    ("olha minha tela", StudyCommand.SCREENSHOT),
    ("olha a minha tela", StudyCommand.SCREENSHOT),
    ("olha pra minha tela", StudyCommand.SCREENSHOT),
    ("olha para minha tela", StudyCommand.SCREENSHOT),
    ("olhe minha tela", StudyCommand.SCREENSHOT),
    ("ve minha tela", StudyCommand.SCREENSHOT),
    ("veja minha tela", StudyCommand.SCREENSHOT),
    ("modo ditado", StudyCommand.DICTATION_MODE),
    ("voltar para o ditado", StudyCommand.DICTATION_MODE),
    ("volta para o ditado", StudyCommand.DICTATION_MODE),
    ("mais devagar", StudyCommand.SLOWER),
    ("fala mais devagar", StudyCommand.SLOWER),
    ("mais rapido", StudyCommand.FASTER),
    ("fala mais rapido", StudyCommand.FASTER),
    ("repete", StudyCommand.REPEAT),
    ("repita", StudyCommand.REPEAT),
    ("repete isso", StudyCommand.REPEAT),
    ("pausa", StudyCommand.PAUSE),
    ("pause", StudyCommand.PAUSE),
    ("para", StudyCommand.PAUSE),
)

#: Words the transcription adds around a command without changing it.
_FILLER = ("por favor", "friday", "ei", "ok", "entao", "ai")

#: A command has to be the whole utterance, or start it. Beyond this many words the
#: sentence is a question that happens to contain the words, not an order — "pausa"
#: matters, "eu não sei se dá para dar uma pausa nisso agora" does not.
_MAX_COMMAND_WORDS = 12


def _fold(text: str) -> str:
    """Lower case, unaccented, punctuation-free — the shape a match is done in.

    Transcription writes "sessão" and the phrase table cannot depend on the accent
    having survived the microphone, the model and pt-BR spelling of the day.
    """

    stripped = unicodedata.normalize("NFD", text)
    without_accents = "".join(ch for ch in stripped if unicodedata.category(ch) != "Mn")
    cleaned = re.sub(r"[^\w\s]", " ", without_accents, flags=re.UNICODE)
    return " ".join(cleaned.lower().split())


def _without_filler(words: list[str]) -> list[str]:
    text = " ".join(words)
    for filler in _FILLER:
        text = re.sub(rf"^{filler}\b", "", text).strip()
    return text.split()


def _strip_connector(remainder: str) -> str:
    """Drop the word that joins the command to the question.

    "olha minha tela e explica esse slide" leaves "e explica esse slide", and that
    stray "e" would be sent to Hermes as the first word of the question.
    """

    return re.sub(r"^(e|entao|ai|que|dai)\b", "", remainder).strip()


def match(utterance: str) -> Recognised | None:
    """Recognise a command, or ``None`` when the words are a question for Hermes."""

    folded = _fold(utterance)
    if not folded:
        return None
    words = _without_filler(folded.split())
    if not words or len(words) > _MAX_COMMAND_WORDS:
        return None
    folded = " ".join(words)
    best: Recognised | None = None
    best_length = 0
    for phrase, command in _PHRASES:
        if folded != phrase and not folded.startswith(f"{phrase} "):
            continue
        # A longer phrase wins: "encerra a sessao" must not be read as "encerra sessao"
        # missing a word, nor "pausa" steal the front of a longer order.
        if len(phrase) <= best_length:
            continue
        remainder = _strip_connector(folded[len(phrase) :].strip())
        best = Recognised(command, remainder)
        best_length = len(phrase)
    if best is not None:
        logger.info(
            "study_command command={} has_remainder={}",
            best.command.value,
            bool(best.remainder),
        )
    return best


class SessionLog:
    """The day's conversation, in Markdown, one file per day.

    Appended turn by turn rather than written at the end: a session that crashes, or one
    the user simply closes, still leaves everything said up to that point.
    """

    def __init__(self, directory: Path, *, now: object = None) -> None:
        self._directory = Path(directory)
        self._clock = now if callable(now) else datetime.now
        self._path: Path | None = None

    @property
    def path(self) -> Path:
        """The file for today, named for the day and created on first use."""

        stamp = self._clock()
        candidate = self._directory / f"{stamp:%Y-%m-%d}.md"
        if self._path != candidate:
            self._path = candidate
        return candidate

    def start(self, conversation_id: str) -> Path:
        """Open a session heading. Returns the file it was written to."""

        return self._append(
            f"\n## Sessão iniciada {self._clock():%H:%M} — `{conversation_id}`\n\n"
        )

    def user(self, text: str) -> Path:
        return self._append(f"**{self._clock():%H:%M} · Você:** {text.strip()}\n\n")

    def agent(self, text: str) -> Path:
        return self._append(f"**{self._clock():%H:%M} · Friday:** {text.strip()}\n\n")

    def note(self, text: str) -> Path:
        """Something the app did, not something either of them said."""

        return self._append(f"> _{self._clock():%H:%M} · {text.strip()}_\n\n")

    def _append(self, block: str) -> Path:
        path = self.path
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            new_file = not path.exists()
            with path.open("a", encoding="utf-8") as handle:
                if new_file:
                    handle.write(f"# VoxFlow — estudo de {self._clock():%d/%m/%Y}\n")
                handle.write(block)
        except OSError as exc:
            # A conversation must not stop because a disk did. Said once, in the log.
            logger.warning("session_log_failed error_type={} error={!s}", type(exc).__name__, exc)
        return path


#: What Hermes is asked for when the session ends. Spoken aloud like everything else,
#: so it asks for prose rather than a table.
CLOSING_PROMPT = (
    "A sessão de estudo terminou. Faça um resumo do que estudamos nesta conversa, "
    "em poucas frases, e depois liste três perguntas de revisão para eu responder "
    "depois. Fale de forma natural, sem markdown pesado."
)
