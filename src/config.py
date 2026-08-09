"""
Configuration management for AI News Bot
"""
import os
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from .logger import setup_logger


logger = setup_logger(__name__)


# Supported language codes and their display names
LANGUAGE_NAMES = {
    "zh": "Chinese (中文)",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "ja": "Japanese (日本語)",
    "de": "German (Deutsch)",
    "ko": "Korean (한국어)",
    "pt": "Portuguese (Português)",
    "ru": "Russian (Русский)",
    "ar": "Arabic (العربية)",
    "hi": "Hindi (हिन्दी)",
    "it": "Italian (Italiano)",
    "nl": "Dutch (Nederlands)",
}


class Config:
    """Application configuration manager"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.yaml file. If None, searches for it in default locations
        """
        # Load environment variables from .env file
        load_dotenv()

        # Find and load YAML config
        self.config_path = self._find_config_file(config_path)
        self.config_data = self._load_yaml_config()

        logger.info(f"Configuration loaded from {self.config_path}")

    def _find_config_file(self, config_path: Optional[str] = None) -> Path:
        """
        Find the configuration file.

        Args:
            config_path: Explicit path to config file

        Returns:
            Path to configuration file

        Raises:
            FileNotFoundError: If config file cannot be found
        """
        if config_path:
            path = Path(config_path)
            if path.exists():
                return path
            raise FileNotFoundError(f"Config file not found: {config_path}")

        # Search in default locations
        search_paths = [
            Path("config.yaml"),
            Path("config.yml"),
            Path(__file__).parent.parent / "config.yaml",
            Path(__file__).parent.parent / "config.yml",
        ]

        for path in search_paths:
            if path.exists():
                return path

        raise FileNotFoundError(
            "Config file not found. Searched: " + ", ".join(str(p) for p in search_paths)
        )

    def _load_yaml_config(self) -> Dict[str, Any]:
        """
        Load YAML configuration file.

        Returns:
            Configuration dictionary
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config or {}
        except Exception as e:
            logger.error(f"Failed to load config file: {str(e)}")
            return {}

    @property
    def news_topics(self) -> List[str]:
        """Get list of news topics to cover"""
        return self.config_data.get("news", {}).get("topics", [
            "Latest AI developments and breakthroughs"
        ])

    @property
    def stage1_prompt_template(self) -> str:
        """Get the Stage 1 selection prompt template"""
        default_template = """{formatted_news}

## YOUR TASK - STAGE 1: NEWS SELECTION

You are a senior AI industry analyst. Analyze the {total_items} verified news items above and select 5-8 of the highest-quality items. If fewer than 5 verified items are available, select all worthwhile verified items.

### SELECTION CRITERIA:
- ✅ Groundbreaking research or technical breakthroughs
- ✅ Major product launches or significant updates
- ✅ Important policy changes or regulations
- ✅ Large funding rounds or M&A activities
- ✅ Balanced coverage across categories (LLM, Agents, Research, Products, etc.)
- ✅ Include both international and domestic news when available, but do not force equal counts or lower the quality bar for either section
- Prefer items with an "official" or "research" source tier
- Use editorial/community items only when **Selection Role:** is primary_link or corroborated_primary
- Never select **Selection Role:** context_only items; they are clues for comparison only
- ✅ Use the supplied original link as the sole source of factual claims
- ✅ Only select items marked **Verification:** body_verified when present

### OUTPUT FORMAT:
Return ONLY a JSON array of selected news IDs. No explanations, no markdown, just the JSON array.

Example format:
["INT-1", "INT-5", "DOM-2", "INT-12", ...]

CRITICAL: Select 5-8 items when at least 5 verified items are available. Never select **Selection Role:** context_only items. If fewer are available, select every worthwhile verified item that passes the selection role rule."""

        return self.config_data.get("news", {}).get("stage1_prompt_template", default_template)

    @property
    def stage2_prompt_template(self) -> str:
        """Get the Stage 2 summarization prompt template"""
        default_template = """You are a senior AI industry analyst. Create a structured research brief titled "AI Daily Research Brief" for the {count} pre-selected news items below.

{selected_news}

## OUTPUT STRUCTURE:

Start the digest with this exact H1:
# AI Daily Research Brief

Then use these sections in this order. Always keep domestic and international coverage in separate sections. Do not force equal counts; if one side has no selected items, include the empty-section notice described below rather than filling it with lower-quality items.

