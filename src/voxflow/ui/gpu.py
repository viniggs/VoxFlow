"""GPU rendering for the orb's core: a real volumetric raymarch, rendered offscreen.

The core is the one part of the interface that a 2D rasteriser cannot do justice to.
Light inside a volume is an integral along a ray, and faking it with stacked translucent
strokes reads as gauze rather than as light. So the core is raymarched on the GPU.

Everything happens in an offscreen framebuffer and comes back as a ``QImage``. No OpenGL
widget is ever placed in the window tree, which keeps the frameless, translucent,
always-on-top surfaces exactly as they are. If a context cannot be created — a machine
without usable OpenGL, a remote session — :func:`render_core` returns ``None`` and the
caller falls back to the painter implementation.
"""

from __future__ import annotations

import os

from loguru import logger
from PySide6.QtGui import (
    QImage,
    QOffscreenSurface,
    QOpenGLContext,
    QSurfaceFormat,
    QVector2D,
    QVector3D,
)
from PySide6.QtOpenGL import (
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)

from voxflow.ui.theme import StatePalette

#: Set ``VOXFLOW_ORB=painter`` to force the CPU core, for comparison or diagnosis.
_FORCE_PAINTER = os.environ.get("VOXFLOW_ORB", "").strip().casefold() == "painter"

_GL_COLOR_BUFFER_BIT = 0x00004000
_GL_TRIANGLES = 0x0004
_GL_TEXTURE0 = 0x84C0
_GL_TEXTURE_2D = 0x0DE1
_GL_BLEND = 0x0BE2

#: The bloom is computed at a quarter of the core's resolution; it is a blur, so the
#: detail it would gain from a larger buffer is detail it immediately throws away.
_BLOOM_DIVISOR = 4
_MAX_CORE_PIXELS = 640

_VERTEX = """
#version 330 core
// A full-screen triangle straight from the vertex id: no vertex buffers needed.
out vec2 uv;
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    uv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

_NOISE = """
// Value noise with a cheap integer-free hash. Smooth enough for volume work and far
// cheaper than gradient noise at the octave counts used here.
float hash(vec3 p) {
    p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
    vec3 i = floor(x);
    vec3 f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(mix(hash(i + vec3(0.0, 0.0, 0.0)), hash(i + vec3(1.0, 0.0, 0.0)), f.x),
                   mix(hash(i + vec3(0.0, 1.0, 0.0)), hash(i + vec3(1.0, 1.0, 0.0)), f.x), f.y),
               mix(mix(hash(i + vec3(0.0, 0.0, 1.0)), hash(i + vec3(1.0, 0.0, 1.0)), f.x),
                   mix(hash(i + vec3(0.0, 1.0, 1.0)), hash(i + vec3(1.0, 1.0, 1.0)), f.x), f.y),
               f.z);
}

float fbm(vec3 p) {
    float total = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 4; i++) {
        total += amplitude * vnoise(p);
        p = p * 2.07 + vec3(1.7, 9.2, 4.3);
        amplitude *= 0.5;
    }
    return total;
}

// Ridged noise: the folds of ``1 - |2n - 1|`` stack into filaments, which is what draws
// the bright veins running over the surface.
float ridged(vec3 p) {
    float total = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 4; i++) {
        float n = 1.0 - abs(2.0 * vnoise(p) - 1.0);
        total += amplitude * n * n;
        p = p * 2.13 + vec3(5.1, 2.7, 8.9);
        amplitude *= 0.5;
    }
    return total;
}
"""

_RAYMARCH = """
#version 330 core
in vec2 uv;
out vec4 frag;

uniform float uTime;
uniform float uTurbulence;
uniform float uFlow;
uniform vec3 uDeep;
uniform vec3 uMid;
uniform vec3 uHot;

__NOISE__

// Domain warping: displacing the sample point by another noise field is what turns
// round blobs into the flowing, folded filaments the references are made of.
vec3 warp(vec3 p, float t) {
    vec3 q = vec3(
        fbm(p + vec3(0.0, 1.7, 3.1) + vec3(0.0, t * 0.11, t * 0.05)),
        fbm(p + vec3(5.2, 1.3, 2.8) + vec3(t * -0.09, 0.0, t * 0.07)),
        fbm(p + vec3(2.9, 4.6, 0.7) + vec3(t * 0.06, t * -0.08, 0.0))
    );
    return p + uTurbulence * (q - 0.5) * 1.15;
}

struct Sample { float density; float veins; };

