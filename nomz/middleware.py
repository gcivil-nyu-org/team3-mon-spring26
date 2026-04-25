import time
from dataclasses import dataclass
from datetime import datetime as dt
from datetime import timedelta
from datetime import timezone as dt_timezone
import ipaddress
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.db import IntegrityError
from django.db.models import Avg, Max
from django.utils import timezone

from .models import (
    SystemAlert,
    SystemAuditLog,
    SystemPerformanceMetric,
    SystemPerformanceSnapshot,
)

logger = logging.getLogger(__name__)


def get_client_ip(request) -> Optional[str]:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR")

    if not ip:
        return None

    # GenericIPAddressField is strict; avoid failing audit writes on invalid values.
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return None
    return ip


def should_skip_metrics(request) -> bool:
    # Avoid noisy/static traffic.
    path = request.path or ""
    return (
        path.startswith("/static/")
        or path.startswith("/media/")
        or path.endswith("favicon.ico")
    )


@dataclass(frozen=True)
class MetricsConfig:
    snapshot_interval_seconds: int
    error_rate_threshold: float
    avg_latency_ms_threshold: int


def _load_metrics_config() -> MetricsConfig:
    return MetricsConfig(
        snapshot_interval_seconds=int(
            getattr(settings, "SYSTEM_METRICS_SNAPSHOT_INTERVAL_SECONDS", 300)
        ),
        error_rate_threshold=float(
            getattr(settings, "SYSTEM_ALERT_ERROR_RATE_THRESHOLD", 0.2)
        ),
        avg_latency_ms_threshold=int(
            getattr(settings, "SYSTEM_ALERT_AVG_LATENCY_MS_THRESHOLD", 1000)
        ),
    )


def _bucket_bounds(now, interval_seconds: int):
    # Use UTC timestamps to avoid timezone drift.
    now_ts = now.timestamp()
    bucket_start_ts = now_ts - (now_ts % interval_seconds)
    interval_start = dt.fromtimestamp(bucket_start_ts, tz=dt_timezone.utc)
    interval_end = interval_start + timedelta(seconds=interval_seconds)
    return interval_start, interval_end


