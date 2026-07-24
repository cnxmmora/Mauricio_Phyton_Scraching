import asyncio
import json
import os
import random
import re
from pathlib import Path
from typing import Any, AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urldefrag, urljoin, urlparse, urlunparse
from uuid import NAMESPACE_URL, UUID, uuid5

import aiofiles
import aiofiles.os
from curl_cffi.requests import AsyncSession
from selectolax.parser import HTMLParser, Node

from regulation_scraper.schemas.regulation import (
    RegulationItem,
    RegulationUnit,
    RegulationSection,
    RegulationStatus,
)
from regulation_scraper.scrapers.regulation_scraper import RegulationScraper

_SEED = "https://govt.westlaw.com/nycrr/Browse/Home/NewYork/UnofficialNewYorkCodesRulesandRegulations?guid=I51dc5680ac3d11dd9f72c1eb90efe723&originationContext=documenttoc&transitionType=Default&contextData=(sc.Default)"
_SITE_LIST = "https://govt.westlaw.com/SiteList"
_NYCRR_INDEX = "https://govt.westlaw.com/nycrr/Index"
_TITLE_15_NAME = "Title 15 Department of Motor Vehicles"
_TITLE_15_PREFIX = "title 15"
_SHORT_NAMES = {
    "Title": "T.",
    "Subtitle": "Subt.",
    "Chapter": "Ch.",
    "Subchapter": "Subch.",
    "Part": "Pt.",
    "Subpart": "Subpt.",
    "Article": "Art.",
}
_DECOMPOSE = [
    ".co_genericBoxContent",
    "#co_endOfDocument",
    "#co_documentNavigation",
    "script",
    "style",
]
_MAX_TRANSIENT_RETRIES = 3
_REQUEST_TIMEOUTS = (25, 45, 70, 100)
_MAX_PAGE_ATTEMPTS = 5
_TRANSIENT_STATUS_CODES = {403, 408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}
_SECTIONS_JSONL_ENV = "WESTLAW_SECTIONS_JSONL"
_UNITS_JSONL_ENV = "WESTLAW_UNITS_JSONL"
_STRIP_QUERY_KEYS = {
    "bhjs",
    "bhqs",
    "bhcp",
    "bhhash",
    "bhab",
    "bhav",
    "bhov",
    "__cf_chl_tk",
    "__cf_chl_f_tk",
    "__cf_chl_rt_tk",
}
_BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
    "sec-ch-ua-arch": '"x86"',
    "sec-ch-ua-bitness": '"64"',
    "sec-ch-ua-full-version": '"150.0.7871.182"',
    "sec-ch-ua-full-version-list": '"Not;A=Brand";v="8.0.0.0", "Chromium";v="150.0.7871.182", "Google Chrome";v="150.0.7871.182"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-model": '""',
    "sec-ch-ua-platform": '"Windows"',
    "sec-ch-ua-platform-version": '"19.0.0"',
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
}


