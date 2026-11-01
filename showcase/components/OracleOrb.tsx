"use client";

import { useEffect, useRef } from "react";

// The oracle: one WebGL fragment shader. A porcelain sphere of domain-warped marble,
// shaded with engraving hatch lines like the rest of the page, inside a corona of
// hair-thin Helios rays whose length follows the audio level. Thinking shows an orbit
// with three dots; every spoken word sends a ripple out. Draws only while on screen;
// reduced motion draws one frame per state change. No WebGL: a CSS gradient stands in.

export type OrbState = "idle" | "listening" | "thinking" | "speaking";
/** Shared, mutable signal the page writes and the orb reads every frame. */
export type OrbSignal = { level: number; pulses: number };

type P = { amp: number; speed: number; scale: number; glow: number; rays: number; warm: number; think: number; tint: number };

function target(state: OrbState, level: number): P {
  switch (state) {
    case "listening":
      return { amp: 0.035 + level * 0.09, speed: 0.8 + level * 1.1, scale: 0.94 + level * 0.08, glow: 0.4 + level * 0.6, rays: 0.25 + level * 0.9, warm: 0, think: 0, tint: 1 };
    case "speaking":
      return { amp: 0.045 + level * 0.07, speed: 1.05, scale: 0.98 + level * 0.06, glow: 0.5 + level * 0.5, rays: 0.35 + level * 0.8, warm: 1, think: 0, tint: 1 };
    case "thinking":
      return { amp: 0.02, speed: 1.9, scale: 0.86, glow: 0.22, rays: 0.06, warm: 0.3, think: 1, tint: 0.55 };
    default:
      return { amp: 0.025, speed: 0.35, scale: 0.9, glow: 0.22, rays: 0.12, warm: 0.45, think: 0, tint: 0.85 };
  }
}

const VERT = `attribute vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }`;

