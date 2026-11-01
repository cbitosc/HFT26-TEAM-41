"use client";
// The Oracle's orb: a WebGL fragment shader on one quad. A glass sphere (fake 3D normal →
// diffuse, specular, fresnel rim) holds domain-warped fbm "liquid" in lapis, cobalt and
// gold; the edge wobbles with live audio level, and each state shifts colour and motion:
//   idle — slow breathing · listening — aqua, swells with the mic · thinking — violet
//   swirl, contracts · speaking — pearl core pulses, ripples leave the surface.
// Noise: 3D simplex by Ashima Arts / Stefan Gustavson (MIT), see ATTRIBUTIONS.md.
import { useEffect, useRef, type RefObject } from "react";

export type OrbState = "idle" | "listening" | "thinking" | "speaking";
const STATE_INDEX: Record<OrbState, number> = { idle: 0, listening: 1, thinking: 2, speaking: 3 };

const VERT = `attribute vec2 aPos; void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }`;

const FRAG = `precision highp float;
uniform vec2 uRes; uniform float uTime; uniform float uLevel; uniform vec4 uMix;
vec3 mod289(vec3 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 mod289(vec4 x){return x-floor(x*(1.0/289.0))*289.0;}
vec4 permute(vec4 x){return mod289(((x*34.0)+1.0)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-0.85373472095314*r;}
float snoise(vec3 v){
  const vec2 C=vec2(1.0/6.0,1.0/3.0); const vec4 D=vec4(0.0,0.5,1.0,2.0);
  vec3 i=floor(v+dot(v,C.yyy)); vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz); vec3 l=1.0-g; vec3 i1=min(g.xyz,l.zxy); vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx; vec3 x2=x0-i2+C.yyy; vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(i.z+vec4(0.0,i1.z,i2.z,1.0))+i.y+vec4(0.0,i1.y,i2.y,1.0))+i.x+vec4(0.0,i1.x,i2.x,1.0));
  float n_=0.142857142857; vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.0*floor(p*ns.z*ns.z);
  vec4 x_=floor(j*ns.z); vec4 y_=floor(j-7.0*x_);
  vec4 x=x_*ns.x+ns.yyyy; vec4 y=y_*ns.x+ns.yyyy; vec4 h=1.0-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy); vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.0+1.0; vec4 s1=floor(b1)*2.0+1.0; vec4 sh=-step(h,vec4(0.0));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy; vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x); vec3 p1=vec3(a0.zw,h.y); vec3 p2=vec3(a1.xy,h.z); vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x; p1*=norm.y; p2*=norm.z; p3*=norm.w;
  vec4 m=max(0.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.0); m=m*m;
  return 42.0*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
float fbm(vec3 p){ float f=0.0; float a=0.55; for(int i=0;i<3;i++){ f+=a*snoise(p); p*=1.9; a*=0.45; } return f; }

void main(){
  vec2 uv = (gl_FragCoord.xy - 0.5*uRes) / min(uRes.x, uRes.y);
  vec2 p = uv * 2.6;
  float t = uTime; float lv = uLevel;
  float r = length(p); float a = atan(p.y, p.x);
  vec2 ca = vec2(cos(a), sin(a));

  float wob = snoise(vec3(ca*0.9, t*0.3)) * (0.016 + lv*0.05 + uMix.z*0.012)
            + sin(a*2.0 + t*1.1) * 0.008 * (1.0 + uMix.w*1.5)
            + snoise(vec3(ca*1.8, t*0.8)) * lv * 0.018;
  float R = 0.8 + wob + lv*0.05 + uMix.y*0.02 - uMix.z*0.05 + 0.014*sin(t*0.9);
  float d = r / R;
  float px = 2.6 / min(uRes.x, uRes.y);
  float inside = 1.0 - smoothstep(1.0 - 1.6*px/R, 1.0, d);

  vec3 lapis = vec3(0.03,0.06,0.28); vec3 cobalt = vec3(0.12,0.24,0.86); vec3 sky = vec3(0.36,0.72,1.0);
  vec3 pearl = vec3(0.97,0.95,0.89); vec3 gold = vec3(0.98,0.76,0.40); vec3 violet = vec3(0.52,0.34,0.98);
  vec3 aqua = vec3(0.32,0.95,0.86);
  vec3 col = vec3(0.0);

  if (d < 1.0) {
    vec3 n = vec3(p/R, sqrt(max(0.0, 1.0 - d*d)));
    vec2 q = (p/R) / (0.55 + 0.45*n.z);
    float speed = 0.22 + uMix.y*0.12 + uMix.z*0.55 + uMix.w*0.22;
    float tt = t * speed;
    vec2 w = q * 0.95;
    vec2 warp = vec2(fbm(vec3(w + vec2(1.7, 9.2), tt)), fbm(vec3(w + vec2(8.3, 2.8), tt*1.1)));
    float f = fbm(vec3(w + 1.25*warp, tt*0.8)) * 0.5 + 0.5;
    float g = fbm(vec3(w*2.0 - warp, tt*1.3 + 4.0)) * 0.5 + 0.5;
    vec3 c = mix(lapis, cobalt, smoothstep(0.22, 0.6, f));
    vec3 hi = mix(sky, aqua, uMix.y);
    hi = mix(hi, violet, uMix.z);
    c = mix(c, hi, smoothstep(0.52, 0.86, f) * (0.8 + lv*0.4));
    c += gold * pow(smoothstep(0.6, 0.95, g), 2.0) * (0.3 + uMix.w*0.5 + uMix.z*0.35);
    float core = exp(-dot(q, q) * 3.0);
    c += pearl * core * (0.07 + lv*0.6*(uMix.w + uMix.y*0.6));
    vec3 L = normalize(vec3(-0.45, 0.55, 0.9));
    c *= 0.55 + 0.45*max(dot(n, L), 0.0);
    c += pearl * pow(max(dot(reflect(-L, n), vec3(0.0, 0.0, 1.0)), 0.0), 28.0) * 0.55;
    vec3 rim = mix(sky, gold, 0.5 + 0.5*sin(a*2.0 + t*0.6));
    rim = mix(rim, violet, uMix.z*0.7);
    rim = mix(rim, aqua, uMix.y*0.5);
    c += rim * pow(1.0 - n.z, 2.2) * 0.85;
    col = c;
  }

  float od = max(r - R, 0.0);
  vec3 gc = mix(cobalt, sky, 0.5 + 0.5*sin(a*2.0 - t*0.7));
  gc = mix(gc, aqua, uMix.y*0.6); gc = mix(gc, violet, uMix.z*0.6); gc = mix(gc, gold, uMix.w*0.25);
  float glow = exp(-od*6.0) * (0.32 + lv*0.9) * (1.0 - inside);
  float rip = 0.0;
  for (int k = 0; k < 3; k++) {
    float ph = fract(t*0.45 + float(k)/3.0);
    rip += exp(-pow((r - (R + ph*0.9)) * 22.0, 2.0)) * (1.0 - ph) * 0.5;
  }
  rip *= (uMix.w*(0.35 + lv) + uMix.y*lv*0.8) * (1.0 - inside);
  float fade = 1.0 - smoothstep(0.92, 1.28, r); // never reach the canvas edge
  glow *= fade; rip *= fade;
  vec3 outer = gc*glow + mix(sky, gold, 0.4)*rip;
  float oa = clamp(glow*0.9 + rip, 0.0, 1.0);
  gl_FragColor = vec4(col*inside + outer*(1.0 - inside), inside + oa*(1.0 - inside));
}`;