class NewYork(RegulationScraper):
    def __init__(self, cache_dir=None) -> None:
        super().__init__(cache_dir=cache_dir)
        self._session: AsyncSession | None = None
        self._headers = self._build_headers()
        self._request_delay = _env_float("WESTLAW_REQUEST_DELAY", 0.35)

    def _build_headers(self) -> dict[str, str]:
        headers = dict(_BASE_HEADERS)

        user_agent = os.getenv("WESTLAW_USER_AGENT", "").strip()
        if user_agent:
            headers["User-Agent"] = user_agent

        accept_language = os.getenv("WESTLAW_ACCEPT_LANGUAGE", "").strip()
        if accept_language:
            headers["Accept-Language"] = accept_language

        referer = os.getenv("WESTLAW_REFERER", "").strip()
        if referer:
            headers["Referer"] = referer

        cookie = os.getenv("WESTLAW_COOKIE", "").strip()
        if cookie:
            headers["Cookie"] = cookie

        return headers

    def _get_session(self) -> AsyncSession:
        if self._session is None:
            self._session = AsyncSession()
        return self._session

    async def _reset_session(self) -> None:
        if self._session is None:
            return

        close_result = self._session.close()
        if hasattr(close_result, "__await__"):
            await close_result
        self._session = None

    @staticmethod
    def _is_cloudflare_challenge(status_code: int, headers: dict[str, str], body: str) -> bool:
        if status_code == 403 and headers.get("cf-mitigated") == "challenge":
            return True

        body_lower = body.lower()
        return (
            "cf-challenge" in body_lower
            or "challenge-platform" in body_lower
            or "just a moment" in body_lower
            or "checking your browser" in body_lower
        )

    @staticmethod
    def _can_retry(attempt: int) -> bool:
        return attempt < _MAX_PAGE_ATTEMPTS

    @staticmethod
    async def _sleep_backoff(attempt: int) -> None:
        await asyncio.sleep(min(2 ** attempt, 10))

    async def _attempt_fetch(self, url: str, timeout_seconds: int) -> tuple[Any | None, Exception | None]:
        try:
            session = self._get_session()
            response = await session.get(
                url=url,
                impersonate="chrome",
                headers=self._headers,
                timeout=timeout_seconds,
            )
            return response, None
        except Exception as e:
            return None, e

    def _response_error(self, response: Any, url: str) -> Exception | None:
        response_text = response.text or ""
        if self._is_cloudflare_challenge(
            response.status_code,
            dict(response.headers),
            response_text,
        ):
            return RuntimeError("Cloudflare challenge detectado durante fetch.")

        if response.status_code in _TRANSIENT_STATUS_CODES:
            return RuntimeError(f"Estado transitorio {response.status_code} para {url}")

        return None

    async def _resolve_seed(self) -> str:
        forced = os.getenv("WESTLAW_SEED_URL", "").strip()
        if forced:
            return _normalize_westlaw_url(forced)

        site_list = os.getenv("WESTLAW_SITE_LIST_URL", _SITE_LIST).strip() or _SITE_LIST
        nycrr_index_url = os.getenv("WESTLAW_NYCRR_INDEX_URL", _NYCRR_INDEX).strip()

        try:
            site_list_page = await self.page(site_list)
            discovered = self._discover_nycrr_index(site_list_page, site_list)
            if discovered:
                nycrr_index_url = discovered
        except Exception:
            # Fallback to the known NYCRR index URL when SiteList is blocked.
            nycrr_index_url = nycrr_index_url or _NYCRR_INDEX

        nycrr_index_page = await self.page(nycrr_index_url)
        browse_seed = self._discover_browse_seed(nycrr_index_page, nycrr_index_url)
        if browse_seed:
            return browse_seed

        return _normalize_westlaw_url(_SEED)

    @staticmethod
    def _discover_nycrr_index(page: Node, page_url: str) -> str | None:
        anchors = page.css("a[href]")
        for anchor in anchors:
            href = (anchor.attrs.get("href") or "").strip()
            if not href:
                continue

            full_url = urldefrag(urljoin(page_url, href)).url
            if "/nycrr/Index" in full_url:
                return full_url

            name = _clean_text(anchor.text(deep=True)).lower()
            if "unofficial new york codes, rules and regulations" in name:
                return full_url

        return None

    @staticmethod
    def _discover_browse_seed(page: Node, page_url: str) -> str | None:
        anchors = page.css("a[href]")
        for anchor in anchors:
            href = (anchor.attrs.get("href") or "").strip()
            if not href:
                continue

            full_url = urldefrag(urljoin(page_url, href)).url
            if (
                "/nycrr/Browse/Home/NewYork/UnofficialNewYorkCodesRulesandRegulations"
                in full_url
            ):
                name = _clean_text(anchor.text(deep=True)).lower()
                if "title 15" in name or "department of motor vehicles" in name:
                    return full_url

        # Do not fallback to the first browse link because some sessions land on a
        # deep page (e.g. Part 79). Returning None lets _resolve_seed use _SEED
        # which is pinned to Title 15.
        return None

    async def page(self, url: str) -> Node:
        url = _normalize_westlaw_url(url)
        cache_path = self._cache / f"{uuid5(NAMESPACE_URL, url)}.html"
        cache_only = os.getenv("WESTLAW_CACHE_ONLY", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if await aiofiles.os.path.exists(cache_path):
            async with aiofiles.open(cache_path, mode="r", encoding="utf-8", errors="ignore") as f:
                return HTMLParser(await f.read()).root

        if cache_only:
            raise RuntimeError(
                "WESTLAW_CACHE_ONLY esta activo y no existe cache para la URL: "
                f"{url} (esperado: {cache_path})"
            )

        response_text = await self._download_page_text(url)

        await aiofiles.os.makedirs(cache_path.parent, exist_ok=True)
        async with aiofiles.open(cache_path, mode="w", encoding="utf-8") as f:
            await f.write(response_text)

        return HTMLParser(response_text).root

    async def _download_page_text(self, url: str) -> str:

        last_error: Exception | None = None
        for attempt in range(1, _MAX_PAGE_ATTEMPTS + 1):
            timeout_seconds = _REQUEST_TIMEOUTS[min(attempt - 1, len(_REQUEST_TIMEOUTS) - 1)]

            if self._request_delay > 0:
                await asyncio.sleep(self._request_delay + random.uniform(0.0, 0.25))

            response, fetch_error = await self._attempt_fetch(url, timeout_seconds)
            if fetch_error is not None:
                last_error = fetch_error
                await self._reset_session()
                if self._can_retry(attempt):
                    await self._sleep_backoff(attempt)
                    continue
                break

            assert response is not None
            response_error = self._response_error(response, url)
            if response_error is not None:
                last_error = response_error
                await self._reset_session()
                if self._can_retry(attempt):
                    await self._sleep_backoff(attempt)
                    continue
                break

            response.raise_for_status()

            return response.text or ""

        assert last_error is not None
        raise last_error

    async def regulations(self) -> AsyncGenerator[RegulationItem]:
        sections_manifest = _env_path(_SECTIONS_JSONL_ENV)
        if sections_manifest:
            async for item in self._regulations_from_manifest(sections_manifest):
                yield item
            return

        seen_hierarchy: set[str] = set()
        seen_sections: set[str] = set()
        hierarchy_attempts: dict[str, int] = {}
        seed = await self._resolve_seed()
        stack: list[tuple[str, list[str]]] = [(seed, [_TITLE_15_NAME])]

        try:
            while stack:
                page_url, hierarchy = stack.pop()
                if page_url in seen_hierarchy:
                    continue

                try:
                    page = await self.page(page_url)
                except Exception:
                    attempt = hierarchy_attempts.get(page_url, 0) + 1
                    hierarchy_attempts[page_url] = attempt
                    if attempt <= _MAX_TRANSIENT_RETRIES:
                        # Requeue transient failures to improve coverage.
                        stack.append((page_url, hierarchy))
                    continue

                seen_hierarchy.add(page_url)
                browse_children, section_children = self._partition_children(
                    self._children(page, page_url)
                )

                if self._is_unit_candidate(browse_children, section_children):
                    unit = _reg_unit(page_url, hierarchy)
                    yield unit
                    async for section in self._iter_sections(
                        unit.id,
                        section_children,
                        seen_sections,
                    ):
                        yield section

                if browse_children:
                    self._push_children(stack, hierarchy, browse_children)
        finally:
            await self._reset_session()

    async def _regulations_from_manifest(
        self,
        sections_manifest: Path,
    ) -> AsyncGenerator[RegulationItem]:
        units_manifest = _env_path(_UNITS_JSONL_ENV) or _infer_units_manifest(sections_manifest)
        units_by_id = _load_units_manifest(units_manifest)
        sections = _load_sections_manifest(sections_manifest)

        emitted_units: set[UUID] = set()
        for section in sections:
            unit_id = section["unit_id"]
            if unit_id not in emitted_units:
                unit = units_by_id.get(unit_id)
                if unit is None:
                    unit = RegulationUnit(
                        id=unit_id,
                        state="New York",
                        link=section["link"],
                        external_reference_id=f"Unit {unit_id}",
                        name=f"Unit {unit_id}",
                        status=RegulationStatus.UNKNOWN,
                        hierarchy=["Title 15 Department of Motor Vehicles"],
                    )
                emitted_units.add(unit_id)
                yield unit

            page = await self.page(section["link"])
            yield self._section(
                page,
                section["link"],
                unit_id,
                section["index"],
                section["name"],
            )

    @staticmethod
    def _partition_children(
        children: list[tuple[str, str, str]],
    ) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
        browse_children = [child for child in children if child[0] == "browse"]
        section_children = [child for child in children if child[0] == "document"]
        return browse_children, section_children

    @staticmethod
    def _is_unit_candidate(
        browse_children: list[tuple[str, str, str]],
        section_children: list[tuple[str, str, str]],
    ) -> bool:
        return bool(section_children)

    @staticmethod
    def _is_hierarchy_candidate(
        browse_children: list[tuple[str, str, str]],
        section_children: list[tuple[str, str, str]],
    ) -> bool:
        return bool(browse_children) and not section_children

    @staticmethod
    def _push_children(
        stack: list[tuple[str, list[str]]],
        hierarchy: list[str],
        browse_children: list[tuple[str, str, str]],
    ) -> None:
        # LIFO stack + reverse keeps traversal close to on-page ordering.
        for _, child_name, child_url in reversed(browse_children):
            # Keep traversal constrained to Title 15 and skip cross-title links.
            if child_name.lower().startswith("title ") and not child_name.lower().startswith(
                _TITLE_15_PREFIX
            ):
                continue
            stack.append((child_url, [*hierarchy, child_name]))

    async def _iter_sections(
        self,
        unit_id: UUID,
        section_children: list[tuple[str, str, str]],
        seen_sections: set[str],
    ) -> AsyncGenerator[RegulationSection]:
        section_idx = 0
        pending: list[tuple[str, str, int]] = [
            (section_name, section_url, 1)
            for _, section_name, section_url in section_children
        ]

        while pending:
            section_name, section_url, attempt = pending.pop(0)
            if section_url in seen_sections:
                continue

            try:
                section_page = await self.page(section_url)
            except Exception:
                if attempt <= _MAX_TRANSIENT_RETRIES:
                    pending.append((section_name, section_url, attempt + 1))
                continue

            seen_sections.add(section_url)
            section_idx += 1
            yield self._section(
                section_page,
                section_url,
                unit_id,
                section_idx,
                section_name,
            )

    def _section(
        self,
        page: Node,
        page_url: str,
        unit_id: UUID,
        section_idx: int,
        fallback_name: str,
    ) -> RegulationSection:
        document = page.css_first("#co_document") or page.css_first("#co_contentColumn") or page
        for selector in _DECOMPOSE:
            for node in document.css(selector):
                node.decompose(recursive=True)

        title_node = page.css_first("#co_docHeaderTitleLine")
        title = ""
        if title_node:
            title = title_node.attrs.get("title", "") or _clean_text(title_node.text())
        if not title:
            title = fallback_name

        cite = page.css_first(".co_cites")
        external_reference_id = _clean_text(cite.text()) if cite else title

        return RegulationSection(
            state="New York",
            link=page_url,
            name=title,
            external_reference_id=external_reference_id,
            content=self.markdown(document),
            unit_id=unit_id,
            index=section_idx,
            status=RegulationStatus.REPEALED
            if "(Repealed)" in title or "[Repealed]" in title
            else RegulationStatus.ACTIVE,
        )

    def _children(self, page: Node, page_url: str) -> list[tuple[str, str, str]]:
        anchors = page.css("#co_contentColumn a[href], #co_body a[href], main a[href]")

        seen: set[tuple[str, str]] = set()
        children: list[tuple[str, str, str]] = []
        for anchor in anchors:
            href = anchor.attrs.get("href", "")
            if not href:
                continue

            full_url = _normalize_westlaw_url(urldefrag(urljoin(page_url, href)).url)
            kind = _link_kind(full_url)
            if kind is None:
                continue
            if kind == "browse" and "guid=" not in full_url:
                continue
            if full_url == page_url:
                continue

            name = _clean_text(anchor.text(deep=True))
            if not name:
                continue

            key = (kind, full_url)
            if key in seen:
                continue
            seen.add(key)
            children.append((kind, name, full_url))

        return children


def _reg_unit(page_url: str, hierarchy: list[str]) -> RegulationUnit:
    name = hierarchy[-1] if hierarchy else ""
    return RegulationUnit(
        state="New York",
        link=page_url,
        name=name,
        external_reference_id=_unit_external_reference(hierarchy),
        hierarchy=hierarchy,
        status=RegulationStatus.REPEALED
        if "(Repealed)" in name or "[Repealed]" in name
        else RegulationStatus.ACTIVE,
    )


def _link_kind(url: str) -> str | None:
    if "/nycrr/Document/" in url:
        return "document"
    if "/nycrr/Browse/Home/NewYork/UnofficialNewYorkCodesRulesandRegulations" in url:
        return "browse"
    return None


def _normalize_westlaw_url(url: str) -> str:
    parsed = urlparse(url)
    query_items = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _STRIP_QUERY_KEYS
    ]
    normalized_query = urlencode(query_items, doseq=True)
    return urlunparse(parsed._replace(query=normalized_query, fragment=""))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _unit_external_reference(hierarchy: list[str]) -> str:
    parts: list[str] = []
    for level in hierarchy:
        clean = _clean_text(level)
        match = re.match(
            r"^(Title|Subtitle|Chapter|Subchapter|Part|Subpart|Article)\s+([^\s]+)",
            clean,
            flags=re.IGNORECASE,
        )
        if not match:
            continue

        level_name = match.group(1)
        level_value = match.group(2)
        short = _SHORT_NAMES.get(level_name.title())
        if short:
            parts.append(f"{short} {level_value}")

    if parts:
        return ", ".join(parts)
    return " > ".join(hierarchy)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default

    try:
        return float(raw)
    except ValueError:
        return default


