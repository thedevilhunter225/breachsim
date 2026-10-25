import { CircleAlert, Info, Lightbulb, TriangleAlert } from "lucide-react";
import { Fragment, type ReactNode } from "react";

/**
 * Minimal, safe Markdown support for the legal templates in `content/legal`.
 *
 * Only the subset those documents use is understood: flat `key: value` frontmatter,
 * headings, paragraphs, bullet and numbered lists, block quotes (with GitHub-style
 * `[!NOTE]`/`[!WARNING]` callout markers), horizontal rules, pipe tables, bold text,
 * inline code, links and bracketed placeholders such as `[Company legal name]`.
 *
 * Everything is turned into React elements. Raw HTML in a document is shown as text and
 * never interpreted, and links are limited to http(s), mailto and same-site relative paths.
 */

export type LegalStatus = "draft" | "approved";

export type LegalMeta = {
  title: string;
  status: LegalStatus;
  lastReviewed: string | null;
  summary: string | null;
  audience: string | null;
};

export type InlineNode =
  | { type: "text"; value: string }
  | { type: "strong"; children: InlineNode[] }
  | { type: "code"; value: string }
  | { type: "link"; href: string; external: boolean; children: InlineNode[] }
  | { type: "placeholder"; value: string };

export type CalloutKind = "note" | "tip" | "important" | "warning" | "caution";

export type BlockNode =
  | { type: "heading"; level: 2 | 3 | 4; id: string; text: string; children: InlineNode[] }
  | { type: "paragraph"; children: InlineNode[] }
  | { type: "list"; ordered: boolean; start: number; items: InlineNode[][] }
  | { type: "quote"; callout: CalloutKind | null; children: BlockNode[] }
  | { type: "rule" }
  | { type: "table"; header: InlineNode[][]; rows: InlineNode[][][] };

export type ParsedLegalDocument = { meta: LegalMeta; blocks: BlockNode[] };

export type HeadingLink = { id: string; text: string };

// ---------------------------------------------------------------------------------------
// Frontmatter
// ---------------------------------------------------------------------------------------

const FRONTMATTER_FENCE = /^---[ \t]*$/;
const FRONTMATTER_ENTRY = /^([A-Za-z][\w-]*)[ \t]*:[ \t]*(.*)$/;

export function normalizeNewlines(source: string): string {
  return source.replace(/^﻿/, "").replace(/\r\n?/g, "\n");
}

function unquote(value: string): string {
  const first = value[0];
  if (value.length >= 2 && (first === '"' || first === "'") && value.endsWith(first)) {
    return value.slice(1, -1);
  }
  return value;
}

/**
 * Split a leading `---` fenced block of flat `key: value` pairs from the document body.
 * Keys are lower-cased with hyphens folded to underscores (`last-reviewed` and
 * `last_reviewed` are the same key). Comments, blank lines and nested YAML are ignored.
 */
export function parseFrontmatter(source: string): { data: Record<string, string>; body: string } {
  const text = normalizeNewlines(source);
  const lines = text.split("\n");
  if (!FRONTMATTER_FENCE.test(lines[0])) return { data: {}, body: text };
  const end = lines.findIndex((line, index) => index > 0 && FRONTMATTER_FENCE.test(line));
  if (end === -1) return { data: {}, body: text };

  const data: Record<string, string> = {};
  for (const line of lines.slice(1, end)) {
    const entry = FRONTMATTER_ENTRY.exec(line);
    if (entry) data[entry[1].toLowerCase().replace(/-/g, "_")] = unquote(entry[2].trim());
  }
  return { data, body: lines.slice(end + 1).join("\n") };
}

/** Only an explicit approval counts, so a missing or mistyped status still shows the draft banner. */
export function normalizeStatus(value: string | undefined): LegalStatus {
  return value?.trim().toLowerCase() === "approved" ? "approved" : "draft";
}

