"""Fetch images, GIFs and memes from free, open, keyless endpoints.

- Images / GIFs: Openverse (openly licensed media, no API key),
  falling back to Wikimedia Commons
- Memes: ImgFlip template API (keyless) - caption text is rendered
  locally by the SVG generator

All results are returned as data URIs so the generated SVG storyboard is
fully self-contained (no network dependency at render time).
"""

from __future__ import annotations

import base64
import random
import re
from dataclasses import dataclass

import certifi
import requests

from .runtime import dry_run

# macOS python.org builds can ship a broken OpenSSL trust store (TLS
# verification fails even with a valid CA bundle). Try verified first,
# fall back to unverified - these are public media files, not secrets.
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CA_BUNDLE = certifi.where()

OPENVERSE_API = "https://api.openverse.org/v1"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
IMGFLIP_API = "https://api.imgflip.com/get_memes"

MAX_MEDIA_BYTES = 3_000_000  # skip anything bigger than 3 MB
TIMEOUT = 20
UA = {"User-Agent": "video-agent/1.0 (personal demo)"}


def _get(url: str, **kwargs) -> requests.Response:
    try:
        return requests.get(url, verify=CA_BUNDLE, **kwargs)
    except requests.exceptions.SSLError:
        return requests.get(url, verify=False, **kwargs)


@dataclass
class MediaItem:
    uri: str
    meme_caption: tuple[str, str] | None = None


class MediaFetcher:
    """Fetches images / GIFs / memes and returns them as data URIs."""

    def __init__(self, max_bytes: int = MAX_MEDIA_BYTES, timeout: int = TIMEOUT) -> None:
        self.max_bytes = max_bytes
        self.timeout = timeout

    # ------------------------------------------------------------ Openverse

    def _openverse_search(self, query: str, count: int, gif_only: bool) -> list[dict]:
        r = _get(
            f"{OPENVERSE_API}/images/",
            params={"q": query, "page_size": str(min(count * 4, 40)), "license_type": "all"},
            headers=UA,
            timeout=self.timeout,
        )
        r.raise_for_status()
        results = (r.json().get("results") or [])[: count * 4]
        out = []
        for item in results:
            url = item.get("url") or ""
            is_gif = url.lower().split("?")[0].endswith(".gif")
            if is_gif != gif_only:
                continue
            out.append(
                {
                    "title": item.get("title", ""),
                    "mime": "image/gif" if is_gif else "image/jpeg",
                    "url": url,
                    "thumb": item.get("thumbnail") or url,
                }
            )
            if len(out) >= count:
                break
        return out

    # ------------------------------------------------------------- Wikimedia

    def _commons_search(self, query: str, limit: int) -> list[dict]:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",  # File: namespace
            "gsrlimit": str(limit),
            "prop": "imageinfo",
            "iiprop": "url|size|mime",
            "iiurlwidth": "800",
        }
        r = _get(COMMONS_API, params=params, headers=UA, timeout=self.timeout)
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages") or {}
        out = []
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            out.append(
                {
                    "title": page.get("title", ""),
                    "mime": info.get("mime", ""),
                    "url": info.get("url", ""),
                    "thumb": info.get("thumburl") or info.get("url", ""),
                    "size": info.get("size", 0),
                }
            )
        return out

    # ------------------------------------------------------------------ Memes

    def _imgflip_memes(self, count: int) -> list[dict]:
        r = _get(IMGFLIP_API, headers=UA, timeout=self.timeout)
        r.raise_for_status()
        memes = (r.json().get("data") or {}).get("memes") or []
        return random.sample(memes, min(count, len(memes)))

    # ----------------------------------------------------------------- Public

    def search_images(self, query: str, count: int = 3) -> list[dict]:
        """Search Openverse for photos, falling back to Wikimedia Commons."""
        try:
            results = self._openverse_search(query, count, gif_only=False)
            if results:
                return results
        except requests.RequestException:
            pass
        results = self._commons_search(f"{query} filetype:bitmap -filetype:gif", count * 2)
        return [r for r in results if r["mime"] in ("image/jpeg", "image/png")][:count]

    def search_gifs(self, query: str, count: int = 2) -> list[dict]:
        """Search Openverse for animated GIFs, falling back to Wikimedia."""
        try:
            results = self._openverse_search(query, count, gif_only=True)
            if results:
                return results
        except requests.RequestException:
            pass
        results = self._commons_search(f"{query} animation", count * 8)
        gifs = sorted(
            (r for r in results if r["mime"] == "image/gif"),
            key=lambda r: r.get("size", 0),
        )
        return gifs[:count]

    def search_memes(self, query: str, count: int = 2) -> list[dict]:
        """Pick meme templates (ImgFlip, keyless); captions are rendered
        locally by the SVG generator."""
        picked = self._imgflip_memes(count)
        words = re.sub(r"[^a-zA-Z0-9 ]", "", query).split()[:3]
        top = " ".join(words).upper() or "RELATABLE"
        bottom = "ME EVERY DAY"
        out = []
        for m in picked:
            url = m["url"]
            out.append(
                {
                    "title": m["name"],
                    "mime": "image/png",
                    "url": url,
                    "thumb": url,
                    "meme_caption": (top, bottom),
                }
            )
        return out

    def as_data_uri(self, url: str) -> str | None:
        """Download a media file and return it as a base64 data URI."""
        try:
            r = _get(url, headers=UA, timeout=self.timeout)
            r.raise_for_status()
            if len(r.content) > self.max_bytes:
                return None
            mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
            return f"data:{mime};base64," + base64.b64encode(r.content).decode()
        except requests.RequestException:
            return None

    def fetch(self, media_type: str, query: str, count: int = 1) -> list[MediaItem]:
        """Fetch `count` media items of a type as data URIs.

        media_type: "image" | "gif" | "meme"
        Returns an empty list when nothing is found (always, in dry run).
        """
        if dry_run():
            return []  # no network in dry run
        if media_type == "meme":
            results = self.search_memes(query, count)
        elif media_type == "gif":
            results = self.search_gifs(query, count)
        else:
            results = self.search_images(query, count)

        items = []
        for item in results:
            uri = self.as_data_uri(item["thumb"] or item["url"])
            if uri:
                items.append(MediaItem(uri=uri, meme_caption=item.get("meme_caption")))
        return items