def _env_path(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    if not raw:
        return None
    return Path(raw)


def _infer_units_manifest(sections_manifest: Path) -> Path:
    inferred = Path(str(sections_manifest).replace("reg_section", "reg_unit"))
    if inferred.exists():
        return inferred
    return sections_manifest


def _status_from_raw(value: str | None) -> RegulationStatus:
    raw = (value or "").strip().lower()
    if raw == "active":
        return RegulationStatus.ACTIVE
    if raw == "repealed":
        return RegulationStatus.REPEALED
    return RegulationStatus.UNKNOWN


def _load_units_manifest(path: Path) -> dict[UUID, RegulationUnit]:
    units: dict[UUID, RegulationUnit] = {}
    if not path.exists():
        return units

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                unit = RegulationUnit(
                    id=UUID(str(record.get("id"))),
                    state=record.get("state") or "New York",
                    link=record.get("link") or _SEED,
                    external_reference_id=record.get("external_reference_id") or "",
                    name=record.get("name") or "",
                    status=_status_from_raw(record.get("status")),
                    hierarchy=[str(v) for v in (record.get("hierarchy") or [])],
                )
                units[unit.id] = unit
            except Exception:
                continue
    return units


def _load_sections_manifest(path: Path) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    if not path.exists():
        return sections

    seen_links: set[str] = set()
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                link = _normalize_westlaw_url(str(record.get("link") or ""))
                if not link or "/nycrr/Document/" not in link or link in seen_links:
                    continue
                unit_id = UUID(str(record.get("unit_id")))
                sections.append(
                    {
                        "link": link,
                        "unit_id": unit_id,
                        "index": int(record.get("index") or 0),
                        "name": str(record.get("name") or ""),
                    }
                )
                seen_links.add(link)
            except Exception:
                continue

    sections.sort(key=lambda s: (str(s["unit_id"]), s["index"], s["link"]))
    return sections


SCRAPER = NewYork()