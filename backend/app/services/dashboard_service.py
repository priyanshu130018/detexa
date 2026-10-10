"""
app/services/dashboard_service.py
─────────────────────────────────────────────────────────────────────────────
High-performance aggregated dashboard analytics, time-series trends, and geo risk.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import case, cast, func, Integer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.redis import cache_get, cache_set
from app.db.models import AlertStatus, FraudAlert, RiskLevel, Transaction
from app.models.schemas import (
    CategoryRiskBreakdown,
    DashboardStats,
    GeoRiskPoint,
    RiskDistribution,
    TimeSeriesPoint,
)


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_kpi_stats(self) -> DashboardStats:
        cache_key = "stats:kpis"
        cached = cache_get(cache_key)
        if cached:
            cached["cached"] = True
            return DashboardStats(**cached)

        # Single-pass aggregated query for transactions
        txn_row = (
            self.db.query(
                func.count(Transaction.id).label("total"),
                func.sum(case((Transaction.is_fraud == True, 1), else_=0)).label("fraud_count"),
                func.sum(case((Transaction.risk_level == RiskLevel.HIGH, 1), else_=0)).label("high"),
                func.sum(case((Transaction.risk_level == RiskLevel.MEDIUM, 1), else_=0)).label("medium"),
                func.sum(case((Transaction.risk_level == RiskLevel.LOW, 1), else_=0)).label("low"),
                func.avg(Transaction.fraud_score).label("avg_score"),
            ).first()
        )

        total = txn_row.total or 0 if txn_row else 0
        fraud_count = int(txn_row.fraud_count or 0) if txn_row else 0
        high = int(txn_row.high or 0) if txn_row else 0
        medium = int(txn_row.medium or 0) if txn_row else 0
        low = int(txn_row.low or 0) if txn_row else 0
        avg_score = float(txn_row.avg_score or 0.0) if txn_row else 0.0

        # Single-pass aggregated query for alerts
        alert_row = (
            self.db.query(
                func.count(FraudAlert.id).label("total_alerts"),
                func.sum(case((FraudAlert.status == AlertStatus.OPEN, 1), else_=0)).label("open_alerts"),
            ).first()
        )
        total_alerts = alert_row.total_alerts or 0 if alert_row else 0
        open_alerts = int(alert_row.open_alerts or 0) if alert_row else 0

        stats = DashboardStats(
            total_transactions=total,
            fraud_count=fraud_count,
            fraud_rate=round(fraud_count / total, 4) if total else 0.0,
            high_risk_count=high,
            medium_risk_count=medium,
            low_risk_count=low,
            total_alerts=total_alerts,
            open_alerts=open_alerts,
            avg_fraud_score=round(avg_score, 4),
            cached=False,
        )
        cache_set(cache_key, stats.model_dump(), ttl_seconds=settings.redis_cache_ttl_stats)
        return stats

    def get_time_series_trends(self, days: int = 30) -> List[TimeSeriesPoint]:
        cache_key = f"stats:trends:{days}"
        cached = cache_get(cache_key)
        if cached:
            return [TimeSeriesPoint(**p) for p in cached]

        since_date = datetime.now(timezone.utc) - timedelta(days=days)
        # SQL-level daily aggregation using indexed transaction_date
        rows = (
            self.db.query(
                Transaction.transaction_date.label("d_str"),
                func.count(Transaction.id).label("total"),
                func.sum(case((Transaction.is_fraud == True, 1), else_=0)).label("fraud_cnt"),
                func.avg(Transaction.fraud_score).label("avg_score"),
            )
            .filter(Transaction.timestamp >= since_date)
            .group_by(Transaction.transaction_date)
            .order_by(Transaction.transaction_date.asc())
            .all()
        )

        points = []
        for d_val, total, fraud_cnt, avg_s in rows:
            if not d_val:
                continue
            d_str = str(d_val)
            points.append(
                TimeSeriesPoint(
                    date=d_str,
                    total_transactions=int(total or 0),
                    fraud_transactions=int(fraud_cnt or 0),
                    avg_score=round(float(avg_s or 0.0), 4),
                )
            )

        cache_set(cache_key, [p.model_dump() for p in points], ttl_seconds=settings.redis_cache_ttl_stats)
        return points

    def get_risk_distribution(self) -> RiskDistribution:
        cache_key = "stats:risk_dist"
        cached = cache_get(cache_key)
        if cached:
            return RiskDistribution(**cached)

        row = (
            self.db.query(
                func.sum(case((Transaction.risk_level == RiskLevel.LOW, 1), else_=0)).label("low"),
                func.sum(case((Transaction.risk_level == RiskLevel.MEDIUM, 1), else_=0)).label("medium"),
                func.sum(case((Transaction.risk_level == RiskLevel.HIGH, 1), else_=0)).label("high"),
            ).first()
        )
        low = int(row.low or 0) if row else 0
        medium = int(row.medium or 0) if row else 0
        high = int(row.high or 0) if row else 0

        dist = RiskDistribution(low=low, medium=medium, high=high)
        cache_set(cache_key, dist.model_dump(), ttl_seconds=settings.redis_cache_ttl_stats)
        return dist

    def get_category_breakdown(self) -> List[CategoryRiskBreakdown]:
        cache_key = "stats:categories"
        cached = cache_get(cache_key)
        if cached:
            return [CategoryRiskBreakdown(**p) for p in cached]

        rows = (
            self.db.query(
                Transaction.category,
                func.count(Transaction.id).label("total"),
                func.sum(case((Transaction.is_fraud == True, 1), else_=0)).label("fraud_cnt"),
            )
            .group_by(Transaction.category)
            .all()
        )

        res = []
        for cat, total, f_cnt in rows:
            if not cat:
                continue
            fraud_c = int(f_cnt or 0)
            total_c = int(total or 0)
            res.append(
                CategoryRiskBreakdown(
                    category=cat,
                    total_count=total_c,
                    fraud_count=fraud_c,
                    fraud_rate=round(fraud_c / total_c, 4) if total_c else 0.0,
                )
            )
        sorted_res = sorted(res, key=lambda x: x.fraud_rate, reverse=True)
        cache_set(cache_key, [r.model_dump() for r in sorted_res], ttl_seconds=settings.redis_cache_ttl_stats)
        return sorted_res

    def get_geo_risk(self) -> List[GeoRiskPoint]:
        cache_key = "stats:geo"
        cached = cache_get(cache_key)
        if cached:
            return [GeoRiskPoint(**p) for p in cached]

        rows = (
            self.db.query(
                Transaction.country,
                func.count(Transaction.id).label("total"),
                func.sum(case((Transaction.is_fraud == True, 1), else_=0)).label("fraud_cnt"),
                func.avg(Transaction.fraud_score).label("avg_score"),
            )
            .group_by(Transaction.country)
            .all()
        )

        out = []
        for c, total, f_cnt, avg_s in rows:
            country_name = c or "Unknown"
            total_c = int(total or 0)
            fraud_c = int(f_cnt or 0)
            avg_score = float(avg_s or 0.0)
            out.append(
                GeoRiskPoint(
                    country=country_name,
                    transaction_count=total_c,
                    fraud_count=fraud_c,
                    risk_score=round(avg_score, 4),
                )
            )
        sorted_out = sorted(out, key=lambda x: x.transaction_count, reverse=True)
        cache_set(cache_key, [r.model_dump() for r in sorted_out], ttl_seconds=settings.redis_cache_ttl_stats)
        return sorted_out
