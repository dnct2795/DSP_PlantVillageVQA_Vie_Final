import katex from "katex";
import "katex/dist/katex.min.css";

/** Authored formulas only; model answers are always rendered as plain text. */
export function MathFormula({
  tex,
  label,
  inline = false,
}: {
  tex: string;
  label: string;
  inline?: boolean;
}) {
  const markup = katex.renderToString(tex, {
    displayMode: !inline,
    output: "htmlAndMathml",
    throwOnError: true,
    strict: "error",
    trust: false,
  });
  return (
    <span
      className={inline ? "math-inline" : "math-display"}
      role="math"
      aria-label={label}
      dangerouslySetInnerHTML={{ __html: markup }}
    />
  );
}
