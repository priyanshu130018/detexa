"""
app/api/v1/endpoints/predict.py
─────────────────────────────────────────────────────────────────────────────
AI Prediction REST API endpoints: Single/Batch Credit Fraud & Behavioral Anomaly.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import get_behavior_service, get_current_user, get_fraud_service
from app.db.models import User
from app.models.schemas import (
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
    "/credit",
    response_model=FraudPredictionOut,
    status_code=status.HTTP_200_OK,
    summary="Predict Credit Card Fraud (Single)",
    description="Run the ensemble ML stacking pipeline on a transaction payload to compute fraud score, risk level, automated decision (ALLOW/REVIEW/BLOCK), and SHAP explainability drivers.",
)
def predict_credit(
    payload: TransactionIn,
    fraud_svc: FraudDetectionService = Depends(get_fraud_service),
    current_user: User = Depends(get_current_user),
) -> FraudPredictionOut:
    data = payload.model_dump()
    if not data.get("user_id"):
        data["user_id"] = str(current_user.id)
    result = fraud_svc.predict_credit(data)
    
    # Push real-time event to connected WebSockets and SSE clients
    try:
        from app.core.realtime_broadcaster import get_realtime_broadcaster
        rb = get_realtime_broadcaster()
        rb.push_new_transaction({
            "id": result.transaction_id,
            "transaction_ref": result.transaction_ref or result.transaction_id,
            "amount": data.get("amount", 0.0),
            "merchant": data.get("merchant", "General Merchant"),
            "category": data.get("category", "General"),
            "country": data.get("country", "US"),
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
        if result.is_fraud or result.risk_level == "High" or result.decision == "BLOCK":
            rb.push_fraud_alert({
                "id": f"alt_{result.transaction_id[:8]}",
                "transaction_id": result.transaction_id,
                "alert_type": "credit_fraud",
                "risk_level": result.risk_level,
                "score": result.fraud_score,
                "description": f"High risk transaction of ${data.get('amount', 0.0):.2f} flagged ({result.decision})",
                "status": "open",
            })
    except Exception as e:
        pass

    return result


@router.post(
    "/credit/batch",
    response_model=BatchCreditFraudOut,
    status_code=status.HTTP_200_OK,
    summary="Predict Credit Card Fraud (Batch)",
    description="Run high-throughput batch inference over an array of transaction payloads.",
)
def predict_credit_batch(
    payload: BatchCreditFraudIn,
    fraud_svc: FraudDetectionService = Depends(get_fraud_service),
    current_user: User = Depends(get_current_user),
) -> BatchCreditFraudOut:
    items = [t.model_dump() for t in payload.transactions]
    for item in items:
        if not item.get("user_id"):
            item["user_id"] = str(current_user.id)
    return fraud_svc.predict_batch(items)


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
    description="Executes sub-millisecond validated fraud inference using native in-memory XGBoost C++ Booster or ONNX Runtime.",
)
def predict_realtime(
    payload: TransactionIn,
    current_user: User = Depends(get_current_user),
):
    from app.ml.inference import get_inference_service
    from app.feature_store import get_feature_store
    from app.graph import get_graph_service

    data = payload.model_dump()
    user_key = str(payload.user_id or current_user.id)

    # Fetch live features from Redis & Neo4j
    redis_hot = get_feature_store().get_hot_features(
        user_key=user_key,
        current_amount=payload.amount,
        current_merchant=payload.merchant,
        current_category=payload.category,
        current_device=payload.device_fingerprint,
        current_ip=payload.ip_address,
        current_country=payload.country,
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

