// src/utils/md.ts
import MarkdownIt from "markdown-it";
import DOMPurify from "dompurify";

const md = new MarkdownIt({
  linkify: true, // autolinks
  breaks: true, // saltos de línea = <br>
});

export function renderMarkdown(src: string) {
  return DOMPurify.sanitize(md.render(src ?? ""));
}
