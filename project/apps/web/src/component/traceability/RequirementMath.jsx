import katex from "katex";
import "katex/dist/katex.min.css";

export default function RequirementMath({ source, block }) {
  const size = block || source.startsWith("\\") ? 2 : 1;
  let html;
  try {
    html = katex.renderToString(source.slice(size, -size), {
      displayMode: block, throwOnError: true, trust: false, maxExpand: 1000, maxSize: 20,
    });
  } catch {
    return source;
  }
  return <span className={block ? "block max-w-full overflow-x-auto" : "inline-block max-w-full align-middle"} dangerouslySetInnerHTML={{ __html: html }} />;
}