For Chinese output, use these section names: "国内 AI 动态" and "国外 AI 动态". For English output, use "Domestic AI Developments" and "International AI Developments".

## Domestic AI Developments
If no domestic selected items passed verification and selection rules, write one sentence: "No sufficiently verified domestic AI items today." Otherwise use the same news-analysis template below for every selected domestic item.

### Executive Summary
- Provide concise bullets that synthesize the selected domestic developments.
- Each bullet must be grounded in one or more selected domestic news items.

### Key Signals
Create a markdown table with these columns:
| Signal | Evidence | Why It Matters |
Evidence must refer to selected domestic items, source tiers, verification status, or corroboration metadata.

### Foundation Models & LLMs
### Research & Papers
### Agents & Products
### Infrastructure & Hardware
### Market & Policy
### Open Source & Community
### Other Notable AI Developments

## International AI Developments
If no international selected items passed verification and selection rules, write one sentence: "No sufficiently verified international AI items today." Otherwise use the same news-analysis template below for every selected international item.

### Executive Summary
- Provide concise bullets that synthesize the selected international developments.
- Each bullet must be grounded in one or more selected international news items.

### Key Signals
Create a markdown table with these columns:
| Signal | Evidence | Why It Matters |
Evidence must refer to selected international items, source tiers, verification status, or corroboration metadata.

### Foundation Models & LLMs
### Research & Papers
### Agents & Products
### Infrastructure & Hardware
### Market & Policy
### Open Source & Community
### Other Notable AI Developments

For each selected news item, place it under the correct domestic or international section and the best matching topic subsection. Use this format:

#### Clear analytical headline
**Source Tier:** official / research / editorial / community
**Verification:** body_verified or the supplied verification status
**Corroboration:** summarize supporting sources when available; otherwise write "Primary source only"
**Published:** original publication date/time if supplied

Write exactly 4-6 sentences of analysis for the item:
- Sentence 1: what happened.
- Sentence 2: the concrete technical, product, research, market, or policy details from the verified text.
- Sentence 3: why it matters.
- Sentence 4: what this changes for developers, researchers, companies, or users.
- Sentences 5-6 are optional only when the verified text supports useful nuance.

Source: [Source Name](URL)

## Source & Verification Notes
- State that the brief is based only on the selected verified items above.
- Mention that official and research sources are preferred, while editorial/community sources are used only when linked to primary material or corroborated.
- Do not add any claims that are not supported by the selected source material.

## QUALITY REQUIREMENTS:
- Summarize ALL {count} selected items. Do not skip any selected item.
- Treat **Verified Article Text** as the only factual basis for summaries.
- Preserve source links exactly as supplied.
- Include Source Tier, Verification, Corroboration, Published, and Source for every news item.
- Use a professional research-brief tone, not a marketing tone.
- Keep the digest readable on a phone: concise paragraphs, clear headings, and no oversized tables except Key Signals.
- Write the final digest in the same language requested by the application.

