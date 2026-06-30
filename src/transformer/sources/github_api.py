"""Unstructured source: GitHub.

A public REST API is available. We fetch the user + repos when ``use_live`` is
set, and ALWAYS fall back to an on-disk fixture/cache (data/samples/github_cache)
so the pipeline is deterministic and runs offline. Languages across non-fork
repos become skill signals; the profile/blog become links.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..models import MatchKeys, Method, RawCandidate
from ..normalize import clean_url, github_key, name_key, normalize_name
from .base import SourceAdapter, v

_API = "https://api.github.com"
_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "samples" / "github_cache"
_M = Method.API_FIELD


class GithubApiAdapter(SourceAdapter):
    source_type = "github_api"

    def __init__(
        self,
        use_live: bool = False,
        cache_dir: Optional[Path] = None,
        timeout: float = 6.0,
    ) -> None:
        self.use_live = use_live
        self.cache_dir = Path(cache_dir) if cache_dir else _CACHE_DIR
        self.timeout = timeout

    def label(self, source_ref: str) -> str:
        return f"{self.source_type}:{self._login(source_ref) or source_ref}"

    @staticmethod
    def _login(source_ref: str) -> Optional[str]:
        return github_key(source_ref) or (str(source_ref).strip().lower() or None)

    def _parse(self, source_ref: str) -> list[RawCandidate]:
        login = self._login(source_ref)
        if not login:
            return []
        payload = self._fetch_live(login) if self.use_live else None
        if payload is None:
            payload = self._load_cache(login)  # raises if absent -> health error
        return [self._payload_to_candidate(login, payload)]

    # -- IO -----------------------------------------------------------------
    def _fetch_live(self, login: str) -> Optional[dict]:
        try:
            import httpx

            headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "candidate-transformer",
            }
            with httpx.Client(timeout=self.timeout, headers=headers) as client:
                u = client.get(f"{_API}/users/{login}")
                if u.status_code != 200:
                    return None
                repos = client.get(
                    f"{_API}/users/{login}/repos",
                    params={"per_page": 100, "sort": "updated"},
                )
                payload = {
                    "user": u.json(),
                    "repos": repos.json() if repos.status_code == 200 else [],
                }
            self._write_cache(login, payload)
            return payload
        except Exception:
            return None  # any failure -> cache fallback

    def _load_cache(self, login: str) -> dict:
        return json.loads((self.cache_dir / f"{login}.json").read_text(encoding="utf-8"))

    def _write_cache(self, login: str, payload: dict) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            (self.cache_dir / f"{login}.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception:
            pass  # caching is best-effort

    # -- mapping ------------------------------------------------------------
    def _payload_to_candidate(self, login: str, payload: dict) -> RawCandidate:
        user = payload.get("user") or {}
        repos = payload.get("repos") or []

        scalars: dict = {}
        lists: dict = {}

        name = normalize_name(user.get("name"))
        if name:
            scalars["full_name"] = v(name, _M, user.get("name"))
        bio = (user.get("bio") or "").strip()
        if bio:
            scalars["headline"] = v(bio, _M, user.get("bio"))

        github_url = clean_url(user.get("html_url")) or clean_url(f"github.com/{login}")
        if github_url:
            scalars["links.github"] = v(github_url, _M, user.get("html_url"))
        portfolio = clean_url(user.get("blog"))
        if portfolio:
            scalars["links.portfolio"] = v(portfolio, _M, user.get("blog"))

        location = (user.get("location") or "").strip()
        if location:
            parts = [p.strip() for p in location.split(",")]
            if parts and parts[0]:
                scalars["location.city"] = v(parts[0], _M, user.get("location"))
            if len(parts) >= 2 and parts[1]:
                scalars["location.region"] = v(parts[1], _M, user.get("location"))

        email = (user.get("email") or "").strip().lower()
        emails: list[str] = []
        if email and "@" in email:
            emails = [email]
            lists["emails"] = [v(email, _M, user.get("email"))]

        # Languages across non-fork repos -> skill signals (deterministic order).
        langs: dict[str, int] = {}
        for repo in repos:
            if repo.get("fork"):
                continue
            lang = repo.get("language")
            if lang:
                langs[lang] = langs.get(lang, 0) + 1
        for lang in sorted(langs, key=lambda l: (-langs[l], l)):
            lists.setdefault("skills", []).append(
                v(lang, _M, {"language": lang, "repos": langs[lang]})
            )

        match_keys = MatchKeys(
            emails=emails,
            github=login,
            name=name_key(name) if name else None,
        )
        return RawCandidate(
            source=f"{self.source_type}#{login}",
            source_type=self.source_type,
            reliability=self.reliability,
            scalars=scalars,
            lists=lists,
            match_keys=match_keys,
        )
