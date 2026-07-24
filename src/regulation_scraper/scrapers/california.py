from typing import AsyncGenerator
from urllib.parse import urljoin
from uuid import UUID

from selectolax.parser import Node

from regulation_scraper.schemas.regulation import (
    RegulationItem,
    RegulationUnit,
    RegulationSection,
    RegulationStatus,
)
from regulation_scraper.scrapers.regulation_scraper import RegulationScraper

_SEED = "https://govt.westlaw.com/calregs/Document/I7A6B47D0FD4311ECBA0CE8BD2C3F45C2?viewType=FullText&originationContext=documenttoc&transitionType=StatuteNavigator&contextData=%28sc.Default%29"
_SHORT_NAMES = {
    "Title": "T.",
    "Division": "D.",
    "Chapter": "Ch.",
    "Article": "Art.",
    "Subchapter": "Subch.",
    "Subarticle": "Subar.",
}
_DECOMPOSE = [
    ".co_genericBoxContent",
    "#co_endOfDocument",
]


class California(RegulationScraper):
    async def regulations(self) -> AsyncGenerator[RegulationItem]:
        seen: dict[str, RegulationUnit] = {}
        page_url = _SEED
        section_idx: int = 0
        while page_url:
            page = await self.page(page_url)
            try:
                unit = _reg_unit(page_url, page)
            except Exception as e:
                raise Exception(f"Failed to parse unit from {page_url}") from e

            if unit.external_reference_id not in seen:
                seen[unit.external_reference_id] = unit
                yield unit
                section_idx = 1
            else:
                unit = seen[unit.external_reference_id]
                section_idx += 1

            try:
                yield self._section(page, page_url, unit.id, section_idx)
            except Exception as e:
                raise Exception(f"Failed to parse section from {page_url}") from e

            _next = page.css_first("#nextDocLink")
            if _next:
                page_url = urljoin(page_url, _next.attrs["href"])
            else:
                page_url = None

    def _section(
        self, page: Node, page_url: str, unit_id: UUID, section_idx: int
    ) -> RegulationSection:
        document = page.css_first("#co_document")
        for selector in _DECOMPOSE:
            for node in document.css(selector):
                node.decompose(recursive=True)

        title = page.css_first("#co_docHeaderTitleLine").attrs["title"]
        return RegulationSection(
            state="California",
            link=page_url,
            name=title,
            external_reference_id=page.css_first(".co_cites", strict=True).text(),
            content=self.markdown(document),
            unit_id=unit_id,
            index=section_idx,
            status=RegulationStatus.REPEALED
            if "[Repealed]" in title
            else RegulationStatus.ACTIVE,
        )


def _reg_unit(page_url: str, page: Node) -> RegulationUnit:
    unit_link = page.css_first(
        "section.co_innertube > a:last-of-type", strict=True
    ).attrs["href"]
    hierarchy_nodes = page.css(".co_genericBoxContent .co_headtext")[1:]
    hierarchy = [h.text(deep=False).strip() for h in hierarchy_nodes]

    id_parts = [
        (_SHORT_NAMES[h[0]], h[1])
        for h in [h[: h.rfind(".")].split(" ", maxsplit=2) for h in hierarchy]
    ]

    return RegulationUnit(
        state="California",
        link=urljoin(page_url, unit_link),
        name=hierarchy[-1],
        external_reference_id=", ".join([" ".join(i) for i in id_parts]),
        hierarchy=hierarchy,
        status=RegulationStatus.REPEALED
        if "[Repealed]" in hierarchy[-1]
        else RegulationStatus.ACTIVE,
    )


SCRAPER = California()
