"""
News fetcher module - Fetches real-time AI news from various sources
"""
import requests
import re
from html import unescape
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import urlparse
from ..logger import setup_logger


logger = setup_logger(__name__)



class _ArticleTextExtractor(HTMLParser):
    """Extract readable text from an HTML document."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "form"}:
            self._skip_depth += 1
        elif tag in {"p", "h1", "h2", "h3", "li", "article", "section", "br"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "nav", "footer", "form"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"p", "h1", "h2", "h3", "li", "article", "section", "br"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self.parts.append(data.strip())

    def get_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


class ArticleVerifier:
    """Verify RSS items against their original article pages."""

    def __init__(
        self,
        source_domains: Optional[Dict[str, List[str]]] = None,
        min_text_chars: int = 400,
        max_text_chars: int = 6000,
        timeout: int = 10,
    ):
        self.source_domains = source_domains or {}
        self.min_text_chars = min_text_chars
        self.max_text_chars = max_text_chars
        self.timeout = timeout

    def verify_item(self, item: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Return a verified copy of the item, or None if provenance checks fail."""
        source = item.get("source", "")
        link = item.get("link", "")
        if not self._is_allowed_source_link(source, link):
            logger.warning(f"Article verification rejected domain: {source} -> {link}")
            return None

        article_text = self.fetch_article_text(link)
        if len(article_text) < self.min_text_chars:
            logger.warning(f"Article verification rejected short body: {source} -> {link}")
            return None

        if not self._title_matches_text(item.get("title", ""), article_text):
            logger.warning(f"Article verification rejected title mismatch: {source} -> {link}")
            return None

        verified = dict(item)
        verified["verification_status"] = "body_verified"
        verified["verified_text"] = article_text[:self.max_text_chars]
        verified["verified_source_domain"] = urlparse(link).hostname or ""
        return verified

    def fetch_article_text(self, url: str) -> str:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            headers_obj = getattr(response, "headers", {}) or {}
            content_type = str(headers_obj.get("content-type", "")) if hasattr(headers_obj, "get") else ""
            if "pdf" in content_type.lower():
                return ""
            encoding = getattr(response, "encoding", None) or getattr(response, "apparent_encoding", None)
            if not isinstance(encoding, str):
                encoding = "utf-8"
            html = response.content.decode(encoding, errors="replace")
            extractor = _ArticleTextExtractor()
            extractor.feed(html)
            return unescape(extractor.get_text())
        except Exception as e:
            logger.warning(f"Article verification failed to fetch body {url}: {str(e)}")
            return ""

    def _is_allowed_source_link(self, source: str, link: str) -> bool:
        host = (urlparse(link).hostname or "").lower()
        if not host:
            return False
        allowed_domains = self.source_domains.get(source, [])
        return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)

    def _title_matches_text(self, title: str, text: str) -> bool:
        tokens = self._significant_tokens(title)
        if not tokens:
            return True
        text_norm = " ".join(self._significant_tokens(text))
        matched = sum(1 for token in set(tokens) if token in text_norm)
        required = min(2, max(1, len(set(tokens)) // 3))
        return matched >= required

    def _significant_tokens(self, text: str) -> List[str]:
        return [
            token for token in re.findall(r"[a-z0-9\u4e00-\u9fff]+", unescape(text).casefold())
            if len(token) >= 3
        ]


class NewsFetcher:
    """Fetch real-time AI news from RSS feeds and news APIs"""

    def __init__(self):
        """Initialize the news fetcher"""
        # RSS feed sources for AI news (official and research sources only)
        self.rss_feeds = {
            "OpenAI News": "https://openai.com/news/rss.xml",
            "Google AI Blog": "https://blog.google/technology/ai/rss/",
            "Google DeepMind Blog": "https://deepmind.google/blog/rss.xml",
            "Google Research Blog": "https://research.google/blog/rss/",
            "HuggingFace Blog": "https://huggingface.co/blog/feed.xml",
            "NVIDIA Deep Learning Blog": "https://blogs.nvidia.com/blog/category/deep-learning/feed/",
            "AWS Machine Learning Blog": "https://aws.amazon.com/blogs/machine-learning/feed/",
            "GitHub Blog AI": "https://github.blog/tag/ai/feed/",
            "arXiv AI": "https://rss.arxiv.org/rss/cs.AI",
            "arXiv Machine Learning": "https://rss.arxiv.org/rss/cs.LG",
            "arXiv Computer Vision": "https://rss.arxiv.org/rss/cs.CV",
            "arXiv NLP": "https://rss.arxiv.org/rss/cs.CL",
        }

        self.source_tiers = {
            "OpenAI News": "official",
            "Google AI Blog": "official",
            "Google DeepMind Blog": "official",
            "Google Research Blog": "official",
            "HuggingFace Blog": "official",
            "NVIDIA Deep Learning Blog": "official",
            "AWS Machine Learning Blog": "official",
            "GitHub Blog AI": "official",
            "arXiv AI": "research",
            "arXiv Machine Learning": "research",
            "arXiv Computer Vision": "research",
            "arXiv NLP": "research",
        }


        self.source_domains = {
            "OpenAI News": ["openai.com"],
            "Google AI Blog": ["blog.google"],
            "Google DeepMind Blog": ["deepmind.google"],
            "Google Research Blog": ["research.google"],
            "HuggingFace Blog": ["huggingface.co"],
            "NVIDIA Deep Learning Blog": ["blogs.nvidia.com", "nvidia.com"],
            "AWS Machine Learning Blog": ["aws.amazon.com"],
            "GitHub Blog AI": ["github.blog"],
            "arXiv AI": ["arxiv.org"],
            "arXiv Machine Learning": ["arxiv.org"],
            "arXiv Computer Vision": ["arxiv.org"],
            "arXiv NLP": ["arxiv.org"],
        }
        self.article_verifier = ArticleVerifier(self.source_domains)

        # Chinese AI news sources (zh)
        self.chinese_feeds = {
            # Tech News Outlets
            "36Kr (36氪)": "https://36kr.com/feed",
            "JiQiZhiXin (机器之心)": "https://rsshub.app/jiqizhixin/latest",
            "Leiphone (雷锋网)": "https://www.leiphone.com/feed",
            "Sina Tech (新浪科技)": "http://rss.sina.com.cn/tech/rollnews.xml",
            # Google News (fallback)
            "Google News AI (CN)": "https://news.google.com/rss/search?q=人工智能+AI&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
            "Google News LLM (CN)": "https://news.google.com/rss/search?q=大模型+GPT+Claude&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        }

        # Japanese AI news sources (ja)
        self.japanese_feeds = {
            # Tech News Outlets
            "ITmedia AI+": "https://rss.itmedia.co.jp/rss/2.0/aiplus.xml",
            "Nikkei xTECH": "https://xtech.nikkei.com/rss/index.rdf",
            "ASCII.jp AI": "https://ascii.jp/elem/000/004/000/4000000/index-2.xml",
            "Impress Watch": "https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf",
            # Google News (fallback)
            "Google News AI (JP)": "https://news.google.com/rss/search?q=人工知能+AI&hl=ja&gl=JP&ceid=JP:ja",
            "Google News Tech (JP)": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtcG9HZ0pEVGlnQVAB?hl=ja&gl=JP&ceid=JP:ja",
        }

        # French AI news sources (fr)
        self.french_feeds = {
            # Tech News Outlets
            "L'Usine Digitale": "https://www.usine-digitale.fr/rss/intelligence-artificielle.xml",
            "01net": "https://www.01net.com/rss/actualites/",
            "Frandroid": "https://www.frandroid.com/feed",
            "BFM Tech": "https://www.bfmtv.com/rss/tech/",
            # Google News (fallback)
            "Google News AI (FR)": "https://news.google.com/rss/search?q=intelligence+artificielle&hl=fr&gl=FR&ceid=FR:fr",
            "Google News Tech (FR)": "https://news.google.com/rss/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FtcG9HZ0pEVGlnQVAB?hl=fr&gl=FR&ceid=FR:fr",
        }

        # Spanish AI news sources (es)
        self.spanish_feeds = {
            # Tech News Outlets
            "Xataka": "https://www.xataka.com/tag/inteligencia-artificial/rss2.xml",
            "El País Tecnología": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/tecnologia/portada",
            "Hipertextual": "https://hipertextual.com/feed",
            "Genbeta": "https://www.genbeta.com/tag/inteligencia-artificial/rss2.xml",
            # Google News
            "Google News AI (ES)": "https://news.google.com/rss/search?q=inteligencia+artificial&hl=es&gl=ES&ceid=ES:es",
        }

        # German AI news sources (de)
        self.german_feeds = {
            # Tech News Outlets
            "Heise Online": "https://www.heise.de/rss/heise-atom.xml",
            "t3n Digital Pioneers": "https://t3n.de/tag/kuenstliche-intelligenz/feed/",
            "Golem.de": "https://rss.golem.de/rss.php?feed=RSS2.0",
            "Computerwoche": "https://www.computerwoche.de/rss/feed/computerwoche-alle",
            # Google News
            "Google News AI (DE)": "https://news.google.com/rss/search?q=künstliche+intelligenz&hl=de&gl=DE&ceid=DE:de",
        }

        # Korean AI news sources (ko)
        self.korean_feeds = {
            # Tech News Outlets
            "Chosun Biz Tech": "https://biz.chosun.com/rss/tech.xml",
            "ZDNet Korea": "https://zdnet.co.kr/rss/",
            "ETNews": "https://rss.etnews.com/Section901.xml",
            "Korean AI News": "https://www.aitimes.kr/rss/allArticle.xml",
            # Google News
            "Google News AI (KR)": "https://news.google.com/rss/search?q=인공지능&hl=ko&gl=KR&ceid=KR:ko",
        }

        # Portuguese AI news sources (pt)
        self.portuguese_feeds = {
            # Tech News Outlets
            "TecMundo": "https://www.tecmundo.com.br/rss",
            "Olhar Digital": "https://olhardigital.com.br/feed/",
            "Canaltech": "https://canaltech.com.br/rss/",
            "Exame": "https://exame.com/feed/tecnologia/",
            # Google News
            "Google News AI (BR)": "https://news.google.com/rss/search?q=inteligência+artificial&hl=pt-BR&gl=BR&ceid=BR:pt-419",
        }

        # Italian AI news sources (it)
        self.italian_feeds = {
            # Tech News Outlets
            "Il Sole 24 Ore Tech": "https://www.ilsole24ore.com/rss/tecnologia.xml",
            "Punto Informatico": "https://www.punto-informatico.it/feed/",
            "Tom's Hardware IT": "https://www.tomshw.it/feed",
            "Wired Italia": "https://www.wired.it/feed/rss",
            # Google News
            "Google News AI (IT)": "https://news.google.com/rss/search?q=intelligenza+artificiale&hl=it&gl=IT&ceid=IT:it",
        }

        # Russian AI news sources (ru)
        self.russian_feeds = {
            # Tech News Outlets
            "Habr": "https://habr.com/ru/rss/all/",
            "CNews": "https://www.cnews.ru/inc/rss/news.xml",
            "Roem.ru": "https://roem.ru/feed/",
            "VC.ru": "https://vc.ru/rss/all",
            # Google News
            "Google News AI (RU)": "https://news.google.com/rss/search?q=искусственный+интеллект&hl=ru&gl=RU&ceid=RU:ru",
        }

        # Dutch AI news sources (nl)
        self.dutch_feeds = {
            # Tech News Outlets
            "Tweakers": "https://feeds.feedburner.com/tweakers/mixed",
            "Computable": "https://www.computable.nl/rss.xml",
            "Dutch IT Channel": "https://dutchitchannel.nl/feed/",
            # Google News
            "Google News AI (NL)": "https://news.google.com/rss/search?q=kunstmatige+intelligentie&hl=nl&gl=NL&ceid=NL:nl",
        }

        # Arabic AI news sources (ar)
        self.arabic_feeds = {
            # Tech News Outlets
            "Arageek": "https://www.arageek.com/feed",
            "Tech Wd": "https://www.tech-wd.com/feed/",
            # Google News
            "Google News AI (AR)": "https://news.google.com/rss/search?q=الذكاء+الاصطناعي&hl=ar&gl=SA&ceid=SA:ar",
        }

        # Hindi AI news sources (hi)
        self.hindi_feeds = {
            # Tech News Outlets
            "Jagran Josh Tech": "https://www.jagranjosh.com/rss/tech.xml",
            "NDTV Gadgets": "https://feeds.feedburner.com/ndtvgadgets-latest",
            # Google News
            "Google News AI (HI)": "https://news.google.com/rss/search?q=कृत्रिम+बुद्धिमत्ता&hl=hi&gl=IN&ceid=IN:hi",
        }

        # Regional feeds are disabled until they have first-party or paper-level provenance.
        self.chinese_feeds = {}
        self.japanese_feeds = {}
        self.french_feeds = {}
        self.spanish_feeds = {}
        self.german_feeds = {}
        self.korean_feeds = {}
        self.portuguese_feeds = {}
        self.italian_feeds = {}
        self.russian_feeds = {}
        self.dutch_feeds = {}
        self.arabic_feeds = {}
        self.hindi_feeds = {}

    def fetch_rss_feed(self, feed_url: str, max_items: int = 10) -> List[Dict[str, str]]:
        """
        Fetch news items from an RSS feed.

        Args:
            feed_url: URL of the RSS feed
            max_items: Maximum number of items to fetch

        Returns:
            List of news items with title, link, description, and published date
        """
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(feed_url, headers=headers, timeout=10)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            items = []
            # Handle both RSS 2.0 and Atom formats
            if root.tag == 'rss':
                news_items = root.findall('.//item')[:max_items]
                for item in news_items:
                    title = item.find('title')
                    link = item.find('link')
                    description = item.find('description')
                    pub_date = item.find('pubDate')

                    items.append({
                        'title': title.text if title is not None else '',
                        'link': link.text if link is not None else '',
                        'description': self._clean_html(description.text if description is not None else ''),
                        'published': pub_date.text if pub_date is not None else '',
                    })
            else:
                # Atom format
                namespace = {'atom': 'http://www.w3.org/2005/Atom'}
                entries = root.findall('.//atom:entry', namespace)[:max_items]
                for entry in entries:
                    title = entry.find('atom:title', namespace)
                    link = entry.find('atom:link', namespace)
                    summary = entry.find('atom:summary', namespace)
                    updated = entry.find('atom:updated', namespace)

                    items.append({
                        'title': title.text if title is not None else '',
                        'link': link.get('href', '') if link is not None else '',
                        'description': self._clean_html(summary.text if summary is not None else ''),
                        'published': updated.text if updated is not None else '',
                    })

            logger.info(f"Fetched {len(items)} items from RSS feed")
            return items

        except Exception as e:
            logger.error(f"Failed to fetch RSS feed {feed_url}: {str(e)}")
            return []

    def _clean_html(self, text: Optional[str]) -> str:
        """Remove HTML tags from text"""
        if not text:
            return ''
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text).strip()

    def _parse_pubdate(self, date_str: str) -> Optional[datetime]:
        """Parse RSS/Atom pubDate strings to UTC datetime. Returns None if unparseable."""
        if not date_str or not date_str.strip():
            return None
        date_str = date_str.strip()

        formats = [
            # RFC 2822 (RSS standard): "Mon, 29 May 2026 14:30:00 +0000"
            ("rfc2822", lambda s: parsedate_to_datetime(s)),
            # ISO 8601 with Z: "2026-05-29T14:30:00Z"
            ("iso_z", lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))),
            # ISO 8601 with timezone: "2026-05-29T14:30:00+00:00"
            ("iso_tz", lambda s: datetime.fromisoformat(s)),
        ]

        for _name, parser in formats:
            try:
                dt = parser(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (ValueError, TypeError, IndexError):
                continue

        return None

    def _filter_by_time(
        self,
        items: List[Dict[str, str]],
        max_age_hours: int = 48
    ) -> List[Dict[str, str]]:
        """Filter news items to only those published within max_age_hours from now."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=max_age_hours)

        kept = []
        dropped = 0
        unparseable = 0

        for item in items:
            pub_dt = self._parse_pubdate(item.get("published", ""))
            if pub_dt is None:
                unparseable += 1
            elif pub_dt >= cutoff:
                kept.append(item)
            else:
                dropped += 1

        if dropped > 0:
            logger.info(f"Time filter: dropped {dropped} items older than {max_age_hours}h")
        if unparseable > 0:
            logger.info(f"Time filter: dropped {unparseable} items with unparseable dates")

        return kept

    def _deduplicate_items(self, items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Keep one item per normalized title, preferring higher-trust sources."""
        unique_items = {}
        tier_rank = {"official": 2, "research": 1}

        for item in items:
            title = unescape(item.get("title", "")).casefold()
            key = re.sub(r"\W+", "", title) or item.get("link", "").strip()
            if not key:
                continue

            existing = unique_items.get(key)
            if existing is None:
                unique_items[key] = item
                continue

            current_rank = tier_rank.get(item.get("source_tier", ""), 0)
            existing_rank = tier_rank.get(existing.get("source_tier", ""), 0)
            if current_rank > existing_rank:
                unique_items[key] = item

        return list(unique_items.values())



    def _iter_items_by_source_rounds(self, items: List[Dict[str, str]]):
        items_by_source = {}
        for item in items:
            items_by_source.setdefault(item.get("source", ""), []).append(item)

        while items_by_source:
            for source in list(items_by_source.keys()):
                source_items = items_by_source[source]
                if source_items:
                    yield source_items.pop(0)
                if not source_items:
                    del items_by_source[source]

    def _verify_news_items(
        self,
        news_data: Dict[str, List[Dict[str, str]]],
        max_articles_to_verify: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, str]]]:
        remaining = max_articles_to_verify
        verified_data = {'international': [], 'domestic': []}

        for section in ('international', 'domestic'):
            for item in self._iter_items_by_source_rounds(news_data[section]):
                if remaining is not None and remaining <= 0:
                    logger.info("Article verification limit reached")
                    return verified_data

                if remaining is not None:
                    remaining -= 1

                verified_item = self.article_verifier.verify_item(item)
                if verified_item:
                    verified_data[section].append(verified_item)

        logger.info(
            f"Article verification kept {len(verified_data['international'])} international "
            f"and {len(verified_data['domestic'])} domestic items"
        )
        return verified_data

    def fetch_recent_news(
        self,
        language: str = "en",
        max_items_per_source: int = 5,
        strict_verification: bool = False,
        max_articles_to_verify: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, str]]]:
        """
        Fetch recent AI news from all configured sources.

        Args:
            language: Language code for the response
            max_items_per_source: Maximum items to fetch per source
            strict_verification: Whether to require source-domain and article-body verification
            max_articles_to_verify: Maximum original article pages to fetch for verification

        Returns:
            Dictionary with 'international' and 'domestic' news lists
        """
        logger.info("Fetching recent AI news from all sources...")

        all_news = {
            'international': [],
            'domestic': []
        }

        # Fetch international news
        for source_name, feed_url in self.rss_feeds.items():
            items = self.fetch_rss_feed(feed_url, max_items_per_source)
            for item in items:
                item['source'] = source_name
                item['source_tier'] = self.source_tiers[source_name]
                all_news['international'].append(item)

        # Fetch domestic news based on language
        language_feeds_map = {
            "zh": self.chinese_feeds,
            "ja": self.japanese_feeds,
            "fr": self.french_feeds,
            "es": self.spanish_feeds,
            "de": self.german_feeds,
            "ko": self.korean_feeds,
            "pt": self.portuguese_feeds,
            "it": self.italian_feeds,
            "ru": self.russian_feeds,
            "nl": self.dutch_feeds,
            "ar": self.arabic_feeds,
            "hi": self.hindi_feeds,
        }

        feeds = language_feeds_map.get(language)
        if not feeds:
            logger.warning(f"No domestic feeds configured for language: {language}, using international only")
            all_news['international'] = self._deduplicate_items(
                self._filter_by_time(all_news['international'])
            )
            if strict_verification:
                all_news = self._verify_news_items(all_news, max_articles_to_verify)
            return all_news

        for source_name, feed_url in feeds.items():
            items = self.fetch_rss_feed(feed_url, max_items_per_source)
            for item in items:
                item['source'] = source_name
                item['source_tier'] = self.source_tiers.get(source_name, "editorial")
                all_news['domestic'].append(item)

        all_news['international'] = self._deduplicate_items(
            self._filter_by_time(all_news['international'])
        )
        all_news['domestic'] = self._deduplicate_items(
            self._filter_by_time(all_news['domestic'])
        )

        if strict_verification:
            all_news = self._verify_news_items(all_news, max_articles_to_verify)

        logger.info(
            f"Fetched {len(all_news['international'])} international news items "
            f"and {len(all_news['domestic'])} domestic ({language}) news items"
        )

        return all_news

    def format_news_for_summary(self, news_data: Dict[str, List[Dict[str, str]]]) -> str:
        """
        Format fetched news into a text suitable for AI summarization.

        Args:
            news_data: Dictionary with 'international' and 'domestic' news lists

        Returns:
            Formatted news text
        """
        formatted = "# Recent AI News Items to Summarize\n\n"

        if news_data['international']:
            formatted += "## International News\n\n"
            for i, item in enumerate(news_data['international'], 1):
                formatted += f"### {i}. {item['title']}\n"
                formatted += f"**Source:** {item['source']}\n"
                if item.get('verification_status'):
                    formatted += f"**Verification:** {item['verification_status']}\n"
                if item.get('verified_text'):
                    formatted += f"**Verified Article Text:** {item['verified_text'][:1200]}...\n"
                elif item['description']:
                    formatted += f"**Description:** {item['description'][:300]}...\n"
                formatted += f"**Link:** {item['link']}\n"
                if item['published']:
                    formatted += f"**Published:** {item['published']}\n"
                formatted += "\n"

        if news_data['domestic']:
            formatted += "## Domestic News\n\n"
            for i, item in enumerate(news_data['domestic'], 1):
                formatted += f"### {i}. {item['title']}\n"
                formatted += f"**Source:** {item['source']}\n"
                if item.get('verification_status'):
                    formatted += f"**Verification:** {item['verification_status']}\n"
                if item.get('verified_text'):
                    formatted += f"**Verified Article Text:** {item['verified_text'][:1200]}...\n"
                elif item['description']:
                    formatted += f"**Description:** {item['description'][:300]}...\n"
                formatted += f"**Link:** {item['link']}\n"
                if item['published']:
                    formatted += f"**Published:** {item['published']}\n"
                formatted += "\n"

        return formatted
