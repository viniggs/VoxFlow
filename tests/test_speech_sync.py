from voxflow.hermes.tts import speech_envelope

_WORDS = [
    (0.0, 300.0, "Entropia"),
    (400.0, 120.0, "é"),
    (560.0, 240.0, "desordem"),
]


def test_envelope_reports_the_word_currently_leaving_the_speaker() -> None:
    amplitude, word = speech_envelope(_WORDS, 150.0)

    assert word == "Entropia"
    assert 0.3 < amplitude <= 1.0


def test_envelope_falls_silent_between_words() -> None:
    amplitude, word = speech_envelope(_WORDS, 360.0)

    assert word == ""
    assert amplitude < 0.2


def test_envelope_peaks_mid_word_and_fades_at_its_edges() -> None:
    start, _ = speech_envelope(_WORDS, 565.0)
    middle, _ = speech_envelope(_WORDS, 680.0)
    end, _ = speech_envelope(_WORDS, 795.0)

    assert middle > start
    assert middle > end


def test_envelope_before_the_first_word_is_quiet() -> None:
    words = [(500.0, 200.0, "olá")]

    assert speech_envelope(words, 10.0) == (0.12, "")


def test_envelope_without_word_boundaries_still_breathes() -> None:
    """Edge TTS may report no boundaries; the orb must keep moving anyway."""

    samples = [speech_envelope([], position)[0] for position in range(0, 600, 25)]

    assert all(word == "" for _, word in (speech_envelope([], p) for p in range(0, 600, 25)))
    assert all(0.0 <= value <= 1.0 for value in samples)
    assert max(samples) - min(samples) > 0.1


# --- one announcement per word ------------------------------------------------------

#: "luz" ends at 350 ms, so 350-500 is a real gap between words.
_SENTENCE = [(0.0, 200.0, "A"), (200.0, 150.0, "luz"), (500.0, 200.0, "a")]


def test_a_word_is_named_once_however_often_it_is_sampled() -> None:
    """The loop polls every 40 ms; the highlight must not move five times per word.

    `Bubble.highlight_word` scans forward for the *next* occurrence, so repeating the
    text of a word that is still being spoken walked the highlight down the paragraph,
    landing on the following "a" or "de". The voice was in time; the pink was not.
    """

    from voxflow.hermes.tts import SpeechCursor

    cursor = SpeechCursor()
    named = [cursor.update(_SENTENCE, position)[1] for position in range(0, 200, 40)]

    assert named[0] == "A"
    assert named[1:] == ["", "", "", ""]


def test_a_repeated_word_still_advances() -> None:
    # Named by position in the sentence rather than by text, so the second "a" is a
    # new word and not a sample of the first one.
    from voxflow.hermes.tts import SpeechCursor

    cursor = SpeechCursor()
    named = [word for _, word in (cursor.update(_SENTENCE, p) for p in (0, 40, 240, 520))]

    assert named == ["A", "", "luz", "a"]


def test_silence_between_words_is_not_announced() -> None:
    # Crossing a gap must not name anything, and must not swallow the word after it.
    from voxflow.hermes.tts import SpeechCursor

    cursor = SpeechCursor()
    named = [word for _, word in (cursor.update(_SENTENCE, p) for p in (240, 460, 520))]

    assert named == ["luz", "", "a"]