const FRAG = `
precision highp float;
uniform vec2 uRes;
uniform float uTime, uLevel, uAmp, uScale, uGlow, uRays, uWarm, uThink, uTint, uPaper, uSpin;
uniform vec4 uRip;

float hash(vec3 p) { p = fract(p * 0.3183099 + 0.1); p *= 17.0; return fract(p.x * p.y * p.z * (p.x + p.y + p.z)); }
float noise(vec3 x) {
  vec3 i = floor(x); vec3 f = fract(x); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x), mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
             mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x), mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y), f.z);
}
float fbm(vec3 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * noise(p); p = p * 2.03 + vec3(1.7, 9.2, 3.1); a *= 0.5; } return s; }
float hair(float dPx) { return 1.0 - smoothstep(0.35, 1.25, dPx); }

void main() {
  float m = min(uRes.x, uRes.y);
  vec2 p = (gl_FragCoord.xy - 0.5 * uRes) / (0.5 * m);
  float px = 2.0 / m;
  float r = length(p);
  vec2 dir = p / max(r, 1e-4);
  float a = atan(p.y, p.x);
  float t = uTime;

  float R = 0.5 * uScale;
  float wob = (noise(vec3(dir * 1.3, t * 0.6)) - 0.5) + (noise(vec3(dir * 3.1, t * 1.3 + 4.0)) - 0.5) * 0.5;
  float rr = R * (1.0 + uAmp * wob * 2.0);

  vec3 cream = vec3(0.97, 0.94, 0.86);
  vec3 gold = vec3(1.0, 0.80, 0.46);
  vec3 lineCol = mix(mix(vec3(0.66, 0.75, 1.0), gold, uWarm), mix(vec3(0.11, 0.18, 0.56), vec3(0.55, 0.40, 0.12), uWarm), uPaper);

  // Corona: 180 hair-thin rays, every fourth one long, lengths breathing with the level.
  float N = 180.0;
  float u = (a / 6.2831853 + 0.5) * N + uSpin * 0.4;
  float cell = floor(u);
  float dRay = abs(fract(u) - 0.5) * (6.2831853 * r / N) / px;
  float n = noise(vec3(cell * 0.21, t * 0.9, 1.0));
  float isLong = mod(cell, 4.0) < 0.5 ? 1.0 : 0.5;
  float L = rr + 0.035 + (0.05 + 0.34 * uRays * n) * isLong * (0.65 + 0.35 * hash(vec3(cell, 2.0, 3.0)));
  float along = clamp((r - rr) / max(L - rr, 1e-3), 0.0, 1.0);
  float ray = hair(dRay) * smoothstep(rr + 0.012, rr + 0.035, r) * (1.0 - smoothstep(L - 0.04, L, r)) * mix(0.9, 0.25, along);

  // Orbit ring with ticks; thinking brightens it and sends three dots round.
  float ringR = R * 1.42;
  float ring = hair(abs(r - ringR) / px) * (0.22 + 0.4 * uThink);
  float tu = (a / 6.2831853 + 0.5) * 72.0 - uSpin;
  float tick = hair(abs(fract(tu) - 0.5) * (6.2831853 * r / 72.0) / px) * step(abs(r - ringR - 0.012), 0.012) * (0.25 + 0.3 * uThink);
  float dots = 0.0;
  for (int k = 0; k < 3; k++) {
    float an = t * 1.7 + float(k) * 2.0944;
    float d = length(p - ringR * vec2(cos(an), sin(an)));
    dots += 1.0 - smoothstep(0.014, 0.014 + px * 1.5, d);
  }
  dots *= uThink;

  // Ripples, one per spoken word or loud syllable.
  float rip = 0.0;
  for (int k = 0; k < 4; k++) {
    float age = uRip[k];
    if (age >= 0.0 && age < 1.0) rip += hair(abs(r - (rr + 0.02 + age * 0.42)) / px * 0.7) * (1.0 - age) * 0.8;
  }

  float halo = exp(-max(r - rr, 0.0) * 6.5) * (0.12 + 0.5 * uGlow) * (1.0 - uPaper * 0.6);
  vec3 haloCol = mix(mix(vec3(0.3, 0.45, 1.0), gold, uWarm * 0.7), vec3(0.2, 0.3, 0.8), uPaper);
  float lineA = clamp(ray + ring + tick + dots + rip, 0.0, 1.0);
  vec3 outRgb = lineCol * lineA + haloCol * halo;
  float outA = clamp(lineA + halo, 0.0, 1.0);

  // The sphere.
  float inside = 1.0 - smoothstep(rr - px, rr + px, r);
  vec2 q = p / rr;
  float z = sqrt(max(0.0, 1.0 - dot(q, q)));
  vec3 nrm = vec3(q, z);
  vec3 sp = nrm * 1.7;
  float ca = cos(t * 0.12), sa = sin(t * 0.12);
  sp.xz = mat2(ca, -sa, sa, ca) * sp.xz;
  float w = fbm(sp + vec3(0.0, 0.0, t * 0.15));
  float f = fbm(sp * 1.4 + w * 2.2 + vec3(t * 0.05, -t * 0.08, 0.0));
  // Two families of fine veins, like Carrara marble rather than a map.
  float vein = pow(1.0 - abs(sin((w * 3.0 + f * 1.2 + nrm.y * 0.8) * 3.14159)), 10.0);
  vein += 0.4 * pow(1.0 - abs(sin((w * 5.0 - f * 0.8 + nrm.x * 1.5) * 3.14159)), 18.0);

  vec3 deep = vec3(0.035, 0.06, 0.28), mid = vec3(0.14, 0.26, 0.78), hi = vec3(0.56, 0.67, 1.0);
  vec3 c = mix(deep, mid, smoothstep(0.25, 0.75, f));
  c = mix(c, hi, smoothstep(0.6, 0.95, f) * 0.6);
  c = mix(c, mix(cream, gold, uWarm * 0.55), vein * (0.5 + 0.5 * uGlow));
  float g = dot(c, vec3(0.3, 0.59, 0.11));
  c = mix(vec3(g), c, uTint);

  vec3 Ld = normalize(vec3(-0.45, 0.55, 0.7));
  float diff = clamp(dot(nrm, Ld), 0.0, 1.0);
  float shade = 0.4 + 0.75 * diff;
  c *= shade;
  // Engraving: latitude hatch lines, thicker where the sphere is darker.
  float lat = (asin(clamp(nrm.y * 0.98 + (f - 0.5) * 0.05, -1.0, 1.0)) * rr) / (3.2 * px);
  float hd = abs(fract(lat) - 0.5) * 2.0;
  float hatch = 1.0 - smoothstep((1.0 - shade) * 0.9, (1.0 - shade) * 0.9 + 0.25, hd);
  c = mix(c, c * 0.45, hatch * 0.6 * smoothstep(0.15, 0.6, z));
  c += cream * pow(clamp(dot(reflect(-Ld, nrm), vec3(0.0, 0.0, 1.0)), 0.0, 1.0), 22.0) * 0.5;
  c += mix(vec3(0.5, 0.62, 1.0), gold, uWarm) * pow(1.0 - z, 2.2) * (0.35 + 0.9 * uGlow);
  c += mid * uLevel * 0.22;

  gl_FragColor = vec4(c * inside + outRgb * (1.0 - inside), inside + outA * (1.0 - inside));
}`;