export function parseLegalDocument(source: string, fallbackTitle = "Untitled document"): ParsedLegalDocument {
  const { data, body } = parseFrontmatter(source);
  const optional = (value: string | undefined) => value?.trim() || null;
  return {
    meta: {
      title: optional(data.title) ?? fallbackTitle,
      status: normalizeStatus(data.status),
      lastReviewed: optional(data.last_reviewed),
      summary: optional(data.summary),
      audience: optional(data.audience),
    },
    blocks: parseBlocks(body),
  };
}

// ---------------------------------------------------------------------------------------
// Links
// ---------------------------------------------------------------------------------------

const UNSAFE_URL_CHARACTERS = /[\u0000-\u001f\u007f\s\\]/;
const URL_SCHEME = /^([a-z][a-z0-9+.-]*):/i;

/**
 * Return the URL when it is safe to render as a link, otherwise null.
 *
 * Allowed: absolute http(s) URLs with a host, mailto: addresses, and same-site relative
 * references starting with `/`, `#`, `?`, `./` or `../`. Everything else — other schemes
 * such as `javascript:` or `data:`, protocol-relative `//host` URLs, and anything containing
 * whitespace, control characters or backslashes (which browsers may silently strip or
 * reinterpret) — is refused.
 */
export function sanitizeHref(raw: string): string | null {
  const url = raw.trim();
  if (!url || UNSAFE_URL_CHARACTERS.test(url)) return null;

  const scheme = URL_SCHEME.exec(url);
  if (scheme) {
    const name = scheme[1].toLowerCase();
    if (name === "http" || name === "https") return /^https?:\/\/[^/?#]+/i.test(url) ? url : null;
    if (name === "mailto") return url.length > "mailto:".length ? url : null;
    return null;
  }
  if (url.startsWith("//")) return null;
  return /^(?:\/|#|\?|\.\.?\/)/.test(url) ? url : null;
}

// ---------------------------------------------------------------------------------------
// Inline content
// ---------------------------------------------------------------------------------------

const ESCAPABLE = new Set(["\\", "`", "*", "_", "[", "]", "(", ")", "#", "|", ">", "!", "-", "+", "."]);
const LINK = /^\[([^\]\n]+)\]\(([^()\s]*)\)/;
const PLACEHOLDER = /^\[([^\]\s][^\]\n]*)\]/;

/** Parse bold, inline code, links, placeholders and backslash escapes. Unmatched markers stay literal. */
export function parseInline(text: string, options: { links?: boolean } = {}): InlineNode[] {
  const allowLinks = options.links ?? true;
  const nodes: InlineNode[] = [];
  let buffer = "";
  const flush = () => {
    if (buffer) nodes.push({ type: "text", value: buffer });
    buffer = "";
  };

  let index = 0;
  while (index < text.length) {
    const char = text[index];

    if (char === "\\" && ESCAPABLE.has(text[index + 1])) {
      buffer += text[index + 1];
      index += 2;
      continue;
    }

    if (char === "`") {
      const close = text.indexOf("`", index + 1);
      if (close > index + 1) {
        flush();
        nodes.push({ type: "code", value: text.slice(index + 1, close) });
        index = close + 1;
        continue;
      }
    }

    if (char === "*" && text[index + 1] === "*") {
      const close = text.indexOf("**", index + 2);
      if (close > index + 2) {
        flush();
        nodes.push({ type: "strong", children: parseInline(text.slice(index + 2, close), options) });
        index = close + 2;
        continue;
      }
    }

    if (char === "[") {
      const rest = text.slice(index);
      const link = allowLinks ? LINK.exec(rest) : null;
      if (link) {
        flush();
        // Link text never contains further links; an unsafe target degrades to plain text.
        const children = parseInline(link[1], { links: false });
        const href = sanitizeHref(link[2]);
        if (href) nodes.push({ type: "link", href, external: /^(?:https?|mailto):/i.test(href), children });
        else nodes.push(...children);
        index += link[0].length;
        continue;
      }
      const placeholder = PLACEHOLDER.exec(rest);
      if (placeholder) {
        flush();
        nodes.push({ type: "placeholder", value: placeholder[1].trim() });
        index += placeholder[0].length;
        continue;
      }
    }

    buffer += char;
    index += 1;
  }
  flush();
  return nodes;
}

