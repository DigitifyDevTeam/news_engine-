"""
Enhanced scraping service with advanced detection and extraction capabilities.
Features: stealth mode, smart content detection, pattern recognition, performance optimization.
"""
import logging
import re
import random
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urljoin, urlparse

from django.utils import timezone
from core.utils import normalize_text
from core.exceptions import ScrapingError

logger = logging.getLogger(__name__)

# Enhanced path patterns for better article detection
SKIP_PATH_PARTS = {
    "tag", "tags", "author", "authors", "category", "categories", "login", "signup",
    "search", "newsletter", "feed", "rss", "comment", "comments", "share", "wp-login",
    "page", "page/", "archives", "archive", "attachment", "cart", "checkout", "account",
    "admin", "dashboard", "profile", "settings", "help", "support", "contact", "about",
    "privacy", "terms", "sitemap", "api", "json", "xml", "download", "file", "files",
}
# File extensions to skip (non-HTML content)
SKIP_FILE_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".rar", ".tar", ".gz", ".jpg", ".jpeg", ".png", ".gif",
    ".mp3", ".mp4", ".avi", ".mov", ".exe", ".dmg", ".iso"
}
# Enhanced article path hints
ARTICLE_PATH_HINTS = (
    "article", "articles", "blog", "post", "posts", "news", "actualite", "actualites", 
    "web", "story", "stories", "report", "analysis", "guide", "tutorial", "review",
    "update", "release", "announcement", "feature", "case-study", "case-studies", "insight"
)
# Content patterns that indicate articles
ARTICLE_TITLE_PATTERNS = [
    r'\b\d{4}\b.*\b\d{1,2}\b.*\b\d{1,2}\b',  # Date patterns
    r'\b(?:how|what|why|when|where|who)\b.*\b(?:to|for|of|in|on|with|by)\b',  # How-to/What articles
    r'\b(?:new|latest|recent|breaking|updated)\b.*\b(?:report|study|analysis|findings)\b',  # News patterns
    r'\b(?:top|best|ultimate|complete|comprehensive)\b.*\b(?:guide|list|review)\b',  # List/Guide patterns
]
MIN_PATH_SEGMENTS = 1
MAX_DISCOVER_LINKS = 100  # Increased for better coverage
MIN_ARTICLE_WORDS = 50   # Reduced to catch more articles
MAX_CONTENT_LENGTH = 50000  # Maximum content length to process

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/121.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
]

# Viewport sizes for rotation
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]

# Playwright: default timeouts (ms)
PLAYWRIGHT_NAV_TIMEOUT = 45000  # Increased from 30000
PLAYWRIGHT_DEFAULT_TIMEOUT = 35000  # Increased from 25000
PLAYWRIGHT_RETRY_TIMEOUT = 60000  # For problematic sites
# Common selectors for article body (tried in order)
ARTICLE_BODY_SELECTORS = [
    "article",
    "main",
    "[role='main']",
    ".article-body",
    ".post-content",
    ".entry-content",
    ".content-body",
    ".article-content",
    ".post-body",
    "main .content",
    "#content",
    ".content",
]
# Cookie/consent banner selectors (click to dismiss)
COOKIE_ACCEPT_SELECTORS = [
    "button:has-text('Accept')",
    "button:has-text('Accepter')",
    "button:has-text('OK')",
    "[data-accept-cookies]",
    ".cookie-accept",
    ".accept-cookies",
    "#accept-cookies",
    "[aria-label*='accept' i]",
]


def _same_domain(url: str, base: str) -> bool:
    try:
        return urlparse(url).netloc == urlparse(base).netloc
    except Exception:
        return False


