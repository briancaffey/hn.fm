"""System health checker for hn.fm — driven by the dynamic service registry.

Reads `service_registry.get_service_specs()` (env-driven) so the Services page
always reflects what's actually wired, and updates between runs when you change
env vars. Disabled services report "disabled" (not a red error); optional
services that are offline don't fail the overall health.
"""

import os
import time
import logging
import requests
from typing import Dict, List, Tuple
from dataclasses import dataclass

from .service_registry import get_service_specs, ServiceSpec

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    name: str
    url: str
    status: str  # "online" | "offline" | "disabled" | "error"
    response_time: float
    error_message: str = None
    details: Dict = None


class SystemChecker:
    """Checks the health of every service in the registry."""

    def __init__(self):
        self.timeout = 8

    def check_all_services(self) -> Tuple[bool, List[ServiceStatus]]:
        results: List[ServiceStatus] = []
        all_healthy = True
        for spec in get_service_specs():
            status = self._check(spec)
            results.append(status)
            # Only required services that aren't online break overall health.
            if status.status not in ("online", "disabled") and not spec.optional:
                all_healthy = False
        return all_healthy, results

    def _check(self, spec: ServiceSpec) -> ServiceStatus:
        details = {"role": spec.role}
        if spec.note:
            details["note"] = spec.note

        if not spec.enabled:
            return ServiceStatus(
                name=spec.name,
                url=spec.base_url or "—",
                status="disabled",
                response_time=0.0,
                details=details,
            )

        if not spec.base_url:
            return ServiceStatus(
                name=spec.name,
                url="not configured",
                status="offline",
                response_time=0.0,
                error_message="base URL not configured",
                details=details,
            )

        url = spec.base_url + spec.health_path
        headers = {}
        if spec.auth_env and os.getenv(spec.auth_env):
            headers["Authorization"] = f"Bearer {os.getenv(spec.auth_env)}"

        try:
            t0 = time.time()
            r = requests.get(url, headers=headers, timeout=self.timeout)
            dt = round(time.time() - t0, 3)
            ok = r.status_code == 200
            if ok and spec.expect_json_key:
                try:
                    body = r.json()
                    ok = spec.expect_json_key in body
                    if ok and spec.expect_json_key == "data":
                        details["models"] = [
                            m.get("id") for m in body.get("data", [])
                        ][:6]
                except Exception:
                    ok = False
            return ServiceStatus(
                name=spec.name,
                url=spec.base_url,
                status="online" if ok else "offline",
                response_time=dt,
                error_message=None if ok else f"HTTP {r.status_code}",
                details=details,
            )
        except requests.exceptions.RequestException as e:
            return ServiceStatus(
                name=spec.name,
                url=spec.base_url,
                status="offline",
                response_time=0.0,
                error_message=str(e)[:120],
                details=details,
            )
