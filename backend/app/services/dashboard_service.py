"""
app/services/dashboard_service.py
─────────────────────────────────────────────────────────────────────────────
High-performance aggregated dashboard analytics, time-series trends, and geo risk.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import func
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

        total = self.db.query(func.count(Transaction.id)).scalar() or 0
        fraud_count = self.db.query(func.count(Transaction.id)).filter(Transaction.is_fraud == True).scalar() or 0
        high = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.HIGH).scalar() or 0
        medium = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.MEDIUM).scalar() or 0
        low = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.LOW).scalar() or 0
        total_alerts = self.db.query(func.count(FraudAlert.id)).scalar() or 0
        open_alerts = self.db.query(func.count(FraudAlert.id)).filter(FraudAlert.status == AlertStatus.OPEN).scalar() or 0
        avg_score = self.db.query(func.avg(Transaction.fraud_score)).scalar() or 0.0

        stats = DashboardStats(
            total_transactions=total,
            fraud_count=fraud_count,
            fraud_rate=round(fraud_count / total, 4) if total else 0.0,
            high_risk_count=high,
            medium_risk_count=medium,
            low_risk_count=low,
            total_alerts=total_alerts,
            open_alerts=open_alerts,
            avg_fraud_score=round(float(avg_score), 4),
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
        # Query transactions grouped by date
        txns = (
            self.db.query(Transaction)
            .filter(Transaction.timestamp >= since_date)
            .order_by(Transaction.timestamp.asc())
            .all()
        )

        bucket: Dict[str, Dict[str, Any]] = {}
        for t in txns:
            d_str = t.timestamp.strftime("%Y-%m-%d")
            if d_str not in bucket:
                bucket[d_str] = {"total": 0, "fraud": 0, "scores": []}
            bucket[d_str]["total"] += 1
            if t.is_fraud:
                bucket[d_str]["fraud"] += 1
            if t.fraud_score is not None:
                bucket[d_str]["scores"].append(t.fraud_score)

        points = []
        for d_str, val in sorted(bucket.items()):
            scores = val["scores"]
            avg = sum(scores) / len(scores) if scores else 0.0
            points.append(
                TimeSeriesPoint(
                    date=d_str,
                    total_transactions=val["total"],
                    fraud_transactions=val["fraud"],
                    avg_score=round(avg, 4),
                )
            )

        cache_set(cache_key, [p.model_dump() for p in points], ttl_seconds=settings.redis_cache_ttl_stats)
        return points

    def get_risk_distribution(self) -> RiskDistribution:
        high = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.HIGH).scalar() or 0
        medium = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.MEDIUM).scalar() or 0
        low = self.db.query(func.count(Transaction.id)).filter(Transaction.risk_level == RiskLevel.LOW).scalar() or 0
        return RiskDistribution(low=low, medium=medium, high=high)

    def get_category_breakdown(self) -> List[CategoryRiskBreakdown]:
        rows = (
            self.db.query(
                Transaction.category,
                func.count(Transaction.id).label("total"),
                func.sum(func.cast(Transaction.is_fraud, func.integer if not hasattr(func, 'int') else func.int)).label("fraud_cnt"),
            )
            .group_by(Transaction.category)
            .all()
        )

        res = []
        for cat, total, f_cnt in rows:
            if not cat:
                continue
            fraud_c = int(f_cnt or 0)
            res.append(
                CategoryRiskBreakdown(
                    category=cat,
                    total_count=total,
                    fraud_count=fraud_c,
                    fraud_rate=round(fraud_c / total, 4) if total else 0.0,
                )
            )
        return sorted(res, key=lambda x: x.fraud_rate, reverse=True)

    def get_geo_risk(self) -> List[GeoRiskPoint]:
        txns = self.db.query(Transaction.country, Transaction.is_fraud, Transaction.fraud_score).all()
        geo_map: Dict[str, Dict[str, Any]] = {}
        for c, is_f, score in txns:
            if not c:
                c = "Unknown"
            if c not in geo_map:
                geo_map[c] = {"total": 0, "fraud": 0, "scores": []}
            geo_map[c]["total"] += 1
            if is_f:
                geo_map[c]["fraud"] += 1
            if score is not None:
                geo_map[c]["scores"].append(score)

        out = []
        for c, val in geo_map.items():
            scores = val["scores"]
            avg = sum(scores) / len(scores) if scores else 0.0
            out.append(
                GeoRiskPoint(
                    country=c,
                    transaction_count=val["total"],
                    fraud_count=val["fraud"],
                    risk_score=round(avg, 4),
                )
            )
        return sorted(out, key=lambda x: x.transaction_count, reverse=True)
