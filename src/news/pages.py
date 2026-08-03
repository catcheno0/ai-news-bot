"""Static digest page publishing."""
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional

import markdown
from markdown.extensions.toc import TocExtension


@dataclass(frozen=True)
class DigestPagePublication:
    latest_path: Path
    dated_path: Path
    latest_url: str
    dated_url: str


class DigestPagePublisher:
    """Write generated Markdown digests as static HTML files."""

    def __init__(self, output_dir: str = "public", site_url: str = ""):
        self.output_dir = Path(output_dir)
        self.site_url = site_url.rstrip("/")

    def publish(
        self,
        content: str,
        language: str,
        generated_at: Optional[datetime] = None,
        primary: bool = True,
    ) -> DigestPagePublication:
        generated_at = generated_at or datetime.now()
        date_slug = generated_at.strftime("%Y-%m-%d")
        latest_name = "latest.html" if primary else f"latest-{language}.html"
        dated_name = f"{date_slug}.html" if primary else f"{date_slug}-{language}.html"

        latest_path = self.output_dir / latest_name
        dated_path = self.output_dir / dated_name

        self.output_dir.mkdir(parents=True, exist_ok=True)
        html = self._render_html(content, language, generated_at)
        latest_path.write_text(html, encoding="utf-8")
        dated_path.write_text(html, encoding="utf-8")

        return DigestPagePublication(
            latest_path=latest_path,
            dated_path=dated_path,
            latest_url=self._page_url(latest_name),
            dated_url=self._page_url(dated_name),
        )

    def _page_url(self, filename: str) -> str:
        if not self.site_url:
            return ""
        return f"{self.site_url}/{filename}"

    def _render_html(self, content: str, language: str, generated_at: datetime) -> str:
        safe_markdown = escape(content)
        md = markdown.Markdown(
            extensions=[
                "extra",
                "sane_lists",
                "tables",
                TocExtension(permalink=False, separator="-"),
            ],
            output_format="html5",
        )
        digest_html = md.convert(safe_markdown)
        toc_html = md.toc if 'href="' in md.toc else '<p class="nav-empty">No sections available.</p>'
        generated_label = generated_at.strftime("%Y-%m-%d %H:%M")
        issue_label = generated_at.strftime("%Y-%m-%d")
        page_title = f"AI Daily Research Brief - {issue_label}"

        return f"""<!doctype html>
<html lang="{escape(language)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(page_title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f3f5f7;
      --paper: #ffffff;
      --ink: #151922;
      --muted: #5d6675;
      --line: #d9e0e8;
      --line-strong: #aeb8c7;
      --accent: #0f766e;
      --accent-strong: #115e59;
      --accent-soft: #e8f5f3;
      --signal: #9f1239;
      --signal-soft: #fff1f2;
      --code: #eef2f6;
    }}

    * {{
      box-sizing: border-box;
    }}

    html {{
      scroll-behavior: smooth;
    }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      line-height: 1.72;
    }}

    a {{
      color: var(--accent-strong);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}

    .report-shell {{
      width: min(1180px, calc(100% - 36px));
      margin: 0 auto;
      padding: 28px 0 52px;
    }}

    .report-hero {{
      padding: 24px 0 22px;
      border-bottom: 1px solid var(--line);
    }}

    .eyebrow {{
      margin: 0 0 8px;
      color: var(--accent-strong);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}

    .report-hero h1 {{
      margin: 0;
      max-width: 780px;
      font-size: 38px;
      line-height: 1.15;
      letter-spacing: 0;
    }}

    .dek {{
      max-width: 760px;
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 16px;
    }}

    .report-meta-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      max-width: 760px;
      margin-top: 20px;
    }}

    .report-meta-grid div {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
      padding: 11px 12px;
    }}

    .report-meta-grid span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.3;
    }}

    .report-meta-grid strong {{
      display: block;
      margin-top: 4px;
      font-size: 14px;
      line-height: 1.35;
    }}

    .report-layout {{
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
      gap: 24px;
      align-items: start;
      margin-top: 24px;
    }}

    .report-sidebar {{
      position: sticky;
      top: 18px;
    }}

    .report-nav,
    .verification-note {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
    }}

    .report-nav {{
      padding: 16px;
    }}

    .report-nav h2,
    .verification-note h2 {{
      margin: 0 0 12px;
      font-size: 13px;
      line-height: 1.35;
      letter-spacing: 0;
      text-transform: uppercase;
      color: var(--muted);
    }}

    .report-nav .toc {{
      font-size: 14px;
    }}

    .report-nav ul {{
      list-style: none;
      margin: 0;
      padding: 0;
    }}

    .report-nav li {{
      margin: 0;
      padding: 0;
    }}

    .report-nav li li {{
      padding-left: 12px;
      border-left: 1px solid var(--line);
    }}

    .report-nav a {{
      display: block;
      padding: 6px 0;
      color: var(--ink);
      text-decoration: none;
    }}

    .report-nav a:hover {{
      color: var(--accent-strong);
    }}

    .nav-empty {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}

    .verification-note {{
      margin-top: 12px;
      padding: 15px 16px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }}

    .verification-note p {{
      margin: 0;
    }}

    .report-document {{
      min-width: 0;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 34px 42px 44px;
      box-shadow: 0 18px 42px rgba(21, 25, 34, 0.08);
    }}

    .report-document h1,
    .report-document h2,
    .report-document h3,
    .report-document h4 {{
      line-height: 1.32;
      letter-spacing: 0;
    }}

    .report-document h1 {{
      margin: 0 0 22px;
      padding-bottom: 18px;
      border-bottom: 2px solid var(--ink);
      font-size: 30px;
    }}

    .report-document h2 {{
      margin: 34px 0 14px;
      padding: 12px 0 0;
      border-top: 1px solid var(--line-strong);
      font-size: 22px;
    }}

    .report-document h2:first-child {{
      margin-top: 0;
    }}

    .report-document h3 {{
      margin: 26px 0 10px;
      padding-left: 12px;
      border-left: 3px solid var(--accent);
      font-size: 18px;
    }}

    .report-document h4 {{
      margin: 18px 0 8px;
      color: var(--muted);
      font-size: 15px;
    }}

    .report-document p {{
      margin: 10px 0;
    }}

    .report-document ul,
    .report-document ol {{
      padding-left: 22px;
    }}

    .report-document li {{
      margin: 6px 0;
    }}

    .report-document blockquote {{
      margin: 18px 0;
      padding: 12px 15px;
      border-left: 4px solid var(--signal);
      background: var(--signal-soft);
      color: #4a1326;
    }}

    .report-document code {{
      background: var(--code);
      border-radius: 4px;
      padding: 2px 5px;
      font-family: "Cascadia Code", Consolas, monospace;
      font-size: 0.92em;
    }}

    .report-document pre {{
      overflow: auto;
      padding: 14px;
      background: var(--code);
      border-radius: 8px;
    }}

    .report-document table {{
      width: 100%;
      border-collapse: collapse;
      margin: 18px 0 22px;
      font-size: 14px;
    }}

    .report-document th,
    .report-document td {{
      border: 1px solid var(--line);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}

    .report-document th {{
      background: var(--accent-soft);
      color: var(--accent-strong);
      font-weight: 700;
    }}

    .report-document hr {{
      margin: 28px 0;
      border: 0;
      border-top: 1px solid var(--line);
    }}

    @media (max-width: 860px) {{
      .report-shell {{
        width: min(100% - 22px, 760px);
        padding: 16px 0 34px;
      }}

      .report-hero h1 {{
        font-size: 30px;
      }}

      .report-meta-grid {{
        grid-template-columns: 1fr;
      }}

      .report-layout {{
        grid-template-columns: 1fr;
        gap: 14px;
      }}

      .report-sidebar {{
        position: static;
      }}

      .report-document {{
        padding: 24px 18px 30px;
      }}

      .report-document h1 {{
        font-size: 25px;
      }}

      .report-document h2 {{
        font-size: 20px;
      }}
    }}
  </style>
</head>
<body>
  <div class="report-shell">
    <header class="report-hero">
      <p class="eyebrow">AI News Bot</p>
      <h1>AI Daily Research Brief</h1>
      <p class="dek">Research report generated from verified AI news sources.</p>
      <div class="report-meta-grid" aria-label="Report metadata">
        <div>
          <span>Issue date</span>
          <strong>{escape(issue_label)}</strong>
        </div>
        <div>
          <span>Generated at</span>
          <strong>{escape(generated_label)}</strong>
        </div>
        <div>
          <span>Language</span>
          <strong>{escape(language.upper())}</strong>
        </div>
      </div>
    </header>
    <div class="report-layout">
      <aside class="report-sidebar">
        <nav class="report-nav" aria-label="Digest sections">
          <h2>Contents</h2>
{toc_html}
        </nav>
        <section class="verification-note" aria-label="Verification note">
          <h2>Verification</h2>
          <p>Items are selected from verified source bodies and tiered sources. Official and research sources are preferred; editorial and community sources are used only when corroborated or linked to primary material.</p>
        </section>
      </aside>
      <main class="report-document">
{digest_html}
      </main>
    </div>
  </div>
</body>
</html>
"""
