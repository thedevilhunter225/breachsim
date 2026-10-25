import { readFile } from "node:fs/promises";
import path from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  getLegalDocument,
  isLegalSlug,
  LEGAL_DOCUMENT_SLUGS,
  legalContentDirectory,
  listLegalDocuments,
} from "./legal-documents";
import {
  extractHeadings,
  LegalMarkdown,
  normalizeStatus,
  parseBlocks,
  parseFrontmatter,
  parseInline,
  parseLegalDocument,
  plainText,
  sanitizeHref,
  type BlockNode,
  type InlineNode,
} from "./legal-markdown";

function render(markdown: string): string {
  return renderToStaticMarkup(createElement(LegalMarkdown, { blocks: parseBlocks(markdown) }));
}

function blockText(block: BlockNode): string {
  switch (block.type) {
    case "heading":
    case "paragraph":
      return plainText(block.children);
    case "list":
      return block.items.map(plainText).join(" ");
    case "quote":
      return block.children.map(blockText).join(" ");
    case "table":
      return [...block.header, ...block.rows.flat()].map(plainText).join(" ");
    case "rule":
      return "";
  }
}

function inlineNodes(blocks: BlockNode[]): InlineNode[] {
  const walk = (nodes: InlineNode[]): InlineNode[] =>
    nodes.flatMap((node) => (node.type === "strong" || node.type === "link" ? [node, ...walk(node.children)] : [node]));
  return blocks.flatMap((block) => {
    switch (block.type) {
      case "heading":
      case "paragraph":
        return walk(block.children);
      case "list":
        return block.items.flatMap(walk);
      case "quote":
        return inlineNodes(block.children);
      case "table":
        return [...block.header, ...block.rows.flat()].flatMap(walk);
      case "rule":
        return [];
    }
  });
}

function linksIn(blocks: BlockNode[]): string[] {
  return inlineNodes(blocks).flatMap((node) => (node.type === "link" ? [node.href] : []));
}

function placeholdersIn(blocks: BlockNode[]): string[] {
  return inlineNodes(blocks).flatMap((node) => (node.type === "placeholder" ? [node.value] : []));
}

function quoteDepth(block: BlockNode | undefined): number {
  return block?.type === "quote" ? 1 + quoteDepth(block.children[0]) : 0;
}

describe("parseFrontmatter", () => {
  it("reads flat key/value pairs, unquotes values and normalises key spelling", () => {
    const { data, body } = parseFrontmatter(
      "﻿---\r\ntitle: \"Privacy notice\"\r\nStatus: draft\r\nlast-reviewed: '[Last reviewed date]'\r\n# comment\r\nnested:\r\n  - ignored\r\nx: y\r\n---\r\nBody line\r\n",
    );
    expect(data).toEqual({
      title: "Privacy notice",
      status: "draft",
      last_reviewed: "[Last reviewed date]",
      nested: "",
      x: "y",
    });
    expect(body).toBe("Body line\n");
  });

  it("treats a document without a complete fence as body text", () => {
    expect(parseFrontmatter("No frontmatter")).toEqual({ data: {}, body: "No frontmatter" });
    expect(parseFrontmatter("---\ntitle: Unclosed\n")).toEqual({ data: {}, body: "---\ntitle: Unclosed\n" });
  });
});

describe("parseLegalDocument", () => {
  it("builds metadata from frontmatter with fallbacks", () => {
    const parsed = parseLegalDocument(
      "---\ntitle:  Terms  \nsummary: Short\naudience: Customers\nlast_reviewed: 2026-01-01\nstatus: Approved\n---\n## One\n",
      "terms",
    );
    expect(parsed.meta).toEqual({
      title: "Terms",
      status: "approved",
      lastReviewed: "2026-01-01",
      summary: "Short",
      audience: "Customers",
    });
    expect(parsed.blocks).toEqual([
      { type: "heading", level: 2, id: "one", text: "One", children: [{ type: "text", value: "One" }] },
    ]);

    expect(parseLegalDocument("Plain body", "fallback").meta).toEqual({
      title: "fallback",
      status: "draft",
      lastReviewed: null,
      summary: null,
      audience: null,
    });
    expect(parseLegalDocument("---\ntitle: \"\"\n---\nText").meta.title).toBe("Untitled document");
  });

  it("treats anything but an explicit approval as a draft", () => {
    expect(normalizeStatus("approved")).toBe("approved");
    expect(normalizeStatus(" APPROVED ")).toBe("approved");
    expect(normalizeStatus("final")).toBe("draft");
    expect(normalizeStatus("")).toBe("draft");
    expect(normalizeStatus(undefined)).toBe("draft");
  });
});