export function plainText(nodes: InlineNode[]): string {
  return nodes
    .map((node) => {
      if (node.type === "text" || node.type === "code") return node.value;
      if (node.type === "placeholder") return `[${node.value}]`;
      return plainText(node.children);
    })
    .join("");
}

export function slugify(text: string): string {
  const slug = text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/[\s-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return slug || "section";
}

function uniqueSlug(text: string, used: Set<string>): string {
  const base = slugify(text);
  let candidate = base;
  for (let suffix = 2; used.has(candidate); suffix += 1) candidate = `${base}-${suffix}`;
  used.add(candidate);
  return candidate;
}

// ---------------------------------------------------------------------------------------
// Blocks
// ---------------------------------------------------------------------------------------

const HEADING = /^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$/;
const RULE = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
const QUOTE = /^ {0,3}>[ \t]?(.*)$/;
const LIST_ITEM = /^ {0,3}([-*+]|\d{1,9}[.)])[ \t]+(.*)$/;
const TABLE_DIVIDER = /^ *\|? *:?-{3,}:? *(?:\| *:?-{3,}:? *)*\|? *$/;
const CALLOUT_MARKER = /^\[!(note|tip|important|warning|caution)\]$/i;
/** Block quotes nest at most this deep; anything deeper is flattened into a paragraph. */
const MAX_QUOTE_DEPTH = 3;

type ParseState = { ids: Set<string>; depth: number };

function isTableStart(lines: string[], index: number): boolean {
  const divider = lines[index + 1];
  return lines[index].includes("|") && divider !== undefined && divider.includes("|") && TABLE_DIVIDER.test(divider);
}

function startsOtherBlock(lines: string[], index: number): boolean {
  const line = lines[index];
  return HEADING.test(line) || RULE.test(line) || QUOTE.test(line) || isTableStart(lines, index);
}

function isOrderedMarker(marker: string): boolean {
  return /\d/.test(marker);
}

function splitTableRow(line: string): string[] {
  let row = line.trim();
  if (row.startsWith("|")) row = row.slice(1);
  if (row.endsWith("|") && !row.endsWith("\\|")) row = row.slice(0, -1);

  const cells: string[] = [];
  let current = "";
  for (let index = 0; index < row.length; index += 1) {
    if (row[index] === "\\" && row[index + 1] === "|") {
      current += "|";
      index += 1;
    } else if (row[index] === "|") {
      cells.push(current.trim());
      current = "";
    } else {
      current += row[index];
    }
  }
  cells.push(current.trim());
  return cells;
}

