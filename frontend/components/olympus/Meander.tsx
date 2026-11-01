import { useId } from "react";

/** A Greek key (meander) band drawn as a repeating SVG pattern; inherits currentColor. */
export default function Meander({ className = "", height = 18 }: { className?: string; height?: number }) {
  const id = useId().replace(/:/g, "");
  const unit = height * 1.2;
  const s = height / 18;
  return (
    <svg className={`meander ${className}`} style={{ height }} aria-hidden="true">
      <defs>
        <pattern id={`mk${id}`} width={unit} height={height} patternUnits="userSpaceOnUse">
          <path
            d={`M0 ${17 * s} H${18 * s} V${1 * s} H${4 * s} V${13 * s} H${14 * s} V${5 * s} H${8 * s} V${9 * s}`}
            fill="none"
            stroke="currentColor"
            strokeWidth={1.4}
          />
          <path d={`M${18 * s} ${17 * s} H${unit}`} stroke="currentColor" strokeWidth={1.4} />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#mk${id})`} />
    </svg>
  );
}