describe("sanitizeHref", () => {
  it.each([
    "https://example.com/privacy",
    "http://example.com",
    "HTTPS://Example.com/a?b=c#d",
    "mailto:privacy@example.com",
    "/legal/dpa",
    "#section-1",
    "?tab=terms",
    "./subprocessors",
    "../legal/terms",
  ])("allows %s", (url) => {
    expect(sanitizeHref(url)).toBe(url);
  });

  it("trims surrounding whitespace", () => {
    expect(sanitizeHref("  /legal  ")).toBe("/legal");
  });

  it.each([
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html;base64,PHNjcmlwdD4=",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "//evil.example",
    "/\\evil.example",
    "https:evil.example",
    "http://",
    "mailto:",
    "legal/dpa",
    "/legal dpa",
    "\u0000/legal",
    "",
  ])("refuses %j", (url) => {
    expect(sanitizeHref(url)).toBeNull();
  });
});

describe("parseInline", () => {
  it("parses bold text, inline code, links and placeholders", () => {
    expect(parseInline("A **bold [Company legal name]** and `{{first_name}}` with [the DPA](/legal/dpa).")).toEqual([
      { type: "text", value: "A " },
      {
        type: "strong",
        children: [
          { type: "text", value: "bold " },
          { type: "placeholder", value: "Company legal name" },
        ],
      },
      { type: "text", value: " and " },
      { type: "code", value: "{{first_name}}" },
      { type: "text", value: " with " },
      { type: "link", href: "/legal/dpa", external: false, children: [{ type: "text", value: "the DPA" }] },
      { type: "text", value: "." },
    ]);
  });

  it("marks http(s) and mailto links as external", () => {
    expect(parseInline("[site](https://example.com) [mail](mailto:a@example.com)")).toEqual([
      { type: "link", href: "https://example.com", external: true, children: [{ type: "text", value: "site" }] },
      { type: "text", value: " " },
      { type: "link", href: "mailto:a@example.com", external: true, children: [{ type: "text", value: "mail" }] },
    ]);
  });

  it("degrades unsafe links to their text and never nests links", () => {
    expect(parseInline("[click](javascript:alert%281%29) now")).toEqual([
      { type: "text", value: "click" },
      { type: "text", value: " now" },
    ]);
    expect(parseInline("[x](/y)", { links: false })).toEqual([
      { type: "placeholder", value: "x" },
      { type: "text", value: "(/y)" },
    ]);
  });

  it("honours escapes and leaves unmatched markers literal", () => {
    expect(parseInline("\\[not a placeholder\\] \\*\\*not bold\\*\\* \\q")).toEqual([
      { type: "text", value: "[not a placeholder] **not bold** \\q" },
    ]);
    expect(parseInline("**unclosed and [ ] bracket")).toEqual([{ type: "text", value: "**unclosed and [ ] bracket" }]);
    expect(parseInline("`open only")).toEqual([{ type: "text", value: "`open only" }]);
    expect(parseInline("empty `` pair")).toEqual([{ type: "text", value: "empty `` pair" }]);
  });
});