Sample volume(vec3 pos, float t) {
    // A thin gaussian shell. Thickness is what turned this into fog: a fat shell
    // integrates dozens of samples per ray and averages all the structure away.
    float r = length(pos);
    float shell = exp(-pow((r - 0.74) / 0.115, 2.0));
    if (shell < 0.006) return Sample(0.0, 0.0);

    vec3 w = warp(pos * 1.45, t);

    // Ridges cubed: the filaments have to dominate, or the volume reads as wool.
    float veins = ridged(w * 1.6 + vec3(0.0, t * 0.09, 0.0));
    veins = pow(clamp(veins * 1.18, 0.0, 1.0), 4.2);
    float body = fbm(w * 0.9);

    float density = shell * (veins * 1.85 + body * 0.16);
    density = max(0.0, density - 0.055) * 4.4;
    return Sample(density, veins * shell);
}

void main() {
    vec2 p = uv * 2.0 - 1.0;
    vec3 origin = vec3(0.0, 0.0, -3.0);
    vec3 direction = normalize(vec3(p * 1.02, 1.95));

    // Analytic entry and exit of the bounding sphere: every step is spent inside the
    // volume instead of marching through empty space.
    float b = dot(origin, direction);
    float c = dot(origin, origin) - 1.0;
    float h = b * b - c;
    if (h <= 0.0) {
        frag = vec4(0.0);
        return;
    }
    h = sqrt(h);
    float near = -b - h;
    float far = -b + h;

    const int STEPS = 64;
    float span = (far - near) / float(STEPS);
    vec3 colour = vec3(0.0);
    float transmittance = 1.0;

    for (int i = 0; i < STEPS; i++) {
        float t = near + (float(i) + 0.5) * span;
        vec3 pos = origin + direction * t;
        Sample s = volume(pos, uTime * uFlow);
        if (s.density <= 0.0) continue;

        // Staying inside the palette by mixing only between its three colours keeps
        // the hue honest. Adding light to one channel is what produced stray yellows.
        float heat = clamp(s.veins * 2.4, 0.0, 1.0);
        vec3 emission = mix(uDeep, uMid, 0.40 + 0.60 * heat);
        emission = mix(emission, uHot, heat * heat);

        colour += emission * s.density * transmittance * span * 1.35;
        transmittance *= exp(-s.density * span * 0.85);
        if (transmittance < 0.015) break;
    }

    // Radiance has no upper bound, but a pixel does; tone map before writing out.
    vec3 mapped = vec3(1.0) - exp(-colour * 1.55);
    float peak = max(mapped.r, max(mapped.g, mapped.b));
    // Alpha follows the light itself, so the glow keeps its shape without ever letting
    // a channel exceed it. Premultiplied pixels must satisfy colour <= alpha; breaking
    // that makes Qt's integer un-premultiply wrap and paint complementary blotches.
    float alpha = clamp(max(1.0 - transmittance, peak), 0.0, 1.0);
    frag = vec4(mapped * alpha, alpha);
}
"""

_BRIGHT_BLUR = """
#version 330 core
in vec2 uv;
out vec4 frag;
uniform sampler2D uSource;
uniform vec2 uStep;
uniform float uThreshold;

vec4 tap(vec2 at) {
    vec4 c = texture(uSource, at);
    // Only the bright parts are allowed to bloom; blooming everything just fogs it.
    c.rgb = max(vec3(0.0), c.rgb - uThreshold);
    return c;
}

void main() {
    // Nine-tap gaussian along one axis, run twice for a separable blur.
    float weights[5] = float[](0.227027, 0.194594, 0.121621, 0.054054, 0.016216);
    vec4 total = tap(uv) * weights[0];
    for (int i = 1; i < 5; i++) {
        total += tap(uv + uStep * float(i)) * weights[i];
        total += tap(uv - uStep * float(i)) * weights[i];
    }
    frag = total;
}
"""

_COMPOSITE = """
#version 330 core
in vec2 uv;
out vec4 frag;
uniform sampler2D uCore;
uniform sampler2D uBloom;
uniform float uBloomGain;