function compile(gl: WebGLRenderingContext, type: number, src: string) {
  const s = gl.createShader(type)!;
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) ?? "shader error");
  return s;
}

export default function OracleOrb({ state, level, className = "" }: { state: OrbState; level: RefObject<number>; className?: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const fallback = useRef<HTMLDivElement>(null);
  const target = useRef(STATE_INDEX[state]);

  useEffect(() => {
    target.current = STATE_INDEX[state];
  }, [state]);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const gl = el.getContext("webgl", { premultipliedAlpha: true, antialias: false, alpha: true });
    if (!gl) {
      el.style.display = "none";
      fallback.current?.style.removeProperty("display");
      return;
    }
    let prog: WebGLProgram;
    try {
      prog = gl.createProgram()!;
      gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VERT));
      gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FRAG));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog) ?? "link error");
    } catch (err) {
      console.error("[orb]", err);
      el.style.display = "none";
      fallback.current?.style.removeProperty("display");
      return;
    }
    gl.useProgram(prog);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "aPos");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const uRes = gl.getUniformLocation(prog, "uRes");
    const uTime = gl.getUniformLocation(prog, "uTime");
    const uLevel = gl.getUniformLocation(prog, "uLevel");
    const uMix = gl.getUniformLocation(prog, "uMix");

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      const { width, height } = el.getBoundingClientRect();
      el.width = Math.max(1, Math.round(width * dpr));
      el.height = Math.max(1, Math.round(height * dpr));
      gl.viewport(0, 0, el.width, el.height);
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(el);

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const mix = [1, 0, 0, 0];
    let lv = 0;
    let t = 0;
    let last = performance.now();
    let raf = 0;
    const frame = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      t += dt * (reduced ? 0.3 : 1);
      const k = 1 - Math.exp(-dt * 4);
      for (let i = 0; i < 4; i++) mix[i] += ((i === target.current ? 1 : 0) - mix[i]) * k;
      const want = Math.max(0, Math.min(1, level.current ?? 0));
      lv += (want - lv) * (1 - Math.exp(-dt * (want > lv ? 18 : 6)));
      gl.uniform2f(uRes, el.width, el.height);
      gl.uniform1f(uTime, t);
      gl.uniform1f(uLevel, lv);
      gl.uniform4f(uMix, mix[0], mix[1], mix[2], mix[3]);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      // Free resources but keep the context: StrictMode re-runs this effect on the same canvas,
      // and a lost context would hand the second run a dead GL.
      gl.deleteBuffer(buf);
      gl.deleteProgram(prog);
    };
  }, [level]);

  return (
    <div className={`relative ${className}`}>
      <canvas ref={canvas} className="absolute inset-0 h-full w-full" aria-hidden="true" />
      <div
        ref={fallback}
        style={{ display: "none" }}
        className="absolute inset-[18%] rounded-full bg-[radial-gradient(circle_at_35%_30%,#f6f1e2,#5b8cff_30%,#1e3ad6_60%,#0a1238)] shadow-[0_0_120px_30px_rgba(60,110,255,0.35)]"
        aria-hidden="true"
      />
    </div>
  );
}
