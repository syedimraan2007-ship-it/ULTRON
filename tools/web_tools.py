from base64 import urlsafe_b64decode
from html.parser import HTMLParser
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urlsplit
from urllib.request import Request, urlopen
import webbrowser


REQUEST_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 1_000_000
MAX_TEXT_CHARS = 3_000
USER_AGENT = "ULTRON/1.0 (local assistant; public web page reader)"
SEARCH_URL = "https://www.bing.com/search?q="
MAX_SEARCH_RESPONSE_BYTES = 500_000
SEARCH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "find",
    "give",
    "information",
    "latest",
    "official",
    "search",
    "specification",
    "specifications",
    "specs",
    "tell",
    "the",
    "urls",
    "web",
    "website",
    "what",
}
PREFERRED_SOURCE_DOMAINS = {
    "apple.com",
    "arxiv.org",
    "developer.mozilla.org",
    "docs.python.org",
    "github.com",
    "learn.microsoft.com",
    "microsoft.com",
    "nasa.gov",
    "nvidia.com",
    "python.org",
    "stackoverflow.com",
    "wikipedia.org",
}


class _ReadableTextParser(HTMLParser):
    """Extract visible text from a small HTML document."""

    _IGNORED_TAGS = {"script", "style", "noscript", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


class _SearchResultsParser(HTMLParser):
    """Extract result links and snippets from a search-results page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._active_field: str | None = None
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())

        if (
            tag == "div" and "result" in classes
        ) or (tag == "li" and "b_algo" in classes):
            if self._current and self._current.get("url"):
                self.results.append(self._current)
            self._current = {}
            self._active_field = None
            return

        if self._current is None:
            return

        if tag == "a" and ("result__a" in classes or not self._current.get("url")):
            href = attributes.get("href")
            if href:
                self._current["url"] = self._result_url(href)
                self._active_field = "title"
                return

        if "result__snippet" in classes or "b_caption" in classes:
            self._active_field = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "template"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return

        if self._ignored_depth:
            return

        if tag in {"a", "span"}:
            self._active_field = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth or self._current is None or self._active_field is None:
            return

        value = " ".join(data.split())
        if value:
            self._current[self._active_field] = (
                f"{self._current.get(self._active_field, '')} {value}"
            ).strip()

    @staticmethod
    def _result_url(href: str) -> str:
        if href.startswith("//"):
            href = f"https:{href}"

        parsed = urlsplit(href)
        if parsed.netloc.endswith("bing.com") and parsed.path == "/ck/a":
            encoded_url = parse_qs(parsed.query).get("u", [""])[0]

            if encoded_url.startswith("a1"):
                try:
                    padding = "=" * (-len(encoded_url[2:]) % 4)
                    decoded_url = urlsafe_b64decode(
                        encoded_url[2:] + padding
                    ).decode("utf-8")

                    if decoded_url.startswith(("http://", "https://")):
                        return decoded_url
                except (UnicodeDecodeError, ValueError):
                    pass

        if parsed.netloc and parsed.path.endswith("/l/"):
            encoded_url = parse_qs(parsed.query).get("uddg", [""])[0]
            return unquote(encoded_url)

        return href

    def finish(self) -> None:
        if self._current and self._current.get("url"):
            self.results.append(self._current)


def _validated_url(url: str) -> str | None:
    if not isinstance(url, str) or not url.strip():
        return None

    candidate = url.strip()

    try:
        parsed = urlsplit(candidate)
        parsed.port
    except ValueError:
        return None

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None

    return candidate


def web_fetch(url: str) -> str:
    """Fetch readable content from a public HTTP or HTTPS webpage."""

    validated_url = _validated_url(url)

    if validated_url is None:
        if not isinstance(url, str) or not url.strip():
            return "No URL was provided."

        return "Only valid public HTTP and HTTPS webpage URLs are allowed."

    request = Request(
        validated_url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            final_url = _validated_url(response.geturl())

            if final_url is None:
                return "The webpage redirected to an invalid or unsupported URL."

            content_type = response.headers.get_content_type()

            if content_type not in {
                "text/html",
                "text/plain",
                "application/xhtml+xml",
            }:
                return (
                    "Unsupported webpage content type: "
                    f"{content_type}. Only HTML and plain text are supported."
                )

            content = response.read(MAX_RESPONSE_BYTES + 1)

    except HTTPError as exc:
        return f"Could not retrieve webpage: HTTP {exc.code} {exc.reason}."
    except (TimeoutError, URLError, OSError) as exc:
        return f"Could not retrieve webpage: {exc}."

    response_was_truncated = len(content) > MAX_RESPONSE_BYTES
    if response_was_truncated:
        content = content[:MAX_RESPONSE_BYTES]

    charset = response.headers.get_content_charset() or "utf-8"
    text = content.decode(charset, errors="replace")

    if content_type in {"text/html", "application/xhtml+xml"}:
        parser = _ReadableTextParser()
        parser.feed(text)
        text = " ".join(parser.parts)

    text = " ".join(text.split())

    if not text:
        return "The webpage did not contain readable text content."

    text_was_truncated = len(text) > MAX_TEXT_CHARS
    text = text[:MAX_TEXT_CHARS].rstrip()

    if response_was_truncated or text_was_truncated:
        text += "\n\n[Content truncated at the safe response limit.]"

    return f"Retrieved webpage content from {final_url}:\n{text}"


def open_search_results(query: str) -> str:
    """Open Google search results for a natural-language query."""

    if not isinstance(query, str) or not query.strip():
        return "No search query was provided."

    search_url = (
        "https://www.google.com/search?q="
        f"{quote_plus(query.strip())}"
    )

    try:
        opened = webbrowser.open(search_url)

        if opened:
            return f"Opened web search for '{query.strip()}'."

        return "Could not open the web search in the default browser."

    except Exception as exc:
        return f"Could not open the web search: {exc}"


def _search_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in SEARCH_STOP_WORDS and len(token) > 1
    }


def _domain_matches(domain: str, preferred_domain: str) -> bool:
    return domain == preferred_domain or domain.endswith(f".{preferred_domain}")


def _search_result_score(
    result: dict[str, str],
    query_tokens: set[str],
    query_phrase: str,
) -> tuple[int, int]:
    title = result["title"].lower()
    snippet = result["snippet"].lower()
    parsed_url = urlsplit(result["url"])
    domain = (parsed_url.hostname or "").lower().removeprefix("www.")
    domain_tokens = _search_tokens(domain.replace(".", " "))
    title_tokens = _search_tokens(title)
    snippet_tokens = _search_tokens(snippet)

    title_matches = query_tokens & title_tokens
    snippet_matches = query_tokens & snippet_tokens
    domain_matches = query_tokens & domain_tokens
    matched_tokens = title_matches | snippet_matches | domain_matches

    relevance = (
        len(title_matches) * 5
        + len(snippet_matches) * 2
        + len(domain_matches) * 4
    )

    if query_phrase in title or query_phrase in snippet:
        relevance += 8

    quality = 0
    if any(_domain_matches(domain, preferred) for preferred in PREFERRED_SOURCE_DOMAINS):
        quality += 8
    if domain.endswith((".gov", ".gov.uk", ".edu", ".edu.au")):
        quality += 3
    if domain.startswith(("docs.", "developer.", "support.", "learn.")):
        quality += 2
    if parsed_url.scheme == "https":
        quality += 1

    if query_tokens and not matched_tokens:
        return (0, quality)

    return (relevance + quality, relevance)


def web_search(query: str) -> str:
    """Return up to five clean search results for a natural-language query."""

    if not isinstance(query, str) or not query.strip():
        return "No search query was provided."

    clean_query = query.strip()
    request = Request(
        f"{SEARCH_URL}{quote_plus(clean_query)}",
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            if response.headers.get_content_type() != "text/html":
                return "Search results were unavailable: the response was not HTML."

            content = response.read(MAX_SEARCH_RESPONSE_BYTES)
            charset = response.headers.get_content_charset() or "utf-8"
            html = content.decode(charset, errors="replace")

    except HTTPError as exc:
        return f"Search results were unavailable: HTTP {exc.code} {exc.reason}."
    except (TimeoutError, URLError, OSError) as exc:
        return f"Search results were unavailable: {exc}."

    parser = _SearchResultsParser()

    try:
        parser.feed(html)
        parser.finish()
    except Exception as exc:
        return f"Search results could not be parsed: {exc}."

    query_phrase = " ".join(clean_query.lower().split())
    query_tokens = _search_tokens(clean_query)
    scored_results: list[tuple[tuple[int, int], dict[str, str]]] = []

    for result in parser.results:
        title = " ".join(result.get("title", "").split())
        result_url = _validated_url(result.get("url", ""))
        snippet = " ".join(result.get("snippet", "").split())

        if not title or result_url is None:
            continue

        clean_result = {
            "title": title,
            "url": result_url,
            "snippet": snippet or "No description available.",
        }
        score = _search_result_score(
            clean_result,
            query_tokens,
            query_phrase,
        )
        if score[0] > 0:
            scored_results.append((score, clean_result))

    scored_results.sort(key=lambda item: item[0], reverse=True)
    results = [result for _, result in scored_results[:5]]

    if not results:
        fallback_query = " ".join(
            token
            for token in re.findall(r"[a-z0-9]+", clean_query.lower())
            if token not in SEARCH_STOP_WORDS
        )

        if fallback_query and fallback_query != clean_query.lower():
            return web_search(fallback_query)

        return "Search results were unavailable or could not be parsed."

    lines = [f"Search results for '{clean_query}':"]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"{index}. {result['title']}",
                f"URL: {result['url']}",
                f"Snippet: {result['snippet']}",
            ]
        )

    return "\n".join(lines)