## AVOID:
- Do not invent news items, examples, companies, dates, numbers, benchmarks, links, or claims.
- Do not include fictional sample content.
- Do not summarize from outside knowledge.
- Do not use hype phrases without verified evidence.
- Do not omit clickable markdown links."""

        return self.config_data.get("news", {}).get("stage2_prompt_template", default_template)

    @property
    def log_level(self) -> str:
        """Get logging level"""
        return self.config_data.get("logging", {}).get("level", "INFO")

    @property
    def log_format(self) -> str:
        """Get logging format"""
        return self.config_data.get("logging", {}).get(
            "format",
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    @property
    def notification_methods(self) -> List[str]:
        """Get enabled notification methods from environment"""
        methods_str = os.getenv("NOTIFICATION_METHODS", "")
        if not methods_str:
            return []
        return [m.strip().lower() for m in methods_str.split(",")]

    @property
    def ai_response_language(self) -> str:
        """Get the language for AI-generated content (single language, deprecated)"""
        return os.getenv("AI_RESPONSE_LANGUAGE", "en").strip().lower()
    
    @property
    def ai_response_languages(self) -> List[str]:
        """Get the list of languages for AI-generated content (supports comma-separated values)"""
        languages_str = os.getenv("AI_RESPONSE_LANGUAGE", "en").strip().lower()
        # Split by comma and clean up whitespace
        languages = [lang.strip() for lang in languages_str.split(",") if lang.strip()]
        # Validate languages
        valid_languages = []
        for lang in languages:
            if lang == "en" or lang in LANGUAGE_NAMES:
                valid_languages.append(lang)
            else:
                logger.warning(f"Unsupported language code '{lang}', skipping")
        # Return at least 'en' if no valid languages
        return valid_languages if valid_languages else ["en"]

    @property
    def enable_web_search(self) -> bool:
        """Get whether to enable web search for fetching current news"""
        # Check config file first, then environment variable
        config_value = self.config_data.get("news", {}).get("enable_web_search")
        if config_value is not None:
            return bool(config_value)
        env_value = os.getenv("ENABLE_WEB_SEARCH", "false").strip().lower()
        return env_value in ("true", "1", "yes", "on")

    @property
    def max_items_per_source(self) -> int:
        """Maximum news items to fetch per source"""
        return self.config_data.get("news", {}).get("max_items_per_source", 5)

    @property
    def news_max_age_hours(self) -> int:
        """Maximum age of RSS items to consider for a daily digest."""
        env_value = os.getenv("NEWS_MAX_AGE_HOURS", "").strip()
        if env_value:
            return int(env_value)
        return int(self.config_data.get("news", {}).get("max_age_hours", 48))


    @property
    def strict_verification(self) -> bool:
        """Whether original article verification is required before generation."""
        config_value = self.config_data.get("news", {}).get("strict_verification")
        if config_value is not None:
            return bool(config_value)
        env_value = os.getenv("STRICT_VERIFICATION", "false").strip().lower()
        return env_value in ("true", "1", "yes", "on")

    @property
    def verification_fail_policy(self) -> str:
        """How to handle items that fail verification."""
        value = str(self.config_data.get("news", {}).get("verification_fail_policy", "skip")).strip().lower()
        return value if value in ("skip", "fail") else "skip"

    @property
    def min_verified_items(self) -> int:
        """Minimum verified item count required before sending a digest."""
        return int(self.config_data.get("news", {}).get("min_verified_items", 8))

    @property
    def max_articles_to_verify(self) -> int:
        """Maximum original articles to fetch and verify per digest run."""
        return int(self.config_data.get("news", {}).get("max_articles_to_verify", 40))

    @property
    def pages_enabled(self) -> bool:
        """Whether to publish generated digests as static GitHub Pages files."""
        env_value = os.getenv("PAGES_ENABLED", "").strip().lower()
        if env_value:
            return env_value in ("true", "1", "yes", "on")
        return bool(self.config_data.get("pages", {}).get("enabled", False))

    @property
    def pages_output_dir(self) -> str:
        """Directory where static digest pages are written."""
        env_value = os.getenv("PAGES_OUTPUT_DIR", "").strip()
        if env_value:
            return env_value
        return str(self.config_data.get("pages", {}).get("output_dir", "public"))

    @property
    def pages_site_url(self) -> str:
        """Public base URL for GitHub Pages digest links."""
        env_value = os.getenv("PAGES_SITE_URL", "").strip()
        if env_value:
            return env_value.rstrip("/")
        return str(self.config_data.get("pages", {}).get("site_url", "")).rstrip("/")

    @property
    def llm_provider(self) -> str:
        """Get the LLM provider to use (claude or deepseek)"""
        # Check environment variable first, then config file
        env_provider = os.getenv("LLM_PROVIDER", "").strip().lower()
        if env_provider:
            return env_provider
        return self.config_data.get("llm", {}).get("provider", "claude").lower()

    @property
    def llm_model(self) -> Optional[str]:
        """Get the specific model to use (if specified)"""
        # Check environment variable first, then config file
        env_model = os.getenv("LLM_MODEL", "").strip()
        if env_model:
            return env_model
        return self.config_data.get("llm", {}).get("model")

    @property
    def llm_api_key(self) -> Optional[str]:
        """Get the API key for the LLM provider"""
        # Check environment variables based on provider
        provider = self.llm_provider
        if provider == "deepseek":
            return os.getenv("DEEPSEEK_API_KEY")
        elif provider == "claude":
            return os.getenv("ANTHROPIC_API_KEY")
        elif provider == "gemini":
            return os.getenv("GOOGLE_API_KEY")
        elif provider == "grok":
            return os.getenv("XAI_API_KEY")
        elif provider == "openai":
            return os.getenv("OPENAI_API_KEY")
        return None

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.

        Args:
            key: Dot-separated key path (e.g., "news.topics")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split(".")
        value = self.config_data

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default

            if value is None:
                return default

        return value
