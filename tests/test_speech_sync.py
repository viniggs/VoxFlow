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