def _looks_like_article_path(path: str) -> bool:
    """Heuristic: path looks like an article URL (not nav/listing)."""
    path = (path or "").strip().rstrip("/")
    if not path or path == "/":
        return False
    parts = [p for p in path.split("/") if p and p.strip()]
    if len(parts) < MIN_PATH_SEGMENTS:
        return False
    lower = path.lower()
    for skip in SKIP_PATH_PARTS:
        if f"/{skip}/" in lower or lower.startswith(f"{skip}/") or lower.endswith(f"/{skip}"):
            return False
    for hint in ARTICLE_PATH_HINTS:
        if hint in lower:
            return True
    # Date-like segment (e.g. /2025/02/10/slug)
    if re.search(r"/20\d{2}/\d{1,2}/", lower) or re.search(r"/\d{4}/\d{2}/", lower):
        return True
    # Long path with slug (e.g. /some-category/some-article-title)
    if len(parts) >= 2 and len(parts[-1]) > 15:
        return True
    return len(parts) >= 2


class ScrapingService:
    """Discovers article URLs from list pages and extracts full text per article."""

    def __init__(self):
        self._trafilatura = None
        self._playwright = None

    def _get_trafilatura(self):
        if self._trafilatura is None:
            import trafilatura
            self._trafilatura = trafilatura
        return self._trafilatura

    def _create_stealth_browser(self, playwright_instance):
        """Create browser with stealth configuration to avoid detection."""
        user_agent = random.choice(USER_AGENTS)
        viewport = random.choice(VIEWPORTS)
        
        browser = playwright_instance.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-images',  # Faster loading
                '--disable-javascript',  # Enable only when needed
                '--disable-default-apps',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-background-networking',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--metrics-recording-only',
                '--mute-audio',
                '--no-first-run',
                '--safebrowsing-disable-auto-update',
                '--disable-infobars',
                '--disable-logging',
                f'--user-agent={user_agent}'
            ]
        )
        
        context = browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            locale='en-US',
            timezone_id='America/New_York',
            permissions=[],
            ignore_https_errors=True,
            java_script_enabled=True
        )
        
        # Add stealth scripts
        context.add_init_script("""
            // Remove webdriver traces
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)
        
        return browser, context

    def _handle_cookie_consent(self, page):
        """Handle cookie consent banners automatically."""
        try:
            for selector in COOKIE_ACCEPT_SELECTORS:
                try:
                    button = page.wait_for_selector(selector, timeout=2000)
                    if button:
                        button.click()
                        time.sleep(0.5)
                        break
                except:
                    continue
        except Exception:
            pass

    def discover_article_urls(
        self,
        list_page_url: str,
        css_selector: str = "",
        max_links: int = MAX_DISCOVER_LINKS,
        wait_until: str = "load",
        wait_after_load_ms: int = 1500,
        scroll_to_load: bool = True,
    ) -> list[str]:
        """
        Enhanced URL discovery with stealth browser and pattern recognition.
        Finds article URLs using multiple strategies and heuristics.
        """
        from playwright.sync_api import sync_playwright

        parsed = urlparse(list_page_url)
        base_netloc = parsed.netloc

        urls = []
        seen = set()

        def normalize(href: str) -> str:
            if not href or href.startswith("#") or href.lower().startswith("javascript:"):
                return ""
            
            # Check for file extensions to skip
            href_lower = href.lower()
            for ext in SKIP_FILE_EXTENSIONS:
                if href_lower.endswith(ext):
                    return ""
            
            if not href.startswith("http"):
                href = urljoin(list_page_url, href)
            try:
                p = urlparse(href)
                if p.netloc != base_netloc:
                    return ""
                
                # Check file extension in full URL as well
                path_lower = p.path.lower()
                for ext in SKIP_FILE_EXTENSIONS:
                    if path_lower.endswith(ext):
                        return ""
                
                return href.split("#")[0].rstrip("/") or href
            except Exception:
                return ""

        def extract_links_with_text():
            """Extract links with their text for better analysis."""
            links_data = []
            try:
                if css_selector:
                    root = page.query_selector(css_selector)
                    elements = page.query_selector_all(f"{css_selector} a[href]") if root else page.query_selector_all("a[href]")
                else:
                    elements = page.query_selector_all("a[href]")
                
                for el in elements:
                    href = el.get_attribute("href")
                    text = el.inner_text().strip()
                    title = el.get_attribute("title") or ""
                    links_data.append({"href": href, "text": text, "title": title})
            except Exception as e:
                logger.warning("Link extraction failed: %s", e)
            return links_data

        def is_article_by_content(text: str, title: str) -> bool:
            """Check if content looks like an article based on text patterns."""
            combined = (text + " " + title).lower()
            
            # Check for article title patterns
            for pattern in ARTICLE_TITLE_PATTERNS:
                if re.search(pattern, combined, re.IGNORECASE):
                    return True
            
            # Check for article-like words
            article_words = [
                "how to", "guide", "tutorial", "review", "analysis", "report", "study",
                "breaking", "latest", "news", "update", "announcement", "feature",
                "case study", "research", "findings", "investigation", "exclusive"
            ]
            
            word_count = len(combined.split())
            if word_count < 3:
                return False
                
            return any(word in combined for word in article_words)

        try:
            with sync_playwright() as p:
                browser, context = self._create_stealth_browser(p)
                page = context.new_page()
                page.set_default_timeout(PLAYWRIGHT_DEFAULT_TIMEOUT)
                
                # Enhanced navigation with retry for DNS issues
                navigation_success = False
                for attempt in range(2):  # Try twice for DNS issues
                    try:
                        # Navigate with human-like behavior
                        page.goto(list_page_url, wait_until=wait_until, timeout=PLAYWRIGHT_NAV_TIMEOUT)
                        navigation_success = True
                        break
                    except Exception as nav_error:
                        if "net::ERR_NAME_NOT_RESOLVED" in str(nav_error) and attempt == 0:
                            logger.warning("DNS resolution failed, retrying in 3 seconds: %s", list_page_url)
                            time.sleep(3)
                            continue
                        else:
                            raise nav_error
                
                if not navigation_success:
                    raise ScrapingError(f"Navigation failed after retries: {list_page_url}")
                
                # Handle cookie consent
                self._handle_cookie_consent(page)
                
                # Wait for dynamic content
                if wait_after_load_ms:
                    time.sleep(wait_after_load_ms / 1000.0)
                
                # Scroll to load lazy content
                if scroll_to_load:
                    try:
                        for _ in range(3):
                            page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
                            time.sleep(random.uniform(0.5, 1.0))
                        page.evaluate("window.scrollTo(0, 0)")
                    except Exception:
                        pass
                
                # Extract links with content analysis
                links_data = extract_links_with_text()
                
                for link_data in links_data:
                    href = link_data["href"]
                    full = normalize(href)
                    if not full or full in seen:
                        continue
                    
                    path = urlparse(full).path
                    
                    # Multi-strategy article detection
                    is_article = False
                    
                    # Strategy 1: Path-based detection
                    if _looks_like_article_path(path):
                        is_article = True
                    
                    # Strategy 2: Content-based detection
                    if not is_article and is_article_by_content(link_data["text"], link_data["title"]):
                        is_article = True
                    
                    # Strategy 3: URL pattern detection
                    if not is_article:
                        # Check for date patterns in URL
                        if re.search(r'/\d{4}/\d{1,2}/\d{1,2}/', path) or re.search(r'/\d{4}/\d{2}/', path):
                            is_article = True
                        # Check for slug patterns
                        elif len(path.split('/')) >= 3 and len(path.split('/')[-1]) > 10:
                            is_article = True
                    
                    if is_article:
                        seen.add(full)
                        urls.append(full)
                        if len(urls) >= max_links:
                            break
                
                browser.close()
                
        except Exception as e:
            logger.warning("Enhanced discovery failed for %s: %s", list_page_url, e)
            raise ScrapingError(f"Discovery failed: {e}") from e

        return urls

    def scrape_url_with_playwright_enhanced(self, url: str, css_selector: str = "") -> Optional[dict]:
        """
        Enhanced Playwright scraping with smart content detection and multiple fallback strategies.
        """
        from playwright.sync_api import sync_playwright
        
        try:
            with sync_playwright() as p:
                browser, context = self._create_stealth_browser(p)
                page = context.new_page()
                page.set_default_timeout(PLAYWRIGHT_DEFAULT_TIMEOUT)
                
                # Navigate and handle consent
                page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_NAV_TIMEOUT)
                self._handle_cookie_consent(page)
                
                # Wait for dynamic content
                time.sleep(random.uniform(1.0, 2.0))
                
                title = page.title() or url
                
                # Multi-strategy content extraction
                content_text = None
                
                # Strategy 1: Use provided CSS selector
                if css_selector:
                    try:
                        element = page.query_selector(css_selector)
                        if element:
                            content_text = element.inner_text()
                    except Exception:
                        pass
                
                # Strategy 2: Try common article selectors
                if not content_text:
                    for selector in ARTICLE_BODY_SELECTORS:
                        try:
                            element = page.query_selector(selector)
                            if element:
                                text = element.inner_text()
                                if len(text.split()) >= MIN_ARTICLE_WORDS:
                                    content_text = text
                                    break
                        except Exception:
                            continue
                
                # Strategy 3: Get main content with readability-like approach
                if not content_text:
                    try:
                        # Remove unwanted elements
                        page.evaluate("""
                            // Remove navigation, ads, comments
                            const selectorsToRemove = [
                                'nav', 'header', 'footer', 'aside', '.sidebar', '.navigation',
                                '.menu', '.ads', '.advertisement', '.comments', '.social-share',
                                '.popup', '.modal', '.cookie-banner', '.newsletter', '.related'
                            ];
                            selectorsToRemove.forEach(sel => {
                                document.querySelectorAll(sel).forEach(el => el.remove());
                            });
                        """)
                        
                        # Try to get main content
                        main_selectors = ['main', 'article', '[role="main"]', '.content', '.article']
                        for selector in main_selectors:
                            try:
                                element = page.query_selector(selector)
                                if element:
                                    text = element.inner_text()
                                    if len(text.split()) >= MIN_ARTICLE_WORDS:
                                        content_text = text
                                        break
                            except Exception:
                                continue
                    except Exception:
                        pass
                
                # Strategy 4: Fallback to body content
                if not content_text:
                    try:
                        content_text = page.locator("body").inner_text()
                    except Exception:
                        content_text = ""
                
                browser.close()
                
        except Exception as e:
            logger.warning("Enhanced Playwright failed for %s: %s", url, e)
            raise ScrapingError(f"Playwright failed: {e}") from e
        
        if not content_text or not content_text.strip():
            return None
        
        raw_text = normalize_text(content_text)
        if len(raw_text.split()) < MIN_ARTICLE_WORDS:
            return None
        
        # Limit content length to prevent memory issues
        if len(raw_text) > MAX_CONTENT_LENGTH:
            raw_text = raw_text[:MAX_CONTENT_LENGTH] + "..."
        
        return {
            "url": url,
            "title": normalize_text(title)[:512],
            "raw_text": raw_text,
            "published_at": None,
        }

    def scrape_urls_batch(self, urls: List[str], strategy: str = "trafilatura", css_selector: str = "") -> List[dict]:
        """
        Batch scrape multiple URLs with performance optimizations.
        Reuses browser context for Playwright strategy.
        """
        results = []
        
        if strategy == "playwright":
            from playwright.sync_api import sync_playwright
            try:
                with sync_playwright() as p:
                    browser, context = self._create_stealth_browser(p)
                    
                    for i, url in enumerate(urls):
                        try:
                            page = context.new_page()
                            page.set_default_timeout(PLAYWRIGHT_DEFAULT_TIMEOUT)
                            
                            # Add human-like delay between requests
                            if i > 0:
                                time.sleep(random.uniform(1.0, 3.0))
                            
                            page.goto(url, wait_until="domcontentloaded", timeout=PLAYWRIGHT_NAV_TIMEOUT)
                            self._handle_cookie_consent(page)
                            time.sleep(random.uniform(0.5, 1.5))
                            
                            title = page.title() or url
                            
                            # Extract content using enhanced methods
                            content_text = None
                            
                            if css_selector:
                                try:
                                    element = page.query_selector(css_selector)
                                    if element:
                                        content_text = element.inner_text()
                                except Exception:
                                    pass
                            
                            if not content_text:
                                for selector in ARTICLE_BODY_SELECTORS:
                                    try:
                                        element = page.query_selector(selector)
                                        if element:
                                            text = element.inner_text()
                                            if len(text.split()) >= MIN_ARTICLE_WORDS:
                                                content_text = text
                                                break
                                    except Exception:
                                        continue
                            
                            if not content_text:
                                content_text = page.locator("body").inner_text()
                            
                            page.close()
                            
                            if content_text and content_text.strip():
                                raw_text = normalize_text(content_text)
                                if len(raw_text.split()) >= MIN_ARTICLE_WORDS:
                                    if len(raw_text) > MAX_CONTENT_LENGTH:
                                        raw_text = raw_text[:MAX_CONTENT_LENGTH] + "..."
                                    
                                    results.append({
                                        "url": url,
                                        "title": normalize_text(title)[:512],
                                        "raw_text": raw_text,
                                        "published_at": None,
                                    })
                        
                        except Exception as e:
                            logger.warning("Batch scrape failed for %s: %s", url, e)
                            continue
                    
                    browser.close()
                    
            except Exception as e:
                logger.error("Batch Playwright scraping failed: %s", e)
        
        else:
            # Fallback to individual Trafilatura scraping
            for url in urls:
                try:
                    data = self.scrape_url_with_trafilatura(url)
                    if data:
                        results.append(data)
                except Exception as e:
                    logger.warning("Batch Trafilatura failed for %s: %s", url, e)
                    continue
        
        return results

    def scrape_url_with_trafilatura(self, url: str) -> Optional[dict]:
        """Fetch URL and extract main content with Trafilatura. Returns dict with url, title, raw_text, published_at or None."""
        import requests

        trafilatura = self._get_trafilatura()
        try:
            resp = requests.get(
                url,
                timeout=25,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NewsEngine/2.0; +https://github.com/news-engine)"},
            )
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            logger.warning("Fetch failed for %s: %s", url, e)
            raise ScrapingError(f"Fetch failed: {e}") from e

        try:
            doc = trafilatura.extract(html, output_format="txt", include_links=False)
            meta = trafilatura.extract_metadata(html)
        except Exception as e:
            logger.warning("Extract failed for %s: %s", url, e)
            return None

        if not doc or not doc.strip():
            return None

        raw_text = normalize_text(doc)
        if len(raw_text.split()) < MIN_ARTICLE_WORDS:
            return None

        title = (meta and meta.title) or url
        date = None
        if meta and meta.date:
            try:
                date = meta.date if isinstance(meta.date, datetime) else None
            except Exception:
                pass

        return {
            "url": url,
            "title": normalize_text(title)[:512],
            "raw_text": raw_text,
            "published_at": date,
        }

    def _dismiss_cookie_banner(self, page) -> None:
        """Try to click common cookie/consent accept buttons so they don't obscure content."""
        for selector in COOKIE_ACCEPT_SELECTORS:
            try:
                loc = page.locator(selector)
                if loc.count() > 0:
                    loc.first.click(timeout=2000)
                    time.sleep(0.5)
                    return
            except Exception:
                continue

    def _scrape_url_with_playwright_page(
        self,
        page,
        url: str,
        content_selector: str = "",
        wait_until: str = "load",
    ) -> Optional[dict]:
        """
        Use an existing Playwright page to load url and extract content.
        Tries Trafilatura on rendered HTML first, then falls back to inner_text on article/main/body.
        """
        try:
            page.goto(url, wait_until=wait_until, timeout=PLAYWRIGHT_NAV_TIMEOUT)
            time.sleep(0.5)
            self._dismiss_cookie_banner(page)
            time.sleep(0.3)
        except Exception as e:
            logger.warning("Playwright goto failed for %s: %s", url, e)
            raise ScrapingError(f"Playwright failed: {e}") from e

        html = page.content()
        result = self._extract_with_trafilatura_from_html(html, url)
        if result:
            return result

        selectors = [content_selector] if content_selector else ARTICLE_BODY_SELECTORS
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    text = loc.first.inner_text(timeout=3000)
                    if text and len(text.strip().split()) >= MIN_ARTICLE_WORDS:
                        raw = normalize_text(text)
                        title = page.title() or url
                        return {
                            "url": url,
                            "title": normalize_text(title)[:512],
                            "raw_text": raw,
                            "published_at": None,
                        }
            except Exception:
                continue
        try:
            text = page.locator("body").inner_text(timeout=3000)
            if text and len(text.strip().split()) >= MIN_ARTICLE_WORDS:
                raw = normalize_text(text)
                return {
                    "url": url,
                    "title": (page.title() or url)[:512],
                    "raw_text": raw,
                    "published_at": None,
                }
        except Exception:
            pass
        return None

    def scrape_url_with_playwright(
        self,
        url: str,
        css_selector: str = "",
        content_selector: str = "",
        wait_until: str = "load",
    ) -> Optional[dict]:
        """
        Fetch URL with Playwright and extract content.
        Uses Trafilatura on rendered HTML when possible; falls back to article/main/body inner_text.
        """
        pw = self._get_playwright()
        playwright_instance = pw.start()
        try:
            browser = playwright_instance.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(PLAYWRIGHT_DEFAULT_TIMEOUT)
            out = self._scrape_url_with_playwright_page(
                page, url,
                content_selector=content_selector or css_selector,
                wait_until=wait_until,
            )
            browser.close()
            return out
        finally:
            playwright_instance.stop()

    def scrape_source(self, source) -> list:
        """
        Enhanced scraping flow with comprehensive error handling and retry mechanisms.
        1) Discover article URLs via stealth Playwright with pattern recognition
        2) Batch process URLs with optimized browser reuse
        3) Multiple fallback strategies for content extraction
        4) Intelligent retry with exponential backoff
        """
        from articles.models import Article as ArticleModel
        from sources.models import Source as SourceModel

        if not isinstance(source, SourceModel):
            source = SourceModel.objects.get(pk=source)

        url = source.url
        config = source.config or {}
        discover = config.get("discover_articles", True)
        max_articles = min(config.get("max_articles", MAX_DISCOVER_LINKS), 100)  # Increased limit
        css_selector = (source.css_selector or "").strip()
        content_selector = (config.get("content_selector") or "").strip()
        wait_until = config.get("wait_until", "load")
        wait_after_load_ms = config.get("wait_after_load_ms", 1500)
        scroll_to_load = config.get("scroll_to_load", True)
        max_retries = config.get("max_retries", 3)
        retry_delay = config.get("retry_delay", 2)

        article_urls = []
        
        # Enhanced URL discovery with retry
        if discover:
            for attempt in range(max_retries):
                try:
                    article_urls = self.discover_article_urls(
                        url,
                        css_selector=css_selector,
                        max_links=max_articles,
                        wait_until=wait_until,
                        wait_after_load_ms=wait_after_load_ms,
                        scroll_to_load=scroll_to_load,
                    )
                    logger.info("Discovered %d article URLs from %s (attempt %d)", len(article_urls), url, attempt + 1)
                    break
                except ScrapingError as e:
                    logger.warning("Discovery attempt %d failed for %s: %s", attempt + 1, url, e)
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
                    else:
                        logger.error("All discovery attempts failed for %s", url)
                        article_urls = []
                except Exception as e:
                    logger.warning("Discovery failed with unexpected error, falling back to single URL: %s", e)
                    article_urls = [url]
                    break
        else:
            article_urls = [url]

        if not article_urls:
            logger.warning("No article URLs for %s", url)
            source.last_scraped_at = timezone.now()
            source.save(update_fields=["last_scraped_at", "updated_at"])
            return []

        created_or_updated = []
        strategy = source.scrape_strategy
        
        # Enhanced batch processing with error handling
        if strategy == "playwright":
            # Use enhanced batch processing for better performance
            batch_size = 10  # Process in batches to avoid memory issues
            for i in range(0, len(article_urls), batch_size):
                batch_urls = article_urls[i:i + batch_size]
                
                for attempt in range(max_retries):
                    try:
                        results = self.scrape_urls_batch(
                            batch_urls, 
                            strategy="playwright", 
                            css_selector=content_selector
                        )
                        
                        # Process results with duplicate checking
                        for data in results:
                            if not data:
                                continue
                                
                            # Check for duplicates from same source before saving
                            duplicate_article = ArticleModel.objects.filter(
                                source=source,
                                title__iexact=data["title"]
                            ).first()
                            
                            if duplicate_article:
                                logger.info(
                                    "Skipping duplicate article '%s' from source %s (existing ID: %d)",
                                    data["title"][:50], source.name, duplicate_article.pk
                                )
                                continue  # Skip this duplicate article
                            
                            # No duplicate found, proceed with saving
                            try:
                                word_count = len(data["raw_text"].split())
                                obj, _ = ArticleModel.objects.update_or_create(
                                    url=data["url"],
                                    defaults={
                                        "source": source,
                                        "title": data["title"],
                                        "raw_text": data["raw_text"],
                                        "published_at": data.get("published_at"),
                                        "word_count": word_count,
                                        "processing_status": ArticleModel.STATUS_PENDING,
                                    },
                                )
                                created_or_updated.append(obj)
                            except Exception as e:
                                logger.error("Failed to save article %s: %s", data.get("url", "unknown"), e)
                        
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        logger.warning("Batch processing attempt %d failed: %s", attempt + 1, e)
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))
                        else:
                            logger.error("All batch processing attempts failed for batch %d-%d", i, i + batch_size)
                            

                # Add delay between batches to be respectful
                if i + batch_size < len(article_urls):
                    time.sleep(random.uniform(2.0, 5.0))
        
        else:
            # Enhanced individual processing with retry
            for art_url in article_urls:
                success = False
                for attempt in range(max_retries):
                    try:
                        # Alternate between strategies for better success rate
                        if attempt % 2 == 0:
                            data = self.scrape_url_with_trafilatura(art_url)
                        else:
                            data = self.scrape_url_with_playwright_enhanced(art_url, content_selector)
                        
                        if data:
                            # Check for duplicates from same source before saving
                            duplicate_article = ArticleModel.objects.filter(
                                source=source,
                                title__iexact=data["title"]
                            ).first()
                            
                            if duplicate_article:
                                logger.info(
                                    "Skipping duplicate article '%s' from source %s (existing ID: %d)",
                                    data["title"][:50], source.name, duplicate_article.pk
                                )
                                success = True
                                break
                            
                            # No duplicate found, proceed with saving
                            word_count = len(data["raw_text"].split())
                            obj, _ = ArticleModel.objects.update_or_create(
                                url=data["url"],
                                defaults={
                                    "source": source,
                                    "title": data["title"],
                                    "raw_text": data["raw_text"],
                                    "published_at": data.get("published_at"),
                                    "word_count": word_count,
                                    "processing_status": ArticleModel.STATUS_PENDING,
                                },
                            )
                            created_or_updated.append(obj)
                            success = True
                            break
                        
                    except ScrapingError as e:
                        logger.warning("Scraping attempt %d failed for %s: %s", attempt + 1, art_url, e)
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay * (2 ** attempt))
                    except Exception as e:
                        logger.warning("Unexpected error scraping %s: %s", art_url, e)
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                
                if not success:
                    logger.warning("All scraping attempts failed for %s", art_url)
                
                # Human-like delay between requests
                time.sleep(random.uniform(1.0, 3.0))

        # Update source with enhanced metadata
        source.last_scraped_at = timezone.now()
        source.save(update_fields=["last_scraped_at", "updated_at"])
        
        logger.info(
            "Scraping completed for %s: %d articles processed, %d created/updated", 
            url, len(article_urls), len(created_or_updated)
        )
        
        return created_or_updated