function parseLines(lines: string[], state: ParseState): BlockNode[] {
  const blocks: BlockNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      const children = parseInline(heading[2]);
      const text = plainText(children);
      // The page renders the document title as the only <h1>, so body headings start at h2.
      const level = Math.min(Math.max(heading[1].length, 2), 4) as 2 | 3 | 4;
      blocks.push({ type: "heading", level, id: uniqueSlug(text, state.ids), text, children });
      index += 1;
      continue;
    }

    if (RULE.test(line)) {
      blocks.push({ type: "rule" });
      index += 1;
      continue;
    }

    if (QUOTE.test(line)) {
      const inner: string[] = [];
      for (let match = QUOTE.exec(line); match; match = QUOTE.exec(lines[index] ?? "")) {
        inner.push(match[1]);
        index += 1;
      }
      const marker = CALLOUT_MARKER.exec(inner[0].trim());
      const content = marker ? inner.slice(1) : inner;
      const children: BlockNode[] =
        state.depth < MAX_QUOTE_DEPTH
          ? parseLines(content, { ids: state.ids, depth: state.depth + 1 })
          : [{ type: "paragraph", children: parseInline(content.join(" ").trim()) }];
      blocks.push({ type: "quote", callout: marker ? (marker[1].toLowerCase() as CalloutKind) : null, children });
      continue;
    }

    if (isTableStart(lines, index)) {
      const header = splitTableRow(line);
      const rows: InlineNode[][][] = [];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        const cells = splitTableRow(lines[index]);
        rows.push(header.map((_, cell) => parseInline(cells[cell] ?? "")));
        index += 1;
      }
      blocks.push({ type: "table", header: header.map((cell) => parseInline(cell)), rows });
      continue;
    }

    const item = LIST_ITEM.exec(line);
    if (item) {
      const ordered = isOrderedMarker(item[1]);
      const items = [item[2]];
      index += 1;
      while (index < lines.length) {
        const next = lines[index];
        if (!next.trim()) {
          // A blank line ends the list unless the following line continues it.
          const following = LIST_ITEM.exec(lines[index + 1] ?? "");
          if (following && isOrderedMarker(following[1]) === ordered && !RULE.test(lines[index + 1])) {
            index += 1;
            continue;
          }
          break;
        }
        if (startsOtherBlock(lines, index)) break;
        const nextItem = LIST_ITEM.exec(next);
        if (nextItem) {
          if (isOrderedMarker(nextItem[1]) !== ordered) break;
          items.push(nextItem[2]);
        } else {
          // Indented or lazily wrapped continuation of the current item.
          items[items.length - 1] += ` ${next.trim()}`;
        }
        index += 1;
      }
      blocks.push({
        type: "list",
        ordered,
        start: ordered ? Number.parseInt(item[1], 10) : 1,
        items: items.map((text) => parseInline(text.trim())),
      });
      continue;
    }

    const paragraph = [line.trim()];
    index += 1;
    while (
      index < lines.length &&
      lines[index].trim() &&
      !startsOtherBlock(lines, index) &&
      !LIST_ITEM.test(lines[index])
    ) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    blocks.push({ type: "paragraph", children: parseInline(paragraph.join(" ")) });
  }

  return blocks;
}

export function parseBlocks(markdown: string): BlockNode[] {
  return parseLines(normalizeNewlines(markdown).split("\n"), { ids: new Set(), depth: 0 });
}

/** Top-level headings of one level, for a table of contents. */
export function extractHeadings(blocks: BlockNode[], level: 2 | 3 | 4 = 2): HeadingLink[] {
  return blocks.flatMap((block) =>
    block.type === "heading" && block.level === level ? [{ id: block.id, text: block.text }] : [],
  );
}

// ---------------------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------------------

const HEADING_CLASSES: Record<2 | 3 | 4, string> = {
  2: "mt-10 scroll-mt-24 text-[1.3rem] font-semibold leading-snug tracking-[-0.01em] text-ink",
  3: "mt-7 scroll-mt-24 text-[1.05rem] font-semibold leading-snug text-ink",
  4: "mt-6 scroll-mt-24 text-[0.78rem] font-semibold uppercase tracking-[0.09em] text-muted",
};

const CALLOUT_ICON_CLASS = "h-4 w-4 shrink-0";

const CALLOUTS: Record<CalloutKind, { label: string; box: string; tone: string; icon: ReactNode }> = {
  note: {
    label: "Note",
    box: "border-brand-500/30 bg-brand-500/[0.06]",
    tone: "text-brand-500",
    icon: <Info aria-hidden="true" className={CALLOUT_ICON_CLASS} />,
  },
  tip: {
    label: "Tip",
    box: "border-signal/35 bg-signal/[0.07]",
    tone: "text-signal",
    icon: <Lightbulb aria-hidden="true" className={CALLOUT_ICON_CLASS} />,
  },
  important: {
    label: "Important",
    box: "border-violet/35 bg-violet/[0.07]",
    tone: "text-violet",
    icon: <CircleAlert aria-hidden="true" className={CALLOUT_ICON_CLASS} />,
  },
  warning: {
    label: "Warning",
    box: "border-caution/50 bg-caution/10",
    tone: "text-caution",
    icon: <TriangleAlert aria-hidden="true" className={CALLOUT_ICON_CLASS} />,
  },
  caution: {
    label: "Caution",
    box: "border-breach/40 bg-breach/[0.07]",
    tone: "text-breach",
    icon: <TriangleAlert aria-hidden="true" className={CALLOUT_ICON_CLASS} />,
  },
};

function InlineContent({ nodes }: { nodes: InlineNode[] }) {
  return <>{nodes.map(renderInline)}</>;
}