export default function OracleOrb({
  state,
  signal,
  tone = "night",
  className,
}: {
  state: OrbState;
  signal: OrbSignal;
  tone?: "night" | "paper";
  className?: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    const c = canvas.current!;
    const gl = c.getContext("webgl", { premultipliedAlpha: true, alpha: true, antialias: false });
    if (!gl) {
      c.classList.add("orb-fallback");
      return;
    }
    const sh = (type: number, src: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) console.error(gl.getShaderInfoLog(s));
      return s;
    };
    const prog = gl.createProgram()!;
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "a");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const U = Object.fromEntries(
      ["uRes", "uTime", "uLevel", "uAmp", "uScale", "uGlow", "uRays", "uWarm", "uThink", "uTint", "uPaper", "uSpin", "uRip"].map(
        (k) => [k, gl.getUniformLocation(prog, k)],
      ),
    );

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const p: P = { ...target("idle", 0) };
    let level = 0;
    const ripples: number[] = [];
    let seenPulses = signal.pulses;
    let raf = 0;
    let visible = true;
    let last = performance.now();
    let t = 7;
    let spin = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      c.width = Math.round(c.clientWidth * dpr);
      c.height = Math.round(c.clientHeight * dpr);
      gl.viewport(0, 0, c.width, c.height);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(c);

    const draw = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      level += (signal.level - level) * (reduce ? 1 : 1 - Math.pow(0.0005, dt));
      const goal = target(stateRef.current, level);
      const k = reduce ? 1 : 1 - Math.pow(0.004, dt);
      for (const key of Object.keys(p) as (keyof P)[]) p[key] += (goal[key] - p[key]) * k;
      t += dt * p.speed;
      spin += dt * (0.6 + p.think * 2.5);

      if (signal.pulses !== seenPulses) {
        seenPulses = signal.pulses;
        if (!reduce) ripples.push(now);
        if (ripples.length > 4) ripples.shift();
      }
      const ages = [0, 1, 2, 3].map((i) => (ripples[i] === undefined ? -1 : (now - ripples[i]) / 1500));

      gl.uniform2f(U.uRes, c.width, c.height);
      gl.uniform1f(U.uTime, t);
      gl.uniform1f(U.uLevel, level);
      gl.uniform1f(U.uAmp, p.amp);
      gl.uniform1f(U.uScale, p.scale);
      gl.uniform1f(U.uGlow, p.glow);
      gl.uniform1f(U.uRays, p.rays);
      gl.uniform1f(U.uWarm, p.warm);
      gl.uniform1f(U.uThink, p.think);
      gl.uniform1f(U.uTint, p.tint);
      gl.uniform1f(U.uPaper, tone === "paper" ? 1 : 0);
      gl.uniform1f(U.uSpin, spin);
      gl.uniform4f(U.uRip, ages[0], ages[1], ages[2], ages[3]);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 3);

      if (visible && !reduce) raf = requestAnimationFrame(draw);
    };

    const io = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      cancelAnimationFrame(raf);
      if (visible) {
        last = performance.now();
        raf = requestAnimationFrame(draw);
      }
    });
    io.observe(c);
    raf = requestAnimationFrame(draw);
    const redraw = () => requestAnimationFrame(draw);
    c.addEventListener("redraw", redraw);
    return () => {
      c.removeEventListener("redraw", redraw);
      io.disconnect();
      ro.disconnect();
      cancelAnimationFrame(raf);
      // Free our objects but keep the context: a canvas hands the same context back on
      // the next getContext, so losing it here would leave a re-run with a dead one.
      gl.deleteBuffer(buf);
      gl.deleteProgram(prog);
    };
  }, [signal, tone]);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      canvas.current?.dispatchEvent(new Event("redraw"));
    }
  }, [state]);

  return <canvas ref={canvas} className={className} aria-hidden />;
}
