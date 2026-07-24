import io
import uuid
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path

from typing import AsyncGenerator
from uuid import UUID

import aiofiles.os
from markitdown import StreamInfo, MarkItDown
from pydantic import BaseModel, HttpUrl, computed_field
from selectolax.parser import HTMLParser, Node

from regulation_scraper.schemas.regulation import RegulationItem
from regulation_scraper.web.http_client import CurlHttpClient


_CACHE_DIR = Path(".cache")


class Page(BaseModel):
    url: HttpUrl

    @computed_field
    @cached_property
    def id(self) -> UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, str(self.url))

    def cached(self, cache_dir: Path) -> Path:
        return cache_dir / f"{self.id}.html"


class RegulationScraper(ABC):
    def __init__(self, cache_dir: Path = None) -> None:
        self._cache = cache_dir or (_CACHE_DIR / type(self).__name__.lower())
        self._md = MarkItDown()

    async def page(self, url: str) -> Node:
        p = Page(url=url)
        cached = p.cached(self._cache)

        content: str | None = None
        if not await aiofiles.os.path.exists(cached):
            content = await CurlHttpClient.fetch(url)
            await aiofiles.os.makedirs(cached.parent, exist_ok=True)
            async with aiofiles.open(cached, mode="w") as f:
                await f.write(content)
        else:
            async with aiofiles.open(cached, mode="r") as f:
                content = await f.read()

        return HTMLParser(content).root

    def markdown(self, document: Node):
        return self._md.convert(
            source=io.BytesIO(document.html.encode("utf-8")),
            stream_info=StreamInfo(mimetype="text/html", charset="utf-8"),
        ).text_content

    @abstractmethod
    async def regulations(self) -> AsyncGenerator[RegulationItem]:
        raise NotImplementedError()