function renderInline(node: InlineNode, key: number): ReactNode {
  switch (node.type) {
    case "text":
      return <Fragment key={key}>{node.value}</Fragment>;
    case "strong":
      return (
        <strong key={key} className="font-semibold text-ink">
          <InlineContent nodes={node.children} />
        </strong>
      );
    case "code":
      return (
        <code key={key} className="rounded bg-surface-sunken px-1 py-0.5 font-mono text-[0.85em] text-ink">
          {node.value}
        </code>
      );
    case "placeholder":
      return (
        <span
          key={key}
          data-placeholder=""
          className="rounded-[0.3rem] bg-caution/15 px-1 py-px text-ink ring-1 ring-inset ring-caution/35"
        >
          [{node.value}]
        </span>
      );
    case "link":
      return (
        <a
          key={key}
          href={node.href}
          rel={node.external ? "noopener noreferrer" : undefined}
          className="font-medium text-ink underline decoration-brand-500/70 decoration-[1.5px] underline-offset-[3px] transition-colors hover:decoration-brand-500"
        >
          <InlineContent nodes={node.children} />
        </a>
      );
  }
}

function BlockView({ block }: { block: BlockNode }): ReactNode {
  switch (block.type) {
    case "heading": {
      const Tag = `h${block.level}` as "h2" | "h3" | "h4";
      return (
        <Tag id={block.id} className={HEADING_CLASSES[block.level]}>
          <InlineContent nodes={block.children} />
        </Tag>
      );
    }
    case "paragraph":
      return (
        <p className="mt-4">
          <InlineContent nodes={block.children} />
        </p>
      );
    case "list": {
      const items = block.items.map((item, index) => (
        <li key={index} className="pl-1">
          <InlineContent nodes={item} />
        </li>
      ));
      return block.ordered ? (
        <ol start={block.start === 1 ? undefined : block.start} className="mt-4 list-decimal space-y-2 pl-6 marker:text-muted">
          {items}
        </ol>
      ) : (
        <ul className="mt-4 list-disc space-y-2 pl-6 marker:text-subtle">{items}</ul>
      );
    }
    case "quote": {
      if (!block.callout) {
        return (
          <blockquote className="mt-5 border-l-4 border-line-strong pl-4 text-muted [&>*:first-child]:mt-0">
            <LegalMarkdown blocks={block.children} />
          </blockquote>
        );
      }
      const callout = CALLOUTS[block.callout];
      return (
        <div role="note" className={`mt-6 rounded-xl border px-4 py-4 sm:px-5 ${callout.box}`}>
          <p className={`flex items-center gap-2 text-[0.72rem] font-semibold uppercase tracking-[0.1em] ${callout.tone}`}>
            {callout.icon}
            <span className="text-ink">{callout.label}</span>
          </p>
          <div className="text-ink [&>*:first-child]:mt-2">
            <LegalMarkdown blocks={block.children} />
          </div>
        </div>
      );
    }
    case "rule":
      return <hr className="my-10 border-0 border-t border-line" />;
    case "table":
      return (
        <div role="region" aria-label="Table" tabIndex={0} className="mt-6 overflow-x-auto rounded-xl border border-line">
          <table className="w-full min-w-[34rem] border-collapse text-left text-[0.86rem] leading-6">
            <thead className="bg-surface-muted">
              <tr>
                {block.header.map((cell, index) => (
                  <th key={index} scope="col" className="border-b border-line px-3 py-2.5 align-bottom font-semibold text-ink">
                    <InlineContent nodes={cell} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((row, rowIndex) => (
                <tr key={rowIndex} className="border-t border-line first:border-t-0">
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2.5 align-top">
                      <InlineContent nodes={cell} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
  }
}

/** Render parsed blocks. Every value is emitted as React text, so nothing is ever interpreted as HTML. */
export function LegalMarkdown({ blocks }: { blocks: BlockNode[] }) {
  return (
    <>
      {blocks.map((block, index) => (
        <BlockView key={index} block={block} />
      ))}
    </>
  );
}
