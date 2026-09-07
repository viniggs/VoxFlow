"""Naming, parsing and matching the keys a person can bind.

Bindings used to be constants in the hook. Once they became the user's to choose, the
hook needed to know more than a number: what a chord is called, whether a key would
have typed something had we not taken it, and therefore whether taking it is fair.
"""

from __future__ import annotations

from dataclasses import dataclass

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_ESCAPE = 0x1B

#: Every virtual-key that means "a modifier is held", mapped to its canonical name.
MODIFIERS: dict[int, str] = {
    0x10: "shift",
    0xA0: "shift",
    0xA1: "shift",
    0x11: "ctrl",
    0xA2: "ctrl",
    0xA3: "ctrl",
    0x12: "alt",
    0xA4: "alt",
    0xA5: "alt",
    0x5B: "win",
    0x5C: "win",
}

#: Order matters: it is the order a chord is written and read in.
MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")

_NAMED: dict[str, int] = {
    "esc": VK_ESCAPE,
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "backspace": 0x08,
    "delete": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "capslock": 0x14,
    "printscreen": 0x2C,
    "scrolllock": 0x91,
    "pause": 0x13,
    "num_multiply": 0x6A,
    "num_add": 0x6B,
    "num_separator": 0x6C,
    "num_subtract": 0x6D,
    "num_decimal": 0x6E,
    "num_divide": 0x6F,
    # Punctuation carries the US-layout name; the label a person sees comes from
    # PUNCTUATION_LABELS so a different layout at least shows a familiar symbol.
    "semicolon": 0xBA,
    "equal": 0xBB,
    "comma": 0xBC,
    "minus": 0xBD,
    "period": 0xBE,
    "slash": 0xBF,
    "backquote": 0xC0,
    "bracketleft": 0xDB,
    "backslash": 0xDC,
    "bracketright": 0xDD,
    "quote": 0xDE,
}

for _index in range(10):
    _NAMED[str(_index)] = 0x30 + _index
    _NAMED[f"num_{_index}"] = 0x60 + _index
for _index in range(26):
    _NAMED[chr(ord("a") + _index)] = 0x41 + _index
for _index in range(1, 25):
    _NAMED[f"f{_index}"] = 0x6F + _index

_BY_CODE: dict[int, str] = {}
for _name, _code in _NAMED.items():
    _BY_CODE.setdefault(_code, _name)

PUNCTUATION_LABELS = {
    "semicolon": ";",
    "equal": "=",
    "comma": ",",
    "minus": "-",
    "period": ".",
    "slash": "/",
    "backquote": "`",
    "bracketleft": "[",
    "backslash": "\\",
    "bracketright": "]",
    "quote": "'",
    "num_add": "Num +",
    "num_subtract": "Num -",
    "num_multiply": "Num *",
    "num_divide": "Num /",
    "num_decimal": "Num .",
}

#: Keys that put a character on screen, or move one, when pressed by themselves.
#: Claiming one of these without a modifier takes typing away from the user, which is
#: the only situation that justifies swallowing the key.
_TYPES_TEXT: set[int] = {
    0x20,  # space
    0x09,  # tab
    0x0D,  # enter
    0x08,  # backspace
}
_TYPES_TEXT |= set(range(0x30, 0x3A))  # 0-9
_TYPES_TEXT |= set(range(0x41, 0x5B))  # A-Z
_TYPES_TEXT |= set(range(0x60, 0x70))  # numpad digits and operators
_TYPES_TEXT |= {0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0, 0xDB, 0xDC, 0xDD, 0xDE}


def types_text(key: int) -> bool:
    """Would this key, alone, have written something?"""

    return key in _TYPES_TEXT


@dataclass(frozen=True, slots=True)
class Hotkey:
    """One chord: a key, plus the modifiers that must be held with it."""

    key: int
    ctrl: bool = False
    alt: bool = False
    shift: bool = False
    win: bool = False

    @property
    def modifiers(self) -> frozenset[str]:
        held = {"ctrl": self.ctrl, "alt": self.alt, "shift": self.shift, "win": self.win}
        return frozenset(name for name, on in held.items() if on)

    @property
    def has_modifier(self) -> bool:
        return bool(self.modifiers)

    @property
    def steals_typing(self) -> bool:
        """True when binding this takes a character away from the keyboard.

        A chord leaves the plain key alone, so only a bare typing key qualifies. This
        is the whole test for whether the hook is allowed to swallow the event."""

        return not self.has_modifier and types_text(self.key)

    def text(self) -> str:
        """The canonical form stored in the configuration."""

        name = _BY_CODE.get(self.key, f"0x{self.key:02x}")
        return "+".join([*(m for m in MODIFIER_ORDER if m in self.modifiers), name])

    def label(self) -> str:
        """The form a person reads in the interface."""

        name = _BY_CODE.get(self.key, f"0x{self.key:02X}")
        pretty = PUNCTUATION_LABELS.get(name, name.replace("num_", "Num ").upper())
        parts = [m.capitalize() for m in MODIFIER_ORDER if m in self.modifiers]
        parts.append(pretty)
        return " + ".join(parts)


def parse(text: str) -> Hotkey | None:
    """Read a chord from the configuration. ``None`` means "not bound"."""

    cleaned = (text or "").strip().lower()
    if not cleaned:
        return None
    parts = [part for part in cleaned.replace(" ", "").split("+") if part]
    if not parts:
        return None
    # "ctrl++" and "num_add" both have to survive: a trailing empty part after the
    # split means the chord ends in a literal plus.
    if cleaned.endswith("+") and not parts[-1].startswith("num"):
        parts.append("equal")
    modifiers = {part for part in parts[:-1] if part in MODIFIER_ORDER}
    unknown = [part for part in parts[:-1] if part not in MODIFIER_ORDER]
    if unknown:
        return None
    key = _NAMED.get(parts[-1])
    if key is None:
        return None
    return Hotkey(
        key=key,
        ctrl="ctrl" in modifiers,
        alt="alt" in modifiers,
        shift="shift" in modifiers,
        win="win" in modifiers,
    )


def matches(hotkey: Hotkey, key: int, held: set[str]) -> bool:
    """Does this event complete the chord, with nothing extra held down?

    Extra modifiers have to disqualify it, otherwise ``num_add`` would fire on
    ``ctrl+num_add`` and the two bindings could never be told apart."""

    return key == hotkey.key and held == set(hotkey.modifiers)


def contains(hotkey: Hotkey, key: int, held: set[str]) -> bool:
    """Like :func:`matches`, but tolerant of modifiers held for another reason.

    Cancelling has to work in the middle of a chord: while ``ctrl+a`` is held, Ctrl is
    necessarily down, and demanding an exact match would make Esc unreachable."""

    return key == hotkey.key and set(hotkey.modifiers) <= held