void main() {
    vec4 core = texture(uCore, uv);
    vec4 bloom = texture(uBloom, uv);
    // Light adds. This is the whole reason the core now reads as glow instead of gauze.
    vec3 colour = core.rgb + bloom.rgb * uBloomGain;
    float alpha = clamp(core.a + bloom.a * uBloomGain, 0.0, 1.0);
    // Still premultiplied, still legal: the halo gets its own alpha from the blurred
    // coverage, so it can carry light without the colour ever passing it.
    frag = vec4(min(colour, vec3(alpha)), alpha);
}
"""


class _ShaderCore:
    """Owns the offscreen context and the three passes that build one core frame."""

    def __init__(self) -> None:
        self._ready = False
        self._failed = False
        self._surface: QOffscreenSurface | None = None
        self._context: QOpenGLContext | None = None
        self._vao: QOpenGLVertexArrayObject | None = None
        self._raymarch: QOpenGLShaderProgram | None = None
        self._blur: QOpenGLShaderProgram | None = None
        self._composite: QOpenGLShaderProgram | None = None
        self._scene: QOpenGLFramebufferObject | None = None
        self._blur_a: QOpenGLFramebufferObject | None = None
        self._blur_b: QOpenGLFramebufferObject | None = None
        self._final: QOpenGLFramebufferObject | None = None
        self._size = 0

    # ------------------------------------------------------------------ Setup

    def _ensure(self) -> bool:
        if self._ready:
            return True
        if self._failed:
            return False
        try:
            self._create()
        except Exception as exc:  # noqa: BLE001 - any failure means "use the CPU core"
            self._failed = True
            logger.warning("orb_gpu_unavailable error_type={} error={!s}", type(exc).__name__, exc)
            return False
        return self._ready

    def _create(self) -> None:
        surface_format = QSurfaceFormat()
        surface_format.setVersion(3, 3)
        surface_format.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        surface_format.setAlphaBufferSize(8)

        surface = QOffscreenSurface()
        surface.setFormat(surface_format)
        surface.create()
        if not surface.isValid():
            raise RuntimeError("offscreen surface unavailable")

        context = QOpenGLContext()
        context.setFormat(surface_format)
        if not context.create() or not context.makeCurrent(surface):
            raise RuntimeError("no usable OpenGL 3.3 context")

        self._surface = surface
        self._context = context
        self._raymarch = self._program(_RAYMARCH.replace("__NOISE__", _NOISE), "raymarch")
        self._blur = self._program(_BRIGHT_BLUR, "blur")
        self._composite = self._program(_COMPOSITE, "composite")
        self._vao = QOpenGLVertexArrayObject()
        self._vao.create()
        self._ready = True
        actual = context.format()
        logger.info(
            "orb_gpu_ready opengl={}.{}", actual.majorVersion(), actual.minorVersion()
        )
        context.doneCurrent()

    @staticmethod
    def _program(fragment: str, name: str) -> QOpenGLShaderProgram:
        program = QOpenGLShaderProgram()
        if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX):
            raise RuntimeError(f"{name} vertex shader: {program.log()}")
        if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, fragment):
            raise RuntimeError(f"{name} fragment shader: {program.log()}")
        if not program.link():
            raise RuntimeError(f"{name} link: {program.log()}")
        return program

    def _resize(self, size: int) -> None:
        if size == self._size:
            return
        fbo_format = QOpenGLFramebufferObjectFormat()
        small = max(8, size // _BLOOM_DIVISOR)
        self._scene = QOpenGLFramebufferObject(size, size, fbo_format)
        self._blur_a = QOpenGLFramebufferObject(small, small, fbo_format)
        self._blur_b = QOpenGLFramebufferObject(small, small, fbo_format)
        self._final = QOpenGLFramebufferObject(size, size, fbo_format)
        self._size = size

    # ----------------------------------------------------------------- Render

    def render(
        self,
        size: int,
        palette: StatePalette,
        seconds: float,
        turbulence: float,
        flow: float,
    ) -> QImage | None:
        if _FORCE_PAINTER or not self._ensure():
            return None
        size = max(64, min(_MAX_CORE_PIXELS, int(size)))
        context, surface = self._context, self._surface
        if context is None or surface is None:
            return None
        if not context.makeCurrent(surface):
            return None
        try:
            self._resize(size)
            functions = context.functions()
            functions.glDisable(_GL_BLEND)
            self._vao.bind()  # type: ignore[union-attr]

            self._pass_raymarch(functions, palette, seconds, turbulence, flow)
            self._pass_bloom(functions)
            image = self._pass_composite(functions)

            self._vao.release()  # type: ignore[union-attr]
            return image
        except Exception as exc:  # noqa: BLE001 - never let a frame take the app down
            self._failed = True
            logger.warning("orb_gpu_frame_failed error_type={}", type(exc).__name__)
            return None
        finally:
            context.doneCurrent()

    def _pass_raymarch(
        self,
        functions,  # noqa: ANN001 - QOpenGLFunctions has no stable Python annotation
        palette: StatePalette,
        seconds: float,
        turbulence: float,
        flow: float,
    ) -> None:
        scene, program = self._scene, self._raymarch
        assert scene is not None and program is not None
        scene.bind()
        functions.glViewport(0, 0, self._size, self._size)
        functions.glClearColor(0.0, 0.0, 0.0, 0.0)
        functions.glClear(_GL_COLOR_BUFFER_BIT)
        program.bind()
        program.setUniformValue1f("uTime", float(seconds))
        program.setUniformValue1f("uTurbulence", float(turbulence))
        program.setUniformValue1f("uFlow", float(flow))
        program.setUniformValue("uDeep", _vector(palette.glow, 0.55))
        program.setUniformValue("uMid", _vector(palette.core, 1.0))
        program.setUniformValue("uHot", _vector(palette.core, 1.0, whiten=0.62))
        functions.glDrawArrays(_GL_TRIANGLES, 0, 3)
        program.release()
        scene.release()

    def _pass_bloom(self, functions) -> None:  # noqa: ANN001
        blur, first, second, scene = self._blur, self._blur_a, self._blur_b, self._scene
        assert blur is not None and first is not None and second is not None
        assert scene is not None
        small = first.width()
        step = 1.0 / float(small)
        # The threshold applies once, on the way in; the second pass just blurs.
        for target, source_texture, offset, threshold in (
            (first, scene.texture(), (step, 0.0), 0.22),
            (second, first.texture(), (0.0, step), 0.0),
        ):
            target.bind()
            functions.glViewport(0, 0, small, small)
            functions.glClearColor(0.0, 0.0, 0.0, 0.0)
            functions.glClear(_GL_COLOR_BUFFER_BIT)
            blur.bind()
            functions.glActiveTexture(_GL_TEXTURE0)
            functions.glBindTexture(_GL_TEXTURE_2D, source_texture)
            blur.setUniformValue1i("uSource", 0)
            blur.setUniformValue("uStep", _vector2(offset))
            blur.setUniformValue1f("uThreshold", threshold)
            functions.glDrawArrays(_GL_TRIANGLES, 0, 3)
            blur.release()
            target.release()

    def _pass_composite(self, functions) -> QImage:  # noqa: ANN001
        final, program = self._final, self._composite
        scene, bloom = self._scene, self._blur_b
        assert final is not None and program is not None
        assert scene is not None and bloom is not None
        final.bind()
        functions.glViewport(0, 0, self._size, self._size)
        functions.glClearColor(0.0, 0.0, 0.0, 0.0)
        functions.glClear(_GL_COLOR_BUFFER_BIT)
        program.bind()
        functions.glActiveTexture(_GL_TEXTURE0)
        functions.glBindTexture(_GL_TEXTURE_2D, scene.texture())
        program.setUniformValue1i("uCore", 0)
        functions.glActiveTexture(_GL_TEXTURE0 + 1)
        functions.glBindTexture(_GL_TEXTURE_2D, bloom.texture())
        program.setUniformValue1i("uBloom", 1)
        program.setUniformValue1f("uBloomGain", 0.55)
        functions.glDrawArrays(_GL_TRIANGLES, 0, 3)
        program.release()
        image = final.toImage()
        final.release()
        functions.glActiveTexture(_GL_TEXTURE0)
        return image


def _vector(colour, scale: float = 1.0, whiten: float = 0.0) -> QVector3D:
    """A palette colour as linear-ish RGB for the shader."""

    red = colour.redF() * scale
    green = colour.greenF() * scale
    blue = colour.blueF() * scale
    if whiten > 0.0:
        red += (1.0 - red) * whiten
        green += (1.0 - green) * whiten
        blue += (1.0 - blue) * whiten
    return QVector3D(red, green, blue)


def _vector2(pair: tuple[float, float]) -> QVector2D:
    """The blur step, in texture units."""

    return QVector2D(pair[0], pair[1])


_CORE = _ShaderCore()


def render_core(
    size: int,
    palette: StatePalette,
    seconds: float,
    turbulence: float,
    flow: float,
) -> QImage | None:
    """Render one core frame on the GPU, or ``None`` if the GPU path is unavailable."""

    return _CORE.render(size, palette, seconds, turbulence, flow)
