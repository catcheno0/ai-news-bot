"""
AI News Generator using configurable LLM providers
"""
from typing import List, Optional, Dict
import json
import re
from ..logger import setup_logger
from ..config import LANGUAGE_NAMES
from .web_search import WebSearchTool, get_search_tool_definition
from .fetcher import NewsFetcher
from ..llm_providers import get_llm_provider


logger = setup_logger(__name__)


class NewsGenerator:
    """Generate AI news digest using configurable LLM providers"""

    def __init__(
        self,
        provider_name: str = "claude",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        enable_web_search: bool = False
    ):
        """
        Initialize the NewsGenerator.

        Args:
            provider_name: Name of LLM provider to use ('claude' or 'deepseek')
            api_key: API key for the provider. If None, will read from environment
            model: Model name to use. If None, uses provider's default model
            enable_web_search: Whether to enable web search tool for fetching current news

        Raises:
            ValueError: If provider is not recognized or API key is not provided
        """
        # Initialize LLM provider
        self.provider = get_llm_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model
        )

        self.enable_web_search = enable_web_search
        self.search_tool = WebSearchTool() if enable_web_search else None
        self.news_fetcher = NewsFetcher()
        logger.info(
            f"NewsGenerator initialized with {self.provider.provider_name} "
            f"(model: {self.provider.model}, web_search: {enable_web_search})"
        )

    def _format_news_with_ids(self, news_data: Dict) -> tuple:
        """
        Format news with unique IDs for selection stage.

        Args:
            news_data: Dictionary with 'international' and 'domestic' news lists

        Returns:
            Tuple of (formatted_text, news_items_dict)
        """
        formatted = "# Recent AI News Items for Selection\n\n"
        news_items = {}  # id -> full news item
        item_id = 1

        if news_data['international']:
            formatted += "## International News\n\n"
            for item in news_data['international']:
                news_id = f"INT-{item_id}"
                news_items[news_id] = item

                formatted += f"### [{news_id}] {item['title']}\n"
                formatted += f"**Source:** {item['source']}\n"
                formatted += f"**Source Tier:** {item.get('source_tier', 'unknown')}\n"
                if item.get('selection_role'):
                    formatted += f"**Selection Role:** {item['selection_role']}\n"
                if item.get('corroboration_score') is not None:
                    supporters = ", ".join(item.get('supporting_sources', [])) or "none"
                    supporter_tiers = ", ".join(item.get('supporting_source_tiers', [])) or "none"
                    formatted += (
                        f"**Corroboration:** score={item.get('corroboration_score', 0)}; "
                        f"supporting_sources={supporters}; supporting_tiers={supporter_tiers}\n"
                    )
                if item.get('verification_status'):
                    formatted += f"**Verification:** {item['verification_status']}\n"
                if item.get('verified_text'):
                    formatted += f"**Verified Article Text:** {item['verified_text'][:2500]}...\n"
                elif item['description']:
                    formatted += f"**Description:** {item['description'][:400]}...\n"
                formatted += f"**Link:** {item.get('link', '')}\n"
                if item['published']:
                    formatted += f"**Published:** {item['published']}\n"
                formatted += "\n"
                item_id += 1

        if news_data['domestic']:
            formatted += "## Domestic News\n\n"
            item_id = 1
            for item in news_data['domestic']:
                news_id = f"DOM-{item_id}"
                news_items[news_id] = item

                formatted += f"### [{news_id}] {item['title']}\n"
                formatted += f"**Source:** {item['source']}\n"
                formatted += f"**Source Tier:** {item.get('source_tier', 'unknown')}\n"
                if item.get('selection_role'):
                    formatted += f"**Selection Role:** {item['selection_role']}\n"
                if item.get('corroboration_score') is not None:
                    supporters = ", ".join(item.get('supporting_sources', [])) or "none"
                    supporter_tiers = ", ".join(item.get('supporting_source_tiers', [])) or "none"
                    formatted += (
                        f"**Corroboration:** score={item.get('corroboration_score', 0)}; "
                        f"supporting_sources={supporters}; supporting_tiers={supporter_tiers}\n"
                    )
                if item.get('verification_status'):
                    formatted += f"**Verification:** {item['verification_status']}\n"
                if item.get('verified_text'):
                    formatted += f"**Verified Article Text:** {item['verified_text'][:2500]}...\n"
                elif item['description']:
                    formatted += f"**Description:** {item['description'][:400]}...\n"
                formatted += f"**Link:** {item.get('link', '')}\n"
                if item['published']:
                    formatted += f"**Published:** {item['published']}\n"
                formatted += "\n"
                item_id += 1

        return formatted, news_items


    def _format_selected_news_item(self, news_id: str, item: Dict) -> str:
        formatted = f"### [{news_id}] {item['title']}\n"
        formatted += f"**Source:** {item['source']}\n"
        formatted += f"**Source Tier:** {item.get('source_tier', 'unknown')}\n"
        if item.get('selection_role'):
            formatted += f"**Selection Role:** {item['selection_role']}\n"
        if item.get('corroboration_score') is not None:
            supporters = ", ".join(item.get('supporting_sources', [])) or "none"
            supporter_tiers = ", ".join(item.get('supporting_source_tiers', [])) or "none"
            formatted += (
                f"**Corroboration:** score={item.get('corroboration_score', 0)}; "
                f"supporting_sources={supporters}; supporting_tiers={supporter_tiers}\n"
            )
        if item.get('verification_status'):
            formatted += f"**Verification:** {item['verification_status']}\n"
        content = item.get('verified_text') or item.get('description', '')
        if content:
            label = "Verified Article Text" if item.get('verified_text') else "Content"
            formatted += f"**{label}:** {content}\n"
        formatted += f"**Link:** {item['link']}\n"
        if item['published']:
            formatted += f"**Published:** {item['published']}\n"
        return formatted + "\n"

    def _format_selected_news(self, selected_ids: List[str], news_items: Dict[str, Dict]) -> str:
        formatted_selected = "# Selected High-Quality AI News Items\n\n"
        domestic_ids = [news_id for news_id in selected_ids if news_id.startswith("DOM-")]
        international_ids = [news_id for news_id in selected_ids if not news_id.startswith("DOM-")]
        sections = [
            (
                "Domestic AI Developments",
                domestic_ids,
                "No selected domestic items passed verification and selection rules.",
            ),
            (
                "International AI Developments",
                international_ids,
                "No selected international items passed verification and selection rules.",
            ),
        ]

        for title, section_ids, empty_notice in sections:
            formatted_selected += f"## {title}\n\n"
            if not section_ids:
                formatted_selected += f"{empty_notice}\n\n"
                continue
            for news_id in section_ids:
                formatted_selected += self._format_selected_news_item(news_id, news_items[news_id])
                formatted_selected += "\n"

        return formatted_selected

    def _is_selection_allowed(self, item: Dict) -> bool:
        role = item.get("selection_role")
        if role:
            return role in {"primary", "primary_link", "corroborated_primary", "trusted_editorial"}
        return item.get("source_tier") in {"official", "research"}

    def _allowed_news_ids(self, news_items: Dict[str, Dict], target_max_items: int) -> List[str]:
        return [
            news_id for news_id, item in news_items.items()
            if self._is_selection_allowed(item)
        ][:target_max_items]

    def _filter_selection_to_allowed_items(
        self,
        selected_ids: List[str],
        news_items: Dict[str, Dict],
        target_max_items: int,
    ) -> List[str]:
        allowed_ids = set(self._allowed_news_ids(news_items, len(news_items)))
        filtered_ids = [news_id for news_id in selected_ids if news_id in allowed_ids]

        if len(filtered_ids) < len(selected_ids):
            removed = [news_id for news_id in selected_ids if news_id not in allowed_ids]
            logger.warning(f"Selection removed context-only items: {removed}")

        if not filtered_ids:
            logger.warning("No selected items passed selection-role rules, using primary fallback")
            filtered_ids = self._allowed_news_ids(news_items, target_max_items)

        return filtered_ids[:target_max_items]


    def _build_summarization_prompt(
        self,
        stage2_template: str,
        selected_ids: List[str],
        news_items: Dict[str, Dict],
        language: str,
    ) -> str:
        formatted_selected = self._format_selected_news(selected_ids, news_items)
        prompt = stage2_template.format(
            count=len(selected_ids),
            selected_news=formatted_selected
        )
        if language and language.lower() != "en":
            language_name = LANGUAGE_NAMES.get(language.lower(), language.upper())
            prompt += f"\n\nIMPORTANT: Please respond entirely in {language_name}."
        return prompt

    def _count_verified_items(self, news_data: Dict) -> int:
        return sum(
            1
            for section in ("international", "domestic")
            for item in news_data.get(section, [])
            if item.get("verification_status") == "body_verified" and item.get("verified_text")
        )

    def _parse_digest_verification_response(self, response_text: str) -> Dict:
        json_match = re.search(r'\{[\s\S]*?\}', response_text)
        if not json_match:
            return {"passed": False, "unsupported_news_ids": [], "reason": "No JSON object returned"}
        try:
            data = json.loads(json_match.group(0))
        except json.JSONDecodeError:
            return {"passed": False, "unsupported_news_ids": [], "reason": "Invalid JSON returned"}
        unsupported = data.get("unsupported_news_ids", [])
        if not isinstance(unsupported, list):
            unsupported = []
        passed_value = data.get("passed", False)
        passed = passed_value is True or str(passed_value).strip().lower() == "true"
        return {
            "passed": bool(passed and not unsupported),
            "unsupported_news_ids": [str(news_id) for news_id in unsupported],
            "reason": str(data.get("reason", "")),
        }

    def _verify_digest_against_sources(
        self,
        digest_text: str,
        selected_ids: List[str],
        news_items: Dict[str, Dict],
    ) -> Dict:
        source_material = self._format_selected_news(selected_ids, news_items)
        verification_prompt = f"""You are a strict fact-checking gate for an AI news digest.

Compare the digest against the verified source material below. A claim is supported only if it is directly present in the verified article text, title, source, link, or publication time. Do not use outside knowledge.

Return ONLY this JSON object:
{{"passed": true|false, "unsupported_news_ids": ["INT-1"], "reason": "short reason"}}

## VERIFIED SOURCE MATERIAL
{source_material}

## DIGEST TO CHECK
{digest_text}
"""
        response = self.provider.generate(
            messages=[{"role": "user", "content": verification_prompt}],
            max_tokens=1200,
            temperature=0,
        )
        return self._parse_digest_verification_response(response)

    def generate_news_digest_from_sources(
        self,
        max_tokens: int = 8000,
        language: str = "en",
        max_items_per_source: int = 5,
        stage1_template: Optional[str] = None,
        stage2_template: Optional[str] = None,
        strict_verification: bool = False,
        verification_fail_policy: str = "skip",
        min_verified_items: int = 0,
        max_articles_to_verify: Optional[int] = None,
        news_max_age_hours: int = 48,
    ) -> str:
        """
        Fetch real-time news and generate a digest using two-stage prompt chaining:
        Stage 1: Analyze and select 5-8 high-quality news items
        Stage 2: Create detailed summaries for selected items

        Args:
            max_tokens: Maximum tokens in response
            language: Language code for the response
            max_items_per_source: Maximum items to fetch per source
            stage1_template: Optional Stage 1 prompt template (from config)
            stage2_template: Optional Stage 2 prompt template (from config)
            strict_verification: Whether to verify source bodies and fact-check the final digest
            verification_fail_policy: "skip" removes unsupported selected items once; "fail" aborts
            min_verified_items: Minimum verified source items required before generation
            max_articles_to_verify: Maximum original article pages to fetch for verification
            news_max_age_hours: Maximum RSS item age to keep before verification

        Returns:
            Generated news digest as string

        Raises:
            Exception: If fetching or generation fails
        """
        try:
            # Fetch real-time news
            logger.info("Fetching real-time AI news from sources...")
            fetch_kwargs = {
                "language": language,
                "max_items_per_source": max_items_per_source,
                "max_age_hours": news_max_age_hours,
            }
            if strict_verification:
                fetch_kwargs["strict_verification"] = True
                fetch_kwargs["max_articles_to_verify"] = max_articles_to_verify
            news_data = self.news_fetcher.fetch_recent_news(**fetch_kwargs)


            if strict_verification:
                verified_count = self._count_verified_items(news_data)
                if verified_count < min_verified_items:
                    raise Exception(
                        f"Only {verified_count} verified news items available; minimum is {min_verified_items}"
                    )

            if not news_data['international'] and not news_data['domestic']:
                error_msg = "No news items fetched from RSS sources. Please check your network connection or RSS feed availability."
                logger.error(error_msg)
                raise Exception(error_msg)

            # Format news with unique IDs for selection
            formatted_news, news_items = self._format_news_with_ids(news_data)
            total_items = len(news_items)

            logger.info(f"Starting two-stage prompt chaining with {total_items} news items")

            # ============================================================
            # STAGE 1: Selection - Analyze and select 5-8 best items
            # ============================================================
            logger.info(f"Stage 1: Analyzing and selecting high-quality news items...")

            # Use provided template or load from config
            if stage1_template is None:
                from ..config import Config
                config = Config()
                stage1_template = config.stage1_prompt_template

            # Format Stage 1 prompt with placeholders
            selection_prompt = stage1_template.format(
                formatted_news=formatted_news,
                total_items=total_items
            )

            messages = [{"role": "user", "content": selection_prompt}]
            selection_response = self.provider.generate(
                messages=messages,
                max_tokens=4000 # give enough tokens for selection
            )

            # Parse selected IDs
            target_max_items = 8
            json_match = re.search(r'\[[\s\S]*?\]', selection_response)
            if not json_match:
                logger.warning("Could not parse JSON from selection response, using fallback")
                selected_ids = list(news_items.keys())[:target_max_items]
            else:
                try:
                    selected_ids = json.loads(json_match.group(0))
                    # Validate IDs
                    selected_ids = [id for id in selected_ids if id in news_items]

                    if not selected_ids:
                        logger.warning("No valid items selected, using fallback selection")
                        selected_ids = list(news_items.keys())[:target_max_items]
                    elif len(selected_ids) > target_max_items:
                        logger.warning(f"{len(selected_ids)} items selected, trimming to {target_max_items}")
                        selected_ids = selected_ids[:target_max_items]

                except json.JSONDecodeError:
                    logger.warning("JSON parse error, using fallback selection")
                    selected_ids = list(news_items.keys())[:target_max_items]

            selected_ids = self._filter_selection_to_allowed_items(
                selected_ids,
                news_items,
                target_max_items,
            )

            if len(selected_ids) < min_verified_items:
                raise Exception(
                    f"Only {len(selected_ids)} news items selected; minimum is {min_verified_items}"
                )

            logger.info(f"Stage 1 completed: Selected {len(selected_ids)} news items")
            logger.debug(f"Selected IDs: {selected_ids}")

            # ============================================================
            # STAGE 2: Summarization - Create detailed summaries
            # ============================================================
            logger.info(f"Stage 2: Creating detailed summaries for selected items...")

            # Use provided template or load from config
            if stage2_template is None:
                from ..config import Config
                config = Config()
                stage2_template = config.stage2_prompt_template

            # Format Stage 2 prompt with placeholders
            summarization_prompt = self._build_summarization_prompt(
                stage2_template,
                selected_ids,
                news_items,
                language,
            )

            # Execute Stage 2: Generate detailed summaries
            messages = [{"role": "user", "content": summarization_prompt}]
            response_text = self.provider.generate(
                messages=messages,
                max_tokens=max_tokens
            )


            if strict_verification:
                verification = self._verify_digest_against_sources(response_text, selected_ids, news_items)
                if not verification["passed"]:
                    unsupported_ids = set(verification["unsupported_news_ids"])
                    if verification_fail_policy.lower() == "skip" and unsupported_ids:
                        selected_ids = [news_id for news_id in selected_ids if news_id not in unsupported_ids]
                        if len(selected_ids) < min_verified_items:
                            raise Exception(
                                f"Digest verification removed too many items; {len(selected_ids)} remain, "
                                f"minimum is {min_verified_items}"
                            )
                        logger.warning(
                            f"Digest verification rejected {sorted(unsupported_ids)}; regenerating digest"
                        )
                        summarization_prompt = self._build_summarization_prompt(
                            stage2_template,
                            selected_ids,
                            news_items,
                            language,
                        )
                        response_text = self.provider.generate(
                            messages=[{"role": "user", "content": summarization_prompt}],
                            max_tokens=max_tokens
                        )
                        verification = self._verify_digest_against_sources(response_text, selected_ids, news_items)

                if not verification["passed"]:
                    raise Exception(f"Digest verification failed: {verification['reason']}")

            # Add footer with GitHub link
            footer = "\n\n---\n\n*Generated by [AI News Bot](https://github.com/giftedunicorn/ai-news-bot) - Your AI-powered news assistant*"
            response_text += footer

            logger.info("Stage 2 completed: News digest generated successfully")
            logger.info(f"Two-stage prompt chaining completed: {total_items} items → {len(selected_ids)} selected → full digest")
            logger.debug(f"Response length: {len(response_text)} characters")

            return response_text

        except Exception as e:
            logger.error(f"Failed to generate news digest from sources: {str(e)}", exc_info=True)
            raise
