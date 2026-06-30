"""Cliente Supabase vía REST (urllib) — fallback cuando supabase-py falla por httpx."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


class _Result:
    def __init__(self, data: list):
        self.data = data


class _TableQuery:
    def __init__(self, client: "SupabaseHttpClient", table: str):
        self._client = client
        self._table = table
        self._cols = "*"
        self._filters: list[str] = []
        self._range: Optional[tuple[int, int]] = None
        self._limit: Optional[int] = None
        self._insert_data: Any = None
        self._update_data: Any = None
        self._upsert: bool = False
        self._on_conflict: str = ""

    def select(self, cols: str = "*"):
        self._cols = cols
        return self

    def eq(self, col: str, val: Any):
        self._filters.append(f"{col}=eq.{urllib.parse.quote(str(val))}")
        return self

    def lt(self, col: str, val: Any):
        self._filters.append(f"{col}=lt.{val}")
        return self

    def order(self, col: str, desc: bool = False):
        direction = ".desc" if desc else ".asc"
        self._filters.append(f"order={col}{direction}")
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def range(self, start: int, end: int):
        self._range = (start, end)
        return self

    def insert(self, data: Any):
        self._insert_data = data
        return self

    def upsert(self, data: Any, on_conflict: str = "codigo"):
        self._insert_data = data
        self._upsert = True
        self._on_conflict = on_conflict
        return self

    def update(self, data: dict):
        self._update_data = data
        return self

    def execute(self) -> _Result:
        extra_headers = {}
        if self._range is not None:
            start, end = self._range
            extra_headers["Range-Unit"] = "items"
            extra_headers["Range"] = f"{start}-{end}"
        if self._insert_data is not None:
            prefer = "return=representation"
            if self._upsert:
                prefer = f"return=representation,resolution=merge-duplicates"
            return self._client._request(
                "POST", self._table, body=self._insert_data,
                extra_headers=extra_headers,
                prefer=prefer,
                on_conflict=self._on_conflict if self._upsert else None,
            )
        if self._update_data is not None:
            qs = self._build_qs()
            return self._client._request("PATCH", self._table, qs=qs, body=self._update_data, extra_headers=extra_headers)
        qs = self._build_qs()
        return self._client._request("GET", self._table, qs=qs, extra_headers=extra_headers)

    def _build_qs(self) -> str:
        parts = [f"select={urllib.parse.quote(self._cols, safe='*,()')}"]
        parts.extend(self._filters)
        if self._limit is not None:
            parts.append(f"limit={self._limit}")
        return "&".join(parts)


class SupabaseHttpClient:
    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key

    def table(self, name: str) -> _TableQuery:
        return _TableQuery(self, name)

    def _request(self, method: str, table: str, qs: str = "", body: Any = None,
                 extra_headers: Optional[dict] = None, prefer: str = "return=representation",
                 on_conflict: Optional[str] = None) -> _Result:
        url = f"{self.url}/rest/v1/{table}"
        if method == "GET" and qs:
            url += "?" + qs
        elif method == "PATCH" and qs:
            url += "?" + qs
        elif on_conflict:
            url += f"?on_conflict={urllib.parse.quote(on_conflict)}"
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }
        if extra_headers:
            headers.update(extra_headers)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode()
                return _Result(json.loads(raw) if raw else [])
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            raise RuntimeError(err_body) from e


def create_http_client(url: str, key: str) -> SupabaseHttpClient:
    return SupabaseHttpClient(url, key)
