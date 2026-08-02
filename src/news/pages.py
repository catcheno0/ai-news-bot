"""Static digest page publishing."""
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional

import markdown


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
        digest_html = markdown.markdown(
            safe_markdown,
            extensions=["extra", "sane_lists", "tables"],
            output_format="html5",
        )
        generated_label = generated_at.strftime("%Y-%m-%d %H:%M")
        page_title = f"AI News Digest - {generated_at.strftime('%Y-%m-%d')}"

        return f"""<!doctype html>
<html lang="{escape(language)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(page_title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --text: #17202a;
      --muted: #607080;
      --border: #d9e0e7;
      --accent: #1b6ef3;
      --accent-soft: #edf4ff;
      --code: #f0f3f6;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      line-height: 1.72;
    }}

    .shell {{
      width: min(920px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0 48px;
    }}

    header {{
      padding: 28px 0 24px;
    }}

    .eyebrow {{
      margin: 0 0 8px;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}

    h1 {{
      margin: 0 0 10px;
      font-size: 34px;
      line-height: 1.2;
      letter-spacing: 0;
    }}

    .meta {{
      margin: 0;
      color: var(--muted);
      font-size: 14px;
    }}

    main {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 28px;
      box-shadow: 0 18px 42px rgba(23, 32, 42, 0.08);
    }}

    main h1,
    main h2,
    main h3 {{
      line-height: 1.35;
      letter-spacing: 0;
    }}

    main h1 {{
      font-size: 28px;
      margin-top: 0;
    }}

    main h2 {{
      border-top: 1px solid var(--border);
      margin-top: 32px;
      padding-top: 24px;
      font-size: 22px;
    }}

    main h3 {{
      font-size: 18px;
    }}

    a {{
      color: var(--accent);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}

    blockquote {{
      margin: 18px 0;
      padding: 12px 16px;
      border-left: 4px solid var(--accent);
      background: var(--accent-soft);
      color: #26394d;
    }}

    code {{
      background: var(--code);
      border-radius: 4px;
      padding: 2px 5px;
      font-family: "Cascadia Code", Consolas, monospace;
      font-size: 0.92em;
    }}

    pre {{
      overflow: auto;
      padding: 14px;
      background: var(--code);
      border-radius: 8px;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
      font-size: 15px;
    }}

    th,
    td {{
      border: 1px solid var(--border);
      padding: 10px 12px;
      text-align: left;
      vertical-align: top;
    }}

    th {{
      background: #f8fafc;
    }}

    @media (max-width: 640px) {{
      .shell {{
        width: min(100% - 20px, 920px);
        padding: 12px 0 32px;
      }}

      header {{
        padding: 18px 2px;
      }}

      h1 {{
        font-size: 26px;
      }}

      main {{
        padding: 18px;
      }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <p class="eyebrow">AI News Bot</p>
      <h1>{escape(page_title)}</h1>
      <p class="meta">Generated at {escape(generated_label)} | Language: {escape(language.upper())}</p>
    </header>
    <main>
{digest_html}
    </main>
  </div>
</body>
</html>
"""
