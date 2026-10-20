import { Fragment, lazy, Suspense } from "react";

const RequirementMath = lazy(() => import("./RequirementMath"));

/** Display-only math; source text and exports are never rewritten. */
export default function RequirementText({ text = "" }) {
  const parts = String(text).split(/(\$\$[\s\S]+?\$\$|\$[^$\n]+\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\])/g);
  return parts.map((part, index) => {
    const math = part.startsWith("$") || part.startsWith("\\(") || part.startsWith("\\[");
    if (!math) return <Fragment key={index}>{part}</Fragment>;
    return <Suspense key={index} fallback={<span>{part}</span>}><RequirementMath source={part} block={part.startsWith("$$") || part.startsWith("\\[")} /></Suspense>;
  });
}
