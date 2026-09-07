"""GPU rendering for Friday: volumetric core, ordered pearl shell and soft light shafts.

The core is the one part of the interface that a 2D rasteriser cannot do justice to.
Light inside a volume is an integral along a ray, and faking it with stacked translucent
strokes reads as gauze rather than as light. So the core is raymarched on the GPU.

Everything happens in an offscreen framebuffer and comes back as a ``QImage``. No OpenGL
widget is ever placed in the window tree, which keeps the frameless, translucent,
always-on-top surfaces exactly as they are. If a context cannot be created — a machine
without usable OpenGL, a remote session — :func:`render_orb` returns ``None`` and the
caller falls back to the painter implementation.
"""

from __future__ import annotations

import os
from dataclasses import replace

from loguru import logger
from PySide6.QtGui import (
    QColor,
    QImage,
    QOffscreenSurface,
    QOpenGLContext,
    QSurfaceFormat,
    QVector2D,
    QVector3D,
    QVector4D,
)
from PySide6.QtOpenGL import (
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLVertexArrayObject,
)

from voxflow.orb_settings import OrbProfile
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
uniform float uAmplitude;
uniform float uInterior;
uniform float uCoreSize;
uniform float uEnergy;
uniform vec4 uEruption;

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

#define CORE_BOUND 0.94
#define CORE_RADIUS 0.575
#define MOTE_RADIUS 0.88

struct Sample { float density; float veins; };

Sample volume(vec3 pos, float t) {
    // A thin gaussian shell. Thickness is what turned this into fog: a fat shell
    // integrates dozens of samples per ray and averages all the structure away.
    pos /= uCoreSize;
    float r = length(pos);
    float shell = exp(-pow((r - CORE_RADIUS) / 0.078, 2.0));
    // Sparse eruptions are part of the volume: the very same warped ridges,
    // emission and absorption shade both the nebula and its escaping material.
    float plasma = 0.0;
    if (r > CORE_RADIUS - 0.07) {
        for (int plume = 0; plume < 3; plume++) {
            float seed = float(plume) * 2.39996;
            float cycle = uTime * uEruption.y / 7.0 + float(plume) / 3.0;
            float age = min(1.0,fract(cycle)*uEruption.z);
            float cycleFade = 1.0-smoothstep(0.85,1.0,fract(cycle));
            float epoch = floor(cycle);
            // A new site each time; fade to zero before the direction changes.
            float angle = seed + epoch * 1.73;
            vec3 axis = normalize(vec3(cos(angle),sin(angle),0.22*sin(angle*1.7)));
            vec3 tangent = vec3(-sin(angle),cos(angle),0.0);
            float rise = smoothstep(0.02,0.42,age);
            float life = smoothstep(0.0,0.16,age)*(1.0-smoothstep(0.45,0.76,age));
            float height = 0.055 + 0.19*rise*uEruption.x;
            float altitude = dot(pos,axis)-(CORE_RADIUS-0.01);
            float along = clamp(altitude / height,0.0,1.0);
            vec3 bend = tangent * (0.065*sin(along*2.8-age*2.0)*along*rise);
            vec3 lateral = pos-axis*dot(pos,axis)-bend;
            float width = mix(0.080,0.020,along);
            float tube = exp(-dot(lateral,lateral)/(width*width));
            float tip = 1.0-smoothstep(height*0.6,height,altitude);
            float root = smoothstep(-0.06,0.015,altitude);
            // The neck thins as the outer knot lifts free of the surface.
            float release = smoothstep(0.42,0.65,age);
            plasma += tube*tip*root*life*(1.0-release*0.85)*uEruption.x*cycleFade*uEruption.w;
            vec3 knot = axis*(CORE_RADIUS+(0.18*rise+0.10*release)*uEruption.x)
                + tangent*(0.045*rise+0.035*release);
            vec3 offset = pos-knot;
            float radial = dot(offset,axis);
            vec3 crossSection = offset-axis*radial;
            float cloud = exp(-dot(crossSection,crossSection)/0.0020
                -radial*radial/0.0038);
            float escape = smoothstep(0.30,0.50,age)*(1.0-smoothstep(0.60,0.92,age));
            plasma += cloud*escape*0.9*uEruption.x*cycleFade*uEruption.w;
        }
    }
    shell = max(shell,plasma);
    float interiorMask = uInterior * (1.0-smoothstep(0.34,0.51,r));
    if (shell < 0.006 && interiorMask < 0.006) return Sample(0.0, 0.0);

    vec3 w = warp(pos * 2.55, t);

    // Two curved currents at different depths. Empty space remains between them;
    // no uniform fog or extra inner shell fills the centre. Both follow the same
    // domain warp as the surface, and the raymarch naturally occludes them.
    float innerEnergy = 0.0;
    if (interiorMask > 0.006) {
        vec3 q = pos + (w-pos*2.55)*0.22;
        float clock = t*0.065;
        vec2 first = vec2(q.y-0.11*sin(q.x*7.0+clock),
                         q.z-0.10-0.075*cos(q.x*6.0-clock*0.8));
        vec2 second = vec2(q.x-0.13*cos(q.y*6.5-clock*0.7),
                          q.z+0.13-0.06*sin(q.y*8.0+clock));
        float strands = exp(-dot(first,first)/0.0015)
                      + 0.72*exp(-dot(second,second)/0.0012);
        float texture = 0.45+0.55*vnoise(w*7.0+vec3(0.0,t*0.14,0.0));
        innerEnergy = strands*texture*interiorMask;
    }

    if (shell < 0.006) return Sample(innerEnergy*3.6,innerEnergy*0.65);

    // Ridges cubed: the filaments have to dominate, or the volume reads as wool.
    float veins = ridged(w * 1.6 + vec3(0.0, t * 0.09, 0.0));
    veins = pow(clamp(veins * 1.18, 0.0, 1.0), 4.2);
    float body = fbm(w * 0.9);

    float density = shell * (veins * 1.85 + body * 0.16);
    density = max(0.0, density - 0.055) * 4.4;
    return Sample(density+innerEnergy*3.6, max(veins*shell,innerEnergy*0.65));
}