describe("parseBlocks", () => {
  it("clamps heading levels between h2 and h4 and keeps ids unique", () => {
    const headings = parseBlocks("# Title\n## 1. Scope\n### Scope\n#### Détails — [Region]\n##### Deep ##\n## 1. Scope\n## !!!").map(
      (block) => (block.type === "heading" ? [block.level, block.id, block.text] : block.type),
    );
    expect(headings).toEqual([
      [2, "title", "Title"],
      [2, "1-scope", "1. Scope"],
      [3, "scope", "Scope"],
      [4, "details-region", "Détails — [Region]"],
      [4, "deep", "Deep"],
      [2, "1-scope-2", "1. Scope"],
      [2, "section", "!!!"],
    ]);
  });

  it("parses paragraphs, bullet and numbered lists and rules", () => {
    const blocks = parseBlocks(
      [
        "First line",
        "continues here.",
        "- one",
        "  wrapped",
        "* two",
        "",
        "- three",
        "",
        "3. third",
        "4) fourth",
        "lazy continuation",
        "- bullets again",
        "",
        "- - -",
        "- before heading",
        "## Heading",
        "***",
        "After",
      ].join("\n"),
    );
    expect(blocks.map((block) => [block.type, blockText(block)])).toEqual([
      ["paragraph", "First line continues here."],
      ["list", "one wrapped two three"],
      ["list", "third fourth lazy continuation"],
      ["list", "bullets again"],
      ["rule", ""],
      ["list", "before heading"],
      ["heading", "Heading"],
      ["rule", ""],
      ["paragraph", "After"],
    ]);
    expect(blocks[1]).toMatchObject({ ordered: false, start: 1 });
    expect(blocks[2]).toMatchObject({ ordered: true, start: 3 });
  });

  it("parses callouts and plain quotes, and caps quote nesting", () => {
    const [callout, plain, deep] = parseBlocks(
      "> [!WARNING]\n> **Draft.** Not advice.\n>\n> - item\n\n> Plain quote\n\n> > > > > > Deep",
    );
    expect(callout).toMatchObject({ type: "quote", callout: "warning" });
    expect(callout.type === "quote" && callout.children.map((child) => child.type)).toEqual(["paragraph", "list"]);
    expect(plain).toMatchObject({ type: "quote", callout: null });
    expect(quoteDepth(deep)).toBe(4);
    expect(blockText(deep)).toBe("> > Deep");
  });

  it("parses pipe tables, padding missing cells and keeping escaped pipes", () => {
    const blocks = parseBlocks("| Name | Purpose |\n| --- | :---: |\n| Azure | Hosting \\| storage |\n| Together AI |\n\nAfter");
    expect(blocks[0]).toEqual({
      type: "table",
      header: [[{ type: "text", value: "Name" }], [{ type: "text", value: "Purpose" }]],
      rows: [
        [[{ type: "text", value: "Azure" }], [{ type: "text", value: "Hosting | storage" }]],
        [[{ type: "text", value: "Together AI" }], []],
      ],
    });
    expect(blocks[1]).toMatchObject({ type: "paragraph" });
    // A rule under a line that merely contains a pipe is not a table divider.
    expect(parseBlocks("a | b\n---").map((block) => block.type)).toEqual(["paragraph", "rule"]);
  });

  it("extracts top-level headings for a table of contents", () => {
    const blocks = parseBlocks("## A\n### B\n> ## Inside\n## C");
    expect(extractHeadings(blocks)).toEqual([
      { id: "a", text: "A" },
      { id: "c", text: "C" },
    ]);
    expect(extractHeadings(blocks, 3)).toEqual([{ id: "b", text: "B" }]);
  });
});

describe("LegalMarkdown", () => {
  it("renders every block type as escaped React output with safe links only", () => {
    const html = render(
      [
        "## Section <one>",
        "Text with <script>alert(1)</script>, a [site](https://example.com), an [internal page](/legal/dpa), [Placeholder], [bad](javascript:alert%281%29) and [worse](javascript:alert(1)).",
        "",
        "1. first",
        "2. second",
        "",
        "Between lists.",
        "",
        "5. fifth",
        "",
        "- bullet with `code`",
        "",
        "> [!NOTE]",
        "> Callout text",
        "",
        "> Quote text",
        "",
        "---",
        "",
        "| A | B |",
        "| --- | --- |",
        "| **x** | y |",
      ].join("\n"),
    );
    expect(html).toContain('<h2 id="section-one" class=');
    expect(html).toContain("Section &lt;one&gt;");
    expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
    expect(html).not.toContain("<script");
    expect(html).not.toMatch(/href="javascript/i);
    expect(html).toContain('<a href="https://example.com" rel="noopener noreferrer"');
    expect(html).toContain('<a href="/legal/dpa" class=');
    expect(html).toContain('data-placeholder=""');
    expect(html).toContain("[Placeholder]");
    expect(html).toMatch(/<ol class="[^"]*list-decimal/);
    expect(html).toContain('<ol start="5"');
    expect(html).toContain("<ul");
    expect(html).toContain("<code");
    expect(html).toContain('role="note"');
    expect(html).toContain(">Note</span>");
    expect(html).toContain("<blockquote");
    expect(html).toContain("<hr");
    expect(html).toContain('role="region"');
    expect(html).toContain('<th scope="col"');
    expect(html).toContain("<strong");
  });

  it.each([
    ["NOTE", "Note"],
    ["TIP", "Tip"],
    ["IMPORTANT", "Important"],
    ["WARNING", "Warning"],
    ["CAUTION", "Caution"],
  ])("labels [!%s] callouts", (marker, label) => {
    expect(render(`> [!${marker}]\n> Body`)).toContain(`>${label}</span>`);
  });
});

