/**
 * Blinking | cursor shown while isStreaming === true.
 * Uses step-end easing for hard on/off (natural cursor feel).
 * NOT animate-pulse (which fades to 0.5 opacity — Pitfall 6 in RESEARCH.md).
 * The @keyframes blink rule is defined in src/index.css.
 */
export function StreamingCursor() {
  return (
    <span
      className="text-zinc-950 font-normal select-none"
      style={{ animation: "blink 1s step-end infinite" }}
      aria-hidden="true"
    >
      |
    </span>
  );
}
