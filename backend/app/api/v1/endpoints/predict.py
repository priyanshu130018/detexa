"""
app/api/v1/endpoints/predict.py
─────────────────────────────────────────────────────────────────────────────
AI Prediction REST API endpoints: Single/Batch Indian Banking Fraud & Behavioral Anomaly.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_behavior_service, get_current_user, get_fraud_service
from app.db.models import User
from app.models.schemas import (
    BatchBankingFraudIn,
    BatchBankingFraudOut,
    BatchCreditFraudIn,
    BatchCreditFraudOut,
    BehaviorIn,
    BehaviorPredictionOut,
    FraudPredictionOut,
    TransactionIn,
)
from app.services.behavior_service import BehaviorDetectionService
from app.services.fraud_service import FraudDetectionService

router = APIRouter(prefix="/predict", tags=["AI Prediction & Risk Scoring"])


@router.post(
    "/transaction",
    response_model=FraudPredictionOut,
    status_code=status.HTTP_200_OK,
    summary="Predict Indian Banking Transaction Fraud (Single)",
    description="Run the XGBoost pipeline on an Indian banking transaction payload to compute fraud score, risk level, automated decision (ALLOW/CHALLENGE/REVIEW/BLOCK), and TreeSHAP explainability drivers.",
)
@router.post(
    "/credit",
    response_model=FraudPredictionOut,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def predict_transaction(
    payload: TransactionIn,
    fraud_svc: FraudDetectionService = Depends(get_fraud_service),
    current_user: User = Depends(get_current_user),
) -> FraudPredictionOut:
    data = payload.model_dump()
    if not data.get("user_id"):
        data["user_id"] = str(current_user.id)
    if not data.get("customer_id") and data.get("user_id"):
        data["customer_id"] = str(data["user_id"])

    result_dict = fraud_svc.predict_banking(data)
    result = FraudPredictionOut(**result_dict)

    # Push real-time event to connected WebSockets and SSE clients
    try:
        from app.core.realtime_broadcaster import get_realtime_broadcaster
        rb = get_realtime_broadcaster()
        amt = data.get("transaction_amount") or data.get("amount") or 0.0
        rb.push_new_transaction({
            "id": result.transaction_id,
            "transaction_ref": result.transaction_ref or result.transaction_id,
            "customer_id": data.get("customer_id"),
            "amount": amt,
            "transaction_amount": amt,
            "account_type": data.get("account_type", "Savings"),
            "transaction_type": data.get("transaction_type", "UPI"),
            "channel": data.get("channel", "Mobile_App"),
            "kyc_status": data.get("kyc_status", "Verified"),
            "state": data.get("state", "Maharashtra"),
            "merchant": data.get("merchant", "Online Merchant"),
            "category": data.get("merchant_category") or data.get("category", "Retail"),
            "country": data.get("country", "IN"),
            "fraud_score": result.fraud_score,
            "risk_level": result.risk_level,
            "decision": result.decision,
            "is_fraud": result.is_fraud,
            "latency_ms": result.latency_ms,
            "model_version": result.model_version,
            "timestamp": data.get("timestamp") or str(result.transaction_id),
        })
        rb.push_decision({
            "transaction_id": result.transaction_id,
            "decision": result.decision,
            "fraud_score": result.fraud_score,
            "risk_level": result.risk_level,
        })
        if result.is_fraud or result.risk_level == "High" or result.decision in ("BLOCK", "REVIEW"):
            rb.push_fraud_alert({
                "id": f"alt_{result.transaction_id[:8]}",
                "transaction_id": result.transaction_id,
                "alert_type": "banking_fraud",
                "risk_level": result.risk_level,
                "score": result.fraud_score,
                "description": f"High risk {data.get('transaction_type', 'UPI')} transaction of ₹{amt:,.2f} flagged ({result.decision})",
                "status": "open",
            })
    except Exception:
        pass

    return result


@router.post(
    "/transaction/batch",
    response_model=BatchBankingFraudOut,
    status_code=status.HTTP_200_OK,
    summary="Predict Indian Banking Transaction Fraud (Batch)",
    description="Run high-throughput batch inference over an array of banking transaction payloads.",
)
@router.post(
    "/credit/batch",
    response_model=BatchBankingFraudOut,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def predict_transaction_batch(
    payload: BatchBankingFraudIn,
    fraud_svc: FraudDetectionService = Depends(get_fraud_service),
    current_user: User = Depends(get_current_user),
) -> BatchBankingFraudOut:
    items = [t.model_dump() for t in payload.transactions]
    for item in items:
        if not item.get("user_id"):
            item["user_id"] = str(current_user.id)
        if not item.get("customer_id") and item.get("user_id"):
            item["customer_id"] = str(item["user_id"])
    return BatchBankingFraudOut(**fraud_svc.predict_batch(items))


@router.post(
    "/behavior",
    response_model=BehaviorPredictionOut,
    status_code=status.HTTP_200_OK,
    summary="Predict Behavioral Anomaly",
    description="Evaluate session telemetry, keystroke cadence, mouse velocity, device consistency, and network reputation for anomaly detection.",
)
def predict_behavior(
    payload: BehaviorIn,
    behavior_svc: BehaviorDetectionService = Depends(get_behavior_service),
    current_user: User = Depends(get_current_user),
) -> BehaviorPredictionOut:
    data = payload.model_dump()
    if not data.get("user_id"):
        data["user_id"] = str(current_user.id)
    return behavior_svc.predict_behavior(data)


@router.post(
    "/realtime",
    status_code=status.HTTP_200_OK,
    summary="Ultra-Low-Latency Fraud Inference (<1ms)",
    description="Executes sub-millisecond validated fraud inference using native in-memory XGBoost C++ Booster.",
)
def predict_realtime(
    payload: TransactionIn,
    current_user: User = Depends(get_current_user),
):
    from app.ml.inference import get_inference_service
    from app.feature_store import get_feature_store
    from app.graph import get_graph_service

    data = payload.model_dump()
    user_key = str(payload.customer_id or payload.user_id or current_user.id)
    amt = payload.transaction_amount or payload.amount or 0.0

    # Fetch live features from Redis & Neo4j
    redis_hot = get_feature_store().get_hot_features(
        user_key=user_key,
        current_amount=amt,
        current_merchant=payload.merchant,
        current_category=payload.merchant_category or payload.category,
        current_device=payload.device_fingerprint,
        current_ip=payload.ip_address,
        current_country=payload.country or "IN",
    )
    graph_feats = get_graph_service().get_features(
        user_id=user_key,
        current_device_fp=payload.device_fingerprint,
        current_ip=payload.ip_address,
    )

    result = get_inference_service().predict(
        payload=data,
        redis_features=redis_hot,
        graph_features=graph_feats,
    )

    return result.to_dict()