describe("legal documents in content/legal", () => {
  it("loads every published document as a draft with complete metadata", async () => {
    const documents = await listLegalDocuments();
    expect(documents.map((entry) => entry.slug)).toEqual([...LEGAL_DOCUMENT_SLUGS]);
    for (const entry of documents) {
      expect(entry.meta.title.length).toBeGreaterThan(3);
      expect(entry.meta.status).toBe("draft");
      expect(entry.meta.lastReviewed).toBeTruthy();
      expect(entry.meta.summary).toBeTruthy();
      expect(entry.meta.audience).toBeTruthy();
    }
  });

  it("opens every document with the template-draft, not-legal-advice banner", async () => {
    for (const entry of await listLegalDocuments()) {
      const [first] = entry.blocks;
      expect(first).toMatchObject({ type: "quote", callout: "warning" });
      const banner = blockText(first).toLowerCase();
      for (const phrase of ["template draft", "documented product behaviour", "not legal advice", "qualified counsel", "jurisdiction"]) {
        expect(banner).toContain(phrase);
      }
    }
  });

  it("uses only safe links, and internal links point at published documents", async () => {
    for (const entry of await listLegalDocuments()) {
      for (const href of linksIn(entry.blocks)) {
        if (href.startsWith("/legal/")) expect(isLegalSlug(href.slice("/legal/".length))).toBe(true);
        else expect(sanitizeHref(href)).toBe(href);
      }
      const source = await readFile(path.join(legalContentDirectory(), `${entry.slug}.md`), "utf8");
      expect(source).not.toMatch(/<\/?[a-z][^>]*>/i);
      expect(source).not.toMatch(/\]\((?!\/legal|https?:\/\/|mailto:|#)/);
    }
  });

  it("marks the facts counsel must supply as placeholders", async () => {
    for (const entry of await listLegalDocuments()) {
      expect(placeholdersIn(entry.blocks).length).toBeGreaterThan(0);
    }
    const privacy = await getLegalDocument("privacy");
    expect(placeholdersIn(privacy?.blocks ?? [])).toEqual(
      expect.arrayContaining([
        "Company legal name",
        "Registered address",
        "Privacy contact email",
        "Data protection officer",
        "Primary Azure region",
        "Effective date",
      ]),
    );
  });

  it("states the launch boundaries the product enforces", async () => {
    const text = async (slug: string) =>
      ((await getLegalDocument(slug))?.blocks ?? []).map(blockText).join(" ");
    expect(await text("privacy")).toContain("never ask for, collect or store passwords");
    expect(await text("subprocessors")).toMatch(/ElevenLabs[\s\S]*D-ID[\s\S]*SMS gateway[\s\S]*Telephony provider/);
    expect(await text("simulation-authorization")).toContain("No credentials are captured.");
    expect(await text("employee-notice")).toContain("Opt out.");
  });

  it("resolves only allow-listed slugs", async () => {
    expect(isLegalSlug("employee-notice")).toBe(true);
    expect(isLegalSlug("../package")).toBe(false);
    await expect(getLegalDocument("../package")).resolves.toBeNull();
    await expect(getLegalDocument("README")).resolves.toBeNull();
    expect((await getLegalDocument("employee-notice"))?.meta.title).toBe("Employee notice");
  });
});
