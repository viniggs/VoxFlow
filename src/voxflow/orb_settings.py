"""Persisted, bounded per-state orb controls; approved appearance is the default."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

OrbState = Literal[
    "idle",
    "listening",
    "transcribing",
    "thinking",
    "speaking",
    "injecting",
    "error",
]
STATES = ("idle", "listening", "transcribing", "thinking", "speaking", "injecting", "error")


class OrbProfile(BaseModel):
    """One complete visual profile for a Friday mood.

    The ranges are deliberately kept here, close to the persisted data model. The
    studio uses the same limits, so a value changed during a live preview cannot
    produce a shader value outside the safe visual envelope.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    core_speed: float = Field(1.0, ge=0.05, le=3.0)
    turbulence: float = Field(1.0, ge=0.0, le=2.0)
    core_size: float = Field(1.0, ge=0.65, le=1.18)
    focus: float = Field(3.5, ge=0.0, le=5.0)
    energy: float = Field(1.0, ge=0.2, le=2.0)
    white: float = Field(0.54, ge=0.0, le=1.0)
    bloom: float = Field(0.42, ge=0.0, le=1.2)
    interior: float = Field(1.0, ge=0.0, le=2.0)

    eruption_energy: float = Field(1.0, ge=0.0, le=2.0)
    eruption_speed: float = Field(1.0, ge=0.5, le=2.5)
    eruption_size: float = Field(1.0, ge=0.0, le=1.3)
    eruption_rate: float = Field(1.0, ge=0.2, le=3.0)

    mesh_amplitude: float = Field(1.0, ge=0.0, le=2.0)
    mesh_speed: float = Field(1.0, ge=0.05, le=3.0)
    mesh_frequency: float = Field(1.0, ge=0.4, le=2.0)
    bead_size: float = Field(1.0, ge=0.5, le=2.0)
    mesh_light: float = Field(1.0, ge=0.1, le=2.0)
    mesh_white: float = Field(0.94, ge=0.0, le=1.0)
    hover: float = Field(1.0, ge=0.0, le=2.0)

    voice_gain: float = Field(1.0, ge=0.1, le=3.0)
    voice_waves: float = Field(1.0, ge=0.0, le=2.5)
    voice_threshold: float = Field(0.16, ge=0.01, le=0.9)
    attack: float = Field(0.065, ge=0.02, le=0.5)
    release: float = Field(0.23, ge=0.05, le=1.5)
    voice_interval: float = Field(0.36, ge=0.16, le=1.0)

    # Empty means “use the state palette”. A hex value is persisted so the YAML
    # stays human-readable and QColorDialog can round-trip it without loss.
    core_color: str = Field("", pattern=r"^(#[0-9a-fA-F]{6})?$")
    shadow_color: str = Field("", pattern=r"^(#[0-9a-fA-F]{6})?$")
    mesh_color: str = Field("", pattern=r"^(#[0-9a-fA-F]{6})?$")


def default_profile(state: str) -> OrbProfile:
    """Return the approved visual baseline for one state."""

    return OrbProfile(white=0.62 if state == "idle" else 0.54)


# The UI intentionally reads this table instead of Pydantic's internal metadata. It
# keeps the slider scale stable if a validation implementation changes upstream.
FIELD_BOUNDS: dict[str, tuple[float, float]] = {
    "core_speed": (0.05, 3.0),
    "turbulence": (0.0, 2.0),
    "core_size": (0.65, 1.18),
    "focus": (0.0, 5.0),
    "energy": (0.2, 2.0),
    "white": (0.0, 1.0),
    "bloom": (0.0, 1.2),
    "interior": (0.0, 2.0),
    "eruption_energy": (0.0, 2.0),
    "eruption_speed": (0.5, 2.5),
    "eruption_size": (0.0, 1.3),
    "eruption_rate": (0.2, 3.0),
    "mesh_amplitude": (0.0, 2.0),
    "mesh_speed": (0.05, 3.0),
    "mesh_frequency": (0.4, 2.0),
    "bead_size": (0.5, 2.0),
    "mesh_light": (0.1, 2.0),
    "mesh_white": (0.0, 1.0),
    "hover": (0.0, 2.0),
    "voice_gain": (0.1, 3.0),
    "voice_waves": (0.0, 2.5),
    "voice_threshold": (0.01, 0.9),
    "attack": (0.02, 0.5),
    "release": (0.05, 1.5),
    "voice_interval": (0.16, 1.0),
}


class OrbStudioConfig(BaseModel):
    """Complete persisted configuration for the live orb studio."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    states: dict[OrbState, OrbProfile] = Field(default_factory=lambda: {
        state: default_profile(state) for state in STATES
    })

    @model_validator(mode="after")
    def complete_states(self) -> "OrbStudioConfig":
        """Migrate older or hand-written configs without breaking the studio."""

        for state in STATES:
            self.states.setdefault(state, default_profile(state))
        return self


_live = OrbStudioConfig()


def set_live(config: OrbStudioConfig) -> None:
    """Publish a deep copy for every orb, including windows already on screen."""

    global _live
    _live = config.model_copy(deep=True)


def profile_for(state: str) -> OrbProfile:
    """Read the live profile while tolerating enum values from the UI layer."""

    value = getattr(state, "value", state)
    return _live.states.get(value) or default_profile(str(value))