class SystemMonitoringMiddleware:
    """
    Records request metrics, creates system audit logs, and evaluates alerts.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        exception: Optional[BaseException] = None
        response = None
        status_code = 500
        duration_ms = 0

        try:
            response = self.get_response(request)
            status_code = getattr(response, "status_code", 200) or 200
            return response
        except BaseException as exc:
            exception = exc
            status_code = 500
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)

            # Best-effort: never break the main request.
            try:
                self._record_and_maybe_alert(
                    request, status_code, duration_ms, exception
                )
            except Exception:
                # Intentionally swallow to prevent monitoring failures from impacting the app.
                pass

    def _record_and_maybe_alert(
        self,
        request,
        status_code: int,
        duration_ms: int,
        exception: Optional[BaseException],
    ) -> None:
        if should_skip_metrics(request):
            return

        now = timezone.now()
        path = request.path or ""

        is_error = status_code >= 500
        exception_class = ""
        exception_message = ""
        if exception is not None:
            exception_class = exception.__class__.__name__
            exception_message = str(exception)[:500]

        # 1) Per-request metrics
        try:
            SystemPerformanceMetric.objects.create(
                method=request.method,
                path=path,
                duration_ms=duration_ms,
                status_code=int(status_code),
                is_error=is_error,
                exception_class=exception_class,
                exception_message=exception_message,
            )
        except Exception:
            # Monitoring should not block request.
            pass

        # 2) Audit logs: admin actions and system exceptions/health failures.
        self._maybe_audit_admin_change(request, now)
        self._maybe_audit_exception(request, now, exception, status_code, duration_ms)
        self._maybe_audit_server_error_response(
            request, now, exception, status_code, duration_ms
        )
        self._maybe_handle_health_check_failure(request, now, status_code, duration_ms)

        # 3) Snapshot + alert evaluation
        self._maybe_evaluate_alerts(now)

    def _maybe_audit_admin_change(self, request, now) -> None:
        path = request.path or ""
        if not path.startswith("/admin/"):
            return
        if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
            return
        user = getattr(request, "user", None)
        if (
            user is None
            or not getattr(user, "is_authenticated", False)
            or not getattr(user, "is_staff", False)
        ):
            return

        try:
            SystemAuditLog.objects.create(
                created_at=now,
                actor_user=user,
                actor_username=user.username,
                level="INFO",
                action="admin_write",
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                request_path=path,
                http_method=request.method,
                metadata={},
            )
        except Exception:
            pass

    def _maybe_audit_exception(
        self,
        request,
        now,
        exception: Optional[BaseException],
        status_code: int,
        duration_ms: int,
    ) -> None:
        if exception is None:
            return
        try:
            user = getattr(request, "user", None)
            actor_user = (
                user if (user and getattr(user, "is_authenticated", False)) else None
            )
            actor_username = getattr(actor_user, "username", "") if actor_user else ""

            SystemAuditLog.objects.create(
                created_at=now,
                actor_user=actor_user,
                actor_username=actor_username,
                level="ERROR",
                action="unhandled_exception",
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                request_path=request.path,
                http_method=request.method,
                metadata={
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "exception_class": exception.__class__.__name__,
                    "exception_message": str(exception)[:500],
                },
            )
        except Exception:
            pass

    def _maybe_handle_health_check_failure(
        self,
        request,
        now,
        status_code: int,
        duration_ms: int,
    ) -> None:
        path = request.path or ""
        if not path.rstrip("/").endswith("/health"):
            return
        if status_code == 200:
            return

        severity = "CRITICAL" if status_code >= 500 else "HIGH"
        alert_type = "HEALTH_CHECK_FAILURE"

        # Audit log
        try:
            user = getattr(request, "user", None)
            actor_user = (
                user if (user and getattr(user, "is_authenticated", False)) else None
            )
            actor_username = getattr(actor_user, "username", "") if actor_user else ""

            SystemAuditLog.objects.create(
                created_at=now,
                actor_user=actor_user,
                actor_username=actor_username,
                level=severity,
                action="health_check_failure",
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                request_path=path,
                http_method=request.method,
                metadata={"status_code": status_code, "duration_ms": duration_ms},
            )
        except Exception:
            pass

        # Alert record
        try:
            interval_start, _ = _bucket_bounds(
                now, _load_metrics_config().snapshot_interval_seconds
            )
            exists = SystemAlert.objects.filter(
                alert_type=alert_type,
                is_active=True,
                created_at__gte=interval_start,
            ).exists()
            if not exists:
                SystemAlert.objects.create(
                    alert_type=alert_type,
                    severity=severity,
                    message=f"Health check failed with status {status_code}",
                    details={"status_code": status_code, "duration_ms": duration_ms},
                    is_active=True,
                )
        except Exception:
            logger.exception("Failed to create HEALTH_CHECK_FAILURE SystemAlert")

    def _maybe_audit_server_error_response(
        self,
        request,
        now,
        exception: Optional[BaseException],
        status_code: int,
        duration_ms: int,
    ) -> None:
        """
        Records critical system events even when the view returns a 5xx response
        without raising (e.g. error handlers, explicit HttpResponseServerError).
        """
        if status_code < 500:
            return
        if exception is not None:
            # Exceptions are handled in _maybe_audit_exception.
            return

        path = request.path or ""
        if path.rstrip("/").endswith("/health"):
            # Health failures are handled separately to keep alert/audit semantics clear.
            return

        try:
            user = getattr(request, "user", None)
            actor_user = (
                user if (user and getattr(user, "is_authenticated", False)) else None
            )
            actor_username = getattr(actor_user, "username", "") if actor_user else ""

            SystemAuditLog.objects.create(
                created_at=now,
                actor_user=actor_user,
                actor_username=actor_username,
                level="ERROR",
                action="server_error_response",
                ip_address=get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                request_path=path,
                http_method=request.method,
                metadata={"status_code": status_code, "duration_ms": duration_ms},
            )
        except Exception:
            pass

    def _maybe_evaluate_alerts(self, now) -> None:
        config = _load_metrics_config()
        interval_start, interval_end = _bucket_bounds(
            now, config.snapshot_interval_seconds
        )

        # Only evaluate when a new snapshot bucket is created.
        try:
            snapshot_exists = SystemPerformanceSnapshot.objects.filter(
                interval_start=interval_start, interval_end=interval_end
            ).exists()
            if snapshot_exists:
                return

            qs = SystemPerformanceMetric.objects.filter(
                created_at__gte=interval_start,
                created_at__lt=interval_end,
            )
            total_requests = qs.count()
            if total_requests == 0:
                SystemPerformanceSnapshot.objects.create(
                    interval_start=interval_start,
                    interval_end=interval_end,
                    total_requests=0,
                    error_requests=0,
                    error_rate=0,
                    avg_latency_ms=0,
                    max_latency_ms=0,
                )
                self._resolve_alerts_if_cleared(now)
                return

            error_requests = qs.filter(is_error=True).count()
            error_rate = error_requests / total_requests

            lat_agg = qs.aggregate(
                avg_latency=Avg("duration_ms"),
                max_latency=Max("duration_ms"),
            )

            avg_latency_ms = lat_agg.get("avg_latency") or 0
            max_latency_ms = lat_agg.get("max_latency") or 0

            SystemPerformanceSnapshot.objects.create(
                interval_start=interval_start,
                interval_end=interval_end,
                total_requests=total_requests,
                error_requests=error_requests,
                error_rate=error_rate,
                avg_latency_ms=avg_latency_ms,
                max_latency_ms=max_latency_ms,
            )

            self._evaluate_alerts_from_snapshot(
                now=now,
                error_rate=error_rate,
                avg_latency_ms=avg_latency_ms,
            )
        except IntegrityError:
            # Another request likely created the snapshot.
            return
        except Exception:
            pass

    def _evaluate_alerts_from_snapshot(
        self, now, error_rate: float, avg_latency_ms: float
    ) -> None:
        config = _load_metrics_config()

        # HIGH_ERROR_RATE
        self._create_or_resolve_alert(
            alert_type="HIGH_ERROR_RATE",
            severity_threshold_error_rate=config.error_rate_threshold,
            now=now,
            should_trigger=(error_rate >= config.error_rate_threshold),
            message=f"High error rate detected: {error_rate:.2%}",
            details={"error_rate": error_rate},
            higher_severity_on_extreme=True,
        )

        # HIGH_LATENCY
        self._create_or_resolve_alert(
            alert_type="HIGH_LATENCY",
            severity_threshold_error_rate=config.error_rate_threshold,
            now=now,
            should_trigger=(avg_latency_ms >= config.avg_latency_ms_threshold),
            message=f"High latency detected: avg {avg_latency_ms:.0f}ms",
            details={"avg_latency_ms": avg_latency_ms},
            higher_severity_on_extreme=False,
            extreme_value=config.avg_latency_ms_threshold * 2,
        )

    def _create_or_resolve_alert(
        self,
        alert_type: str,
        severity_threshold_error_rate: float,
        now,
        should_trigger: bool,
        message: str,
        details: Dict[str, Any],
        higher_severity_on_extreme: bool,
        extreme_value: Optional[float] = None,
    ) -> None:
        try:
            # Resolve if condition cleared.
            if not should_trigger:
                SystemAlert.objects.filter(
                    alert_type=alert_type,
                    is_active=True,
                ).update(is_active=False, resolved_at=now)
                return

            # Dedup per bucket (active alerts only).
            active_exists = SystemAlert.objects.filter(
                alert_type=alert_type,
                is_active=True,
                created_at__gte=now
                - timedelta(
                    seconds=2 * _load_metrics_config().snapshot_interval_seconds
                ),
            ).exists()
            if active_exists:
                return

            severity = "HIGH"
            if higher_severity_on_extreme and extreme_value is None:
                # If error rate is far above threshold, bump severity.
                # (We don't know the exact value here; use a simple heuristic.)
                if details.get("error_rate", 0) >= max(
                    severity_threshold_error_rate * 2, 0.5
                ):
                    severity = "CRITICAL"
            elif (
                extreme_value is not None
                and details.get("avg_latency_ms", 0) >= extreme_value
            ):
                severity = "CRITICAL"

            SystemAlert.objects.create(
                alert_type=alert_type,
                severity=severity,
                message=message,
                details=details,
                is_active=True,
            )
        except Exception:
            pass

    def _resolve_alerts_if_cleared(self, now) -> None:
        try:
            SystemAlert.objects.filter(
                alert_type__in=["HIGH_ERROR_RATE", "HIGH_LATENCY"],
                is_active=True,
            ).update(is_active=False, resolved_at=now)
        except Exception:
            pass
