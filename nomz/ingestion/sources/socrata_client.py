from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
from urllib.parse import quote_plus, urlencode
import json
import socket
import time
import urllib.error
import urllib.request


@dataclass(frozen=True)
class SocrataResource:
    dataset_id: str
    name: str
    fields: Optional[List[str]] = None


class SocrataError(RuntimeError):
    def __init__(
        self, message: str, status_code: Optional[int] = None, body: str = ""
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class SocrataClient:
    """
    Small Socrata client for NYC OpenData style JSON endpoints.
    Keeps source transport logic centralized for all data pipelines.
    """

    def __init__(
        self,
        domain: str = "data.cityofnewyork.us",
        app_token: Optional[str] = None,
        timeout_seconds: int = 30,
        max_retries: int = 4,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self.domain = domain.rstrip("/")
        self.app_token = app_token
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.base_urls = [
            f"https://{self.domain}/resource",
            f"https://{self.domain}/api/id",
        ]

    def fetch_all(
        self,
        resource: SocrataResource,
        where: Optional[str] = None,
        limit: int = 1000,
        order_by: Optional[str] = None,
    ) -> Iterable[Dict]:
        offset = 0
        retries = 0

        while True:
            payload = self.fetch_page(
                resource=resource,
                where=where,
                limit=limit,
                offset=offset,
                order_by=order_by,
            )
            if not payload:
                break

            for row in payload:
                yield row

            if len(payload) < limit:
                break
            offset += limit
            retries += 1
            # protect against accidental huge loops in bad responses
            if retries > 10000:
                raise SocrataError(
                    "Pagination guard triggered while fetching Socrata data"
                )

    def fetch_page(
        self,
        resource: SocrataResource,
        where: Optional[str],
        limit: int,
        offset: int,
        order_by: Optional[str] = None,
    ) -> List[Dict]:
        resource_id = resource.dataset_id
        params = {"$limit": limit, "$offset": offset}
        if where:
            params["$where"] = where
        if order_by:
            params["$order"] = order_by
        if resource.fields:
            select_expr = ",".join(resource.fields)
            params["$select"] = select_expr

        query = urlencode(params, quote_via=quote_plus)
        last_error: Optional[SocrataError] = None

        for base_url in self.base_urls:
            endpoint = f"{base_url}/{resource_id}.json"
            request_url = f"{endpoint}?{query}"
            for attempt in range(self.max_retries + 1):
                request = urllib.request.Request(request_url)
                request.add_header("Accept", "application/json")
                request.add_header("User-Agent", "NomzIngestion/1.0")
                if self.app_token:
                    request.add_header("X-App-Token", self.app_token)

                try:
                    with urllib.request.urlopen(
                        request, timeout=self.timeout_seconds
                    ) as response:
                        raw = response.read().decode("utf-8")
                        rows = json.loads(raw)
                        if isinstance(rows, dict) and rows.get("error"):
                            raise SocrataError(
                                f"Socrata API error for {resource.name}: {rows.get('message', 'Unknown error')}",
                                body=str(rows),
                            )
                        if not isinstance(rows, list):
                            raise SocrataError(
                                f"Unexpected response shape for {resource.name}"
                            )
                        return rows
                except urllib.error.HTTPError as exc:
                    body = (
                        exc.read().decode("utf-8", errors="replace") if exc.fp else ""
                    )
                    last_error = SocrataError(
                        f"HTTP {exc.code} while loading {resource.name}: {body}",
                        status_code=exc.code,
                        body=body,
                    )
                    is_non_tabular_forbidden = (
                        exc.code == 403 and "non-tabular" in body.lower()
                    )
                    if base_url == self.base_urls[0] and is_non_tabular_forbidden:
                        break

                    is_retryable_http = exc.code in {408, 429, 500, 502, 503, 504}
                    if attempt < self.max_retries and is_retryable_http:
                        sleep_for = self.retry_backoff_seconds * (2**attempt)
                        time.sleep(sleep_for)
                        continue
                    raise last_error
                except urllib.error.URLError as exc:
                    reason = getattr(exc, "reason", exc)
                    last_error = SocrataError(
                        f"Network error while loading {resource.name}: {reason}"
                    )
                    is_timeout = isinstance(reason, (TimeoutError, socket.timeout))
                    if attempt < self.max_retries and is_timeout:
                        sleep_for = self.retry_backoff_seconds * (2**attempt)
                        time.sleep(sleep_for)
                        continue
                    raise last_error
                except TimeoutError as exc:
                    last_error = SocrataError(
                        f"Network timeout while loading {resource.name}: {exc}"
                    )
                    if attempt < self.max_retries:
                        sleep_for = self.retry_backoff_seconds * (2**attempt)
                        time.sleep(sleep_for)
                        continue
                    raise last_error
                except socket.timeout as exc:
                    last_error = SocrataError(
                        f"Network timeout while loading {resource.name}: {exc}"
                    )
                    if attempt < self.max_retries:
                        sleep_for = self.retry_backoff_seconds * (2**attempt)
                        time.sleep(sleep_for)
                        continue
                    raise last_error
                except Exception as exc:
                    last_error = SocrataError(f"Failed to fetch {resource.name}: {exc}")
                    raise last_error

        raise last_error or SocrataError(f"Unable to fetch {resource.name}")