void main() {
    vec2 p = uv * 2.0 - 1.0;
    vec3 origin = vec3(0.0, 0.0, -3.0);
    vec3 direction = normalize(vec3(p * 1.02, 1.95));

    // Analytic entry and exit of the bounding sphere: every step is spent inside the
    // volume instead of marching through empty space.
    vec3 colour = vec3(0.0);
    float transmittance = 1.0;

    float b = dot(origin, direction);
    float c = dot(origin, origin) - CORE_BOUND * CORE_BOUND * uCoreSize * uCoreSize;
    float h = b * b - c;
    // Rays that miss the core still carry motes, so this only skips the march.
    float span = 0.0;
    float near = 0.0;
    const int STEPS = 80;
    if (h > 0.0) {
    h = sqrt(h);
    near = -b - h;
    float far = -b + h;
    span = (far - near) / float(STEPS);

    for (int i = 0; i < STEPS; i++) {
        float t = near + (float(i) + 0.5) * span;
        vec3 pos = origin + direction * t;
        Sample s = volume(pos, uTime * uFlow * 2.30);
        if (s.density <= 0.0) continue;

        // Staying inside the palette by mixing only between its three colours keeps
        // the hue honest. Adding light to one channel is what produced stray yellows.
        float heat = clamp(s.veins * 2.4, 0.0, 1.0);
        vec3 emission = mix(uDeep, uMid, 0.40 + 0.60 * heat);
        emission = mix(emission, uHot, heat * heat);
        colour += emission * s.density * transmittance * span * 1.35 * uEnergy;
        transmittance *= exp(-s.density * span * 0.85);
        if (transmittance < 0.015) break;
    }
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

_CORE_FOCUS = """
#version 330 core
in vec2 uv;
out vec4 frag;
uniform sampler2D uSource;
uniform float uDefinition;
void main() {
    vec2 texel = 2.0 / vec2(textureSize(uSource,0));
    vec4 center = texture(uSource,uv);
    vec4 soft = center*0.25;
    soft += texture(uSource,uv+vec2(texel.x,0))*0.125;
    soft += texture(uSource,uv-vec2(texel.x,0))*0.125;
    soft += texture(uSource,uv+vec2(0,texel.y))*0.125;
    soft += texture(uSource,uv-vec2(0,texel.y))*0.125;
    soft += texture(uSource,uv+texel)*0.0625;
    soft += texture(uSource,uv-texel)*0.0625;
    soft += texture(uSource,uv+vec2(texel.x,-texel.y))*0.0625;
    soft += texture(uSource,uv+vec2(-texel.x,texel.y))*0.0625;
    // Local contrast only: preserve the original volume, animation and palette.
    // Fade in on luminous material to avoid ringing around the transparent edge.
    float strength = uDefinition*1.15*smoothstep(0.025,0.16,center.a);
    vec4 focused = max(vec4(0),center+(center-soft)*strength);
    float alpha = clamp(max(focused.a,max(focused.r,max(focused.g,focused.b))),0.0,1.0);
    frag = vec4(clamp(focused.rgb,vec3(0),vec3(alpha)),alpha);
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



# Each pearl is a small GPU billboard. Rings have proportional populations, keeping
# spacing even at the poles. No random offsets, particle simulation or CPU uploads.
_PEARL_VERTEX = """
#version 330 core
out vec2 pearlUV;
out float pearlDepth;
out float pearlCrest;
uniform float uTime;
uniform float uAmplitude;
uniform float uSize;
uniform vec4 uMotion;
uniform vec4 uMesh;
uniform vec3 uHover;
uniform vec2 uVoice0;
uniform vec2 uVoice1;
uniform vec2 uVoice2;
uniform vec2 uVoice3;
uniform float uClock;
float voiceWave(vec3 normal, vec2 pulse) {
    float distance = acos(clamp(dot(normal, normalize(vec3(0.25,-0.65,-1.0))),-1.0,1.0));
    float travel = distance - pulse.x * 2.1;
    return pulse.y * sin(travel * 16.0) * exp(-travel*travel / 0.22)
        * exp(-pulse.x * 1.1);
}
void main() {
    int bead = gl_VertexID / 6;
    int ring = bead / 224;
    int column = bead % 224;
    float lat = 3.14159265 * (float(ring) + 0.5) / 112.0;
    int population = max(4, int(floor(224.0 * sin(lat) / 4.0 + 0.5)) * 4);
    vec2 corners[6] = vec2[](vec2(-1,-1),vec2(1,-1),vec2(1,1),
                             vec2(-1,-1),vec2(1,1),vec2(-1,1));
    pearlUV = corners[gl_VertexID % 6];
    if (column >= population) {
        gl_Position = vec4(4,4,0,1);
        pearlDepth = 0.0; pearlCrest = 0.0; return;
    }
    float longitude = 6.2831853 * float(column) / float(population);
    vec3 normal = vec3(sin(lat)*cos(longitude), cos(lat), sin(lat)*sin(longitude));
    // Smooth waves in spherical coordinates inherited from a continuous 3D field.
    // Every point keeps its neighbours; no seam at longitude zero or polar noise.
    float frequency = (10.0 + uMotion.w * 0.65)*uMesh.y;
    float wave = 0.52 * sin(dot(normal, vec3(1.0,0.7,0.4))*frequency-uTime)
               + 0.30 * sin(dot(normal, vec3(-0.3,1.0,0.8))*frequency*1.45+uTime*0.73)
               + 0.18 * sin(dot(normal, vec3(0.8,-0.4,1.0))*frequency*1.9-uTime*0.51);
    float swell = uMotion.x + uAmplitude * uMotion.y;
    float sound = voiceWave(normal,uVoice0) + voiceWave(normal,uVoice1)
                + voiceWave(normal,uVoice2) + voiceWave(normal,uVoice3);
    // Lift the resting surface and its voice response by the same proportion.
    float surfaceDisplacement = swell * wave + uAmplitude * 0.008
        + clamp(sound * 0.035,-0.045,0.045)*uMesh.w;
    float radius = 0.88 * (1.0 + 1.7 * surfaceDisplacement * uMesh.x);
    // A bounded tangential current bends the rows into liquid ribbons.
    vec3 current = vec3(normal.y*normal.z, -normal.x*normal.z, normal.x*normal.y);
    vec3 pos = radius * normalize(normal + current * sin(uTime*0.38) * 0.025);
    // Fixed elegant tilt; no random drift or loss of the formation.
    pos.yz = mat2(0.9563,-0.2924,0.2924,0.9563) * pos.yz;
    float depth = clamp(0.5 - pos.z / 1.9, 0.0, 1.0);
    vec2 projected = pos.xy * 1.95 / ((3.0 + pos.z) * 1.02);
    vec2 offset = projected - uHover.xy;
    float distance = length(offset);
    float front = smoothstep(0.30,0.68,depth);
    float influence = exp(-distance*distance*22.0) * uHover.z * front;
    // A local dimple and gentle circular ripples follow the finger-like cursor.
    float touch = influence * (0.018 + 0.013*sin(distance*42.0-uClock*3.8));
    pos *= 1.0 + touch;
    projected = pos.xy * 1.95 / ((3.0 + pos.z) * 1.02);
    projected -= offset * influence * 0.055;
    pearlDepth = depth;
    pearlCrest = clamp(0.5 + 0.5*wave + 0.28*abs(sound) + 0.20*influence,0.0,1.0);
    float reach = uMesh.z * max(0.85, uSize * 0.0027) * (0.72 + 0.28 * depth);
    gl_Position = vec4(projected + pearlUV * reach * 2.0 / uSize, 0, 1);
}
"""

_PEARL_FRAGMENT = """
#version 330 core
in vec2 pearlUV;
in float pearlDepth;
in float pearlCrest;
out vec4 frag;
uniform vec3 uMid;
uniform vec3 uHot;
uniform float uAmplitude;
// Integrate the light footprint over the pixel, rather than sampling only its
// centre. Subpixel pearls keep their energy while crossing pixel boundaries.
vec2 erfApprox(vec2 x) {
    return tanh(1.128379 * x + 0.102772 * x*x*x);
}
float pixelGaussian(vec2 p, vec2 footprint, float sigma) {
    vec2 lo = (p - footprint * 0.5) / (1.414214 * sigma);
    vec2 hi = (p + footprint * 0.5) / (1.414214 * sigma);
    vec2 integral = erfApprox(hi) - erfApprox(lo);
    return integral.x * integral.y * (1.5707963 * sigma*sigma)
        / (footprint.x * footprint.y);
}
void main() {
    vec2 footprint = max(fwidth(pearlUV), vec2(0.0001));
    float halo = pixelGaussian(pearlUV, footprint, 0.36);
    float heart = pixelGaussian(pearlUV, footprint, 0.24);
    float light = (heart * 1.40 + halo * 0.32)
        * (0.055 + 0.945 * smoothstep(0.25,0.70,pearlDepth))
        * (0.56 + 0.65 * pearlCrest + 0.22 * uAmplitude);
    vec3 tint = mix(uMid, uHot, 0.35 + 0.65 * heart);
    frag = vec4(tint * light, light);
}
"""

_RAYS = """
#version 330 core
in vec2 uv;
out vec4 frag;
uniform float uTime;
uniform float uTurbulence; // focus x
uniform float uFlow;       // focus y
uniform float uAmplitude;
uniform vec3 uMid;
void main() {
    vec2 p = uv - vec2(uTurbulence, 1.0-uFlow);
    float r = length(p);
    float a = atan(p.y,p.x);
    float t = uTime * 0.055;
    // Smooth angular lobes, with finer silk filaments inside each shaft.
    float shafts = pow(0.5+0.5*sin(a*9.0 + sin(a*3.0+t)*1.2-t), 18.0);
    float silk = pow(0.5+0.5*sin(a*37.0+sin(a*7.0-t)*2.0+t), 28.0);
    float mist = exp(-r*5.0) * 0.025;
    float light = (shafts*0.11 + silk*0.032)
        * smoothstep(0.055,0.20,r) * exp(-r*4.2) + mist;
    light *= 0.85 + 0.30*uAmplitude;
    frag = vec4(uMid*light, light);
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
        self._focus: QOpenGLShaderProgram | None = None
        self._blur: QOpenGLShaderProgram | None = None
        self._composite: QOpenGLShaderProgram | None = None
        self._scene: QOpenGLFramebufferObject | None = None
        self._blur_a: QOpenGLFramebufferObject | None = None
        self._blur_b: QOpenGLFramebufferObject | None = None
        self._final: QOpenGLFramebufferObject | None = None
        self._size = 0
        self._pearls: QOpenGLShaderProgram | None = None
        self._motion = (0.018, 0.0, 0.0, 2.0)
        self._phase = 0.0
        self._hover = (0.0, 0.0, 0.0)
        self._voice_waves: tuple[tuple[float, float], ...] = ()
        self._clock = 0.0
        self._options: OrbProfile | None = None
        self._mesh_color = None
        self._definition = 3.5
        self._interior = 1.0
        self._colour_boost = 1.0

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
        self._pearls = self._program(_PEARL_FRAGMENT, "pearls", _PEARL_VERTEX)
        self._focus = self._program(_CORE_FOCUS, "core focus")
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
    def _program(fragment: str, name: str, vertex: str = _VERTEX) -> QOpenGLShaderProgram:
        program = QOpenGLShaderProgram()
        if not program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, vertex):
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
        amplitude: float,
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

            self._pass_raymarch(functions, palette, seconds, turbulence, flow, amplitude)
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
        amplitude: float,
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
        program.setUniformValue1f("uAmplitude", float(amplitude))
        options = self._options or OrbProfile()
        program.setUniformValue1f("uInterior", self._interior)
        program.setUniformValue1f("uCoreSize", options.core_size)
        program.setUniformValue1f("uEnergy", options.energy)
        program.setUniformValue(
            "uEruption",
            QVector4D(
                options.eruption_size,
                options.eruption_rate,
                options.eruption_speed,
                options.eruption_energy,
            ),
        )
        program.setUniformValue("uDeep", _vector(palette.glow, 0.55))
        program.setUniformValue("uMid", _vector(palette.core, 1.0))
        program.setUniformValue(
            "uHot",
            _vector(palette.core, 1.0, whiten=options.white),
        )
        functions.glDrawArrays(_GL_TRIANGLES, 0, 3)
        program.release()
        scene.release()
        if self._definition > 0.0 and not isinstance(self, _ShaderRays):
            self._pass_focus(functions)
        assert self._scene is not None
        self._scene.bind()
        self._pass_pearls(functions, palette, amplitude)
        self._scene.release()

    def _pass_focus(self, functions) -> None:
        source, target, program = self._scene, self._final, self._focus
        assert source is not None and target is not None and program is not None
        target.bind()
        functions.glViewport(0, 0, self._size, self._size)
        program.bind()
        functions.glActiveTexture(_GL_TEXTURE0)
        functions.glBindTexture(_GL_TEXTURE_2D, source.texture())
        program.setUniformValue1i("uSource", 0)
        program.setUniformValue1f("uDefinition", self._definition)
        functions.glDrawArrays(_GL_TRIANGLES, 0, 3)
        program.release()
        target.release()
        # Reuse the two full-size buffers; the pearl mesh is added after focus.
        self._scene, self._final = target, source

    def _pass_pearls(self, functions, palette: StatePalette, amplitude: float) -> None:
        program = self._pearls
        assert program is not None
        functions.glEnable(_GL_BLEND)
        functions.glBlendFunc(1, 1)  # Add emitted light, including the far hemisphere.
        program.bind()
        program.setUniformValue1f("uTime", self._phase)
        program.setUniformValue1f("uSize", float(self._size))
        program.setUniformValue1f("uAmplitude", float(amplitude))
        program.setUniformValue("uMotion", QVector4D(*self._motion))
        program.setUniformValue("uHover", QVector3D(*self._hover))
        program.setUniformValue1f("uClock", float(self._clock))
        for index in range(4):
            pulse = self._voice_waves[index] if index < len(self._voice_waves) else (0.0, 0.0)
            program.setUniformValue(f"uVoice{index}", QVector2D(*pulse))
        options = self._options or OrbProfile()
        program.setUniformValue(
            "uMesh",
            QVector4D(
                options.mesh_amplitude,
                options.mesh_frequency,
                options.bead_size,
                options.voice_waves,
            ),
        )
        tint = self._mesh_color or palette.core
        program.setUniformValue("uMid", _vector(tint, options.mesh_light))
        program.setUniformValue(
            "uHot",
            _vector(tint, options.mesh_light, whiten=options.mesh_white),
        )
        functions.glDrawArrays(_GL_TRIANGLES, 0, 112 * 224 * 6)
        program.release()
        functions.glDisable(_GL_BLEND)

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
        program.setUniformValue1f("uBloomGain", self._options.bloom if self._options else 0.42)
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


class _ShaderRays(_ShaderCore):
    def _create(self) -> None:
        super()._create()
        assert self._context is not None and self._surface is not None
        self._context.makeCurrent(self._surface)
        self._raymarch = self._program(_RAYS, "rays")
        self._context.doneCurrent()

    def _pass_pearls(self, functions, palette: StatePalette, amplitude: float) -> None:
        pass


_CORE = _ShaderCore()
_RAY_RENDERER = _ShaderRays()


def render_rays(palette: StatePalette, seconds: float, focus: tuple[float, float],
                amplitude: float) -> QImage | None:
    """Soft shafts at a fixed low resolution, independent of the orb framebuffer."""
    return _RAY_RENDERER.render(384, palette, seconds, focus[0], focus[1], amplitude)


def render_orb(
    size: int,
    palette: StatePalette,
    seconds: float,
    turbulence: float,
    flow: float,
    amplitude: float,
    motion: tuple[float, float, float, float] = (0.018, 0.0, 0.0, 2.0),
    phase: float = 0.0,
    hover: tuple[float, float, float] = (0.0, 0.0, 0.0),
    voice_waves: tuple[tuple[float, float], ...] = (),
    colour_boost: bool = True,
    options: OrbProfile | None = None,
) -> QImage | None:
    """Render one whole orb — core and mote shell — or ``None`` without a GPU."""

    active = options or OrbProfile(white=0.54 if colour_boost else 0.62)
    _CORE._options = active
    _CORE._mesh_color = (
        QColor(active.mesh_color) if active.mesh_color else palette.core
    )
    _CORE._definition = active.focus
    _CORE._interior = active.interior
    palette = replace(
        palette,
        core=QColor(active.core_color) if active.core_color else palette.core,
        glow=QColor(active.shadow_color) if active.shadow_color else palette.glow,
    )
    _CORE._motion = motion
    _CORE._phase = phase
    _CORE._hover = hover
    _CORE._voice_waves = voice_waves
    _CORE._clock = seconds
    _CORE._colour_boost = 1.0 if colour_boost else 0.0
    return _CORE.render(size, palette, seconds, turbulence, flow, amplitude)
