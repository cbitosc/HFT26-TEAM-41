import type { CSSProperties } from "react";
import { ENGRAVINGS, type EngravingName } from "@/lib/olympus/engravings";

type Props = {
  name: EngravingName;
  className?: string;
  style?: CSSProperties;
  /** Accessible name; omit for decorative art (hidden from assistive tech). */
  label?: string;
  /** Gold light sweeps across on hover of the nearest .engr-host. */
  sheen?: boolean;
  /** Fade the edges out, so a cut-out that was cropped flat never shows a hard edge. */
  fade?: boolean;
};

const FADE = "radial-gradient(closest-side, #000 62%, transparent 100%)";

/** An engraving from the theme sheets, filled with currentColor (or --engr) through a CSS mask. */
export default function Engraving({ name, className = "", style, label, sheen, fade }: Props) {
  const [w, h] = ENGRAVINGS[name];
  const url = `url(/engravings/${name}.webp)`;
  const mask = fade ? `${url}, ${FADE}` : url;
  return (
    <span
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={`engr ${sheen ? "engr-sheen" : ""} ${className}`}
      style={{
        aspectRatio: `${w} / ${h}`,
        WebkitMaskImage: mask,
        maskImage: mask,
        ...(fade ? { WebkitMaskComposite: "source-in", maskComposite: "intersect" } : {}),
        ...style,
      }}
    />
  );
}
