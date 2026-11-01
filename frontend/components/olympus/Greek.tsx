import type { CSSProperties } from "react";
import { GREEK, type GreekName } from "@/lib/olympus/greek";

type Props = {
  name: GreekName;
  /** Line work only, printed in currentColor through a CSS mask (for scenes on the night page). */
  ink?: boolean;
  className?: string;
  style?: CSSProperties;
  /** Accessible name; omit for decorative art. */
  alt?: string;
  eager?: boolean;
};

/**
 * An engraving from public/greek. Never rendered wider than its file (maxWidth), so the
 * line work stays sharp; the porcelain cut-out reads as a lit statue on the night stage.
 */
export default function Greek({ name, ink = false, className = "", style, alt = "", eager = false }: Props) {
  const [w, h] = GREEK[name];
  const base: CSSProperties = { aspectRatio: `${w} / ${h}`, maxWidth: w, ...style };
  if (ink) {
    const url = `url(/greek/${name}-ink.webp)`;
    return (
      <span
        role={alt ? "img" : undefined}
        aria-label={alt || undefined}
        aria-hidden={alt ? undefined : true}
        className={`greek greek-ink ${className}`}
        style={{ ...base, WebkitMaskImage: url, maskImage: url }}
      />
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/greek/${name}.webp`}
      width={w}
      height={h}
      alt={alt}
      aria-hidden={alt ? undefined : true}
      loading={eager ? "eager" : "lazy"}
      decoding="async"
      draggable={false}
      className={`greek ${className}`}
      style={base}
    />
  );
}
