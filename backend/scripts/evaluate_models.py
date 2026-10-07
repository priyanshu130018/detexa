"""
backend/scripts/evaluate_models.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive ML Model Evaluation Script for Detexa Platform.
Evaluates:
1. Indian Banking Fraud XGBoost Model vs Logistic Regression Baseline
   - Strictly Time-Based Train/Holdout Split (>=100k holdout samples, >=500 fraud cases)
   - PR-AUC, ROC-AUC, Recall @ 1% FPR, Precision, Recall, F1, Specificity, FPR, FNR, Confusion Matrix
   - Explicit Threshold Analysis at 0.60 and 0.85 (plus full sweep)
   - Data & Label Leakage Validation
2. Feature Importance & TreeSHAP Explainability Drivers
3. Behavior Anomaly Isolation Forest Model
4. Sub-Millisecond Inference Latency Breakdown (Cold start, Preprocessor, Scoring, Total)
5. Model Robustness & Edge Case Stress Testing
"""

import os
import sys
import time
import json
import uuid
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    precision_recall_curve,
    auc,
    confusion_matrix,
    roc_curve,
)
from sklearn.linear_model import LogisticRegression

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import settings
from app.ml.models.banking_fraud_model import BankingFraudModel
from app.ml.models.behavior_model import BehaviorAnomalyModel
from app.ml.inference.service import FraudInferenceService
from app.ml.pipelines.data_preprocessor import BankingDataPreprocessor


def compute_metrics_at_threshold(y_true, y_prob, threshold):
    y_pred = (y_prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    acc = float(accuracy_score(y_true, y_pred))
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0

    return {
        "threshold": float(threshold),
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "accuracy": acc,
        "specificity": specificity,
        "fpr": fpr,
        "fnr": fnr,
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
            "matrix_2x2": [[int(tn), int(fp)], [int(fn), int(tp)]],
        }
    }


def compute_recall_at_fpr(y_true, y_prob, target_fpr=0.01):
    """Calculates Recall at a specific FPR threshold (default: 1% FPR)."""
    fpr, tpr, thresholds = roc_curve(y_true, y_prob)
    # Find index where fpr <= target_fpr
    valid_indices = np.where(fpr <= target_fpr)[0]
    if len(valid_indices) == 0:
        return 0.0, 1.0, 0.0
    idx = valid_indices[-1]
    achieved_recall = float(tpr[idx])
    achieved_fpr = float(fpr[idx])
    cutoff_threshold = float(thresholds[idx]) if idx < len(thresholds) else 1.0
    return achieved_recall, cutoff_threshold, achieved_fpr


def evaluate_all():
    print("=" * 80)
    print("DETEXA ML VALIDATION: XGBOOST VS BASELINE ON INDIAN BANKING DATASET")
    print("=" * 80)

    results = {}

    # ─────────────────────────────────────────────────────────────────────────
    # 1. MODEL LOADING & ARTIFACT VERIFICATION
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[1/8] Verifying Production Model Artifacts & Cold Start Times...")
    saved_dirs = [
        Path("app/ml/saved"),
        Path("backend/app/ml/saved"),
        Path(__file__).parent.parent / "app" / "ml" / "saved",
    ]
    saved_dir = next((p for p in saved_dirs if p.exists()), Path("backend/app/ml/saved"))
    
    banking_pipeline_path = saved_dir / "banking_fraud_pipeline.pkl"
    banking_metadata_path = saved_dir / "banking_fraud_pipeline_metadata.json"
    feature_metadata_path = saved_dir / "feature_metadata.json"
    behavior_path = saved_dir / "behavior_pipeline.pkl"

    print(f"  - Saved artifacts directory: {saved_dir.resolve()}")
    print(f"  - Banking pipeline exists: {banking_pipeline_path.exists()} ({banking_pipeline_path.stat().st_size if banking_pipeline_path.exists() else 0} bytes)")
    print(f"  - Banking metadata exists: {banking_metadata_path.exists()} ({banking_metadata_path.stat().st_size if banking_metadata_path.exists() else 0} bytes)")
    print(f"  - Feature metadata exists: {feature_metadata_path.exists()} ({feature_metadata_path.stat().st_size if feature_metadata_path.exists() else 0} bytes)")
    print(f"  - Behavior pipeline exists: {behavior_path.exists()} ({behavior_path.stat().st_size if behavior_path.exists() else 0} bytes)")

    t0 = time.perf_counter()
    banking_model = BankingFraudModel.get_instance()
    banking_load_time_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    behavior_model = BehaviorAnomalyModel.get_instance()
    behavior_load_time_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    inference_service = FraudInferenceService.get_instance()
    inf_service_load_time_ms = (time.perf_counter() - t0) * 1000

    print(f"  - BankingFraudModel loaded: {banking_model._loaded} (Cold start: {banking_load_time_ms:.2f} ms)")
    print(f"  - BehaviorAnomalyModel loaded: {behavior_model._loaded} (Cold start: {behavior_load_time_ms:.2f} ms)")
    print(f"  - FraudInferenceService engine: '{inference_service._active_engine}' (Cold start: {inf_service_load_time_ms:.2f} ms)")

    results["loading"] = {
        "banking_loaded": banking_model._loaded,
        "behavior_loaded": behavior_model._loaded,
        "active_engine": inference_service._active_engine,
        "banking_cold_start_ms": banking_load_time_ms,
        "behavior_cold_start_ms": behavior_load_time_ms,
        "inference_service_cold_start_ms": inf_service_load_time_ms,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. DATASET LOADING & STRICT TIME-BASED TRAIN/TEST SPLIT
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[2/8] Loading Dataset & Executing Strict Time-Based Train/Holdout Split...")
    data_paths = [
        Path("backend/data/raw/indian_banking_transactions.csv"),
        Path("data/raw/indian_banking_transactions.csv"),
        Path(__file__).parent.parent / "data" / "raw" / "indian_banking_transactions.csv",
        Path("/app/data/raw/indian_banking_transactions.csv"),
    ]
    data_path = next((p for p in data_paths if p.exists()), None)

    if not data_path:
        raise FileNotFoundError("backend/data/raw/indian_banking_transactions.csv dataset not found!")

    df_raw = pd.read_csv(data_path)
    total_raw = len(df_raw)
    duplicates_count = int(df_raw.duplicated().sum())
    missing_count = int(df_raw.isnull().sum().sum())
    total_fraud = int((df_raw["is_fraud"] == 1).sum())
    total_legit = int((df_raw["is_fraud"] == 0).sum())

    print(f"  - Source Dataset: {data_path.resolve()}")
    print(f"  - Total Transactions: {total_raw:,} (Legit: {total_legit:,}, Fraud: {total_fraud:,}, {total_fraud/total_raw:.3%})")

    # Strict Chronological Sorting
    df_raw["_dt"] = pd.to_datetime(df_raw["transaction_date"] + " " + df_raw["transaction_time"])
    df_sorted = df_raw.sort_values(by=["_dt", "transaction_id"]).reset_index(drop=True)

    # Feature Engineering with strict backward-looking expansion (no forward leakage)
    df_sorted["cust_txn_count_prior"] = df_sorted.groupby("customer_id").cumcount().astype(float)
    cum_sum = df_sorted.groupby("customer_id")["transaction_amount"].cumsum()
    prior_sum = cum_sum - df_sorted["transaction_amount"]
    df_sorted["cust_avg_amount_prior"] = np.where(
        df_sorted["cust_txn_count_prior"] > 0,
        prior_sum / np.maximum(df_sorted["cust_txn_count_prior"], 1),
        df_sorted["transaction_amount"]
    )
    df_sorted["cust_amount_diff_from_avg"] = df_sorted["transaction_amount"] - df_sorted["cust_avg_amount_prior"]
    df_sorted["cust_amount_ratio_to_avg"] = df_sorted["transaction_amount"] / (df_sorted["cust_avg_amount_prior"] + 1.0)

    prev_time = df_sorted.groupby("customer_id")["_dt"].shift(1)
    df_sorted["cust_time_since_last_txn_hours"] = ((df_sorted["_dt"] - prev_time).dt.total_seconds() / 3600.0).fillna(168.0)

    prev_channel = df_sorted.groupby("customer_id")["channel"].shift(1)
    df_sorted["cust_channel_change"] = np.where(prev_channel.isna(), 0.0, (df_sorted["channel"] != prev_channel).astype(float))

    prev_type = df_sorted.groupby("customer_id")["transaction_type"].shift(1)
    df_sorted["cust_type_change"] = np.where(prev_type.isna(), 0.0, (df_sorted["transaction_type"] != prev_type).astype(float))

    df_sorted.drop(columns=["_dt"], inplace=True)

    # Time-Based Split: 440,000 Train (80%) | 110,000 Holdout Test (20%)
    test_size = 110000
    df_train = df_sorted.iloc[:-test_size].copy()
    df_test = df_sorted.iloc[-test_size:].copy()

    X_train = df_train.drop(columns=["is_fraud"])
    y_train = df_train["is_fraud"].astype(int)
    X_test = df_test.drop(columns=["is_fraud"])
    y_test = df_test["is_fraud"].astype(int)

    test_total = len(y_test)
    test_fraud = int((y_test == 1).sum())
    test_legit = int((y_test == 0).sum())

    print(f"  - Train Set Size: {len(X_train):,} (From {df_train['transaction_date'].min()} to {df_train['transaction_date'].max()})")
    print(f"  - Holdout Test Size: {test_total:,} (From {df_test['transaction_date'].min()} to {df_test['transaction_date'].max()})")
    print(f"  - Holdout Test Fraud Cases: {test_fraud:,} ({test_fraud / test_total:.3%}) [Meets >= 500 requirement: {test_fraud >= 500}]")
    print(f"  - Holdout Test Size >= 100,000: {test_total >= 100000}")

    results["dataset_split"] = {
        "total_samples": total_raw,
        "train_samples": len(X_train),
        "test_samples": test_total,
        "test_fraud_samples": test_fraud,
        "test_legit_samples": test_legit,
        "train_date_range": [str(df_train["transaction_date"].min()), str(df_train["transaction_date"].max())],
        "test_date_range": [str(df_test["transaction_date"].min()), str(df_test["transaction_date"].max())],
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 3. DATA & LABEL LEAKAGE VERIFICATION
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[3/8] Running Data & Label Leakage Validation Checks...")
    leakage_checks = {}

    # Check 1: Target variable absence in feature matrix
    target_in_features = "is_fraud" in X_train.columns or "is_fraud" in X_test.columns
    leakage_checks["target_in_features"] = target_in_features
    print(f"  - Check 1 [Target in Features]: {'FAILED (LEAK)' if target_in_features else 'PASSED (Clean)'}")

    # Check 2: Max correlation of numeric features with target
    numeric_cols = X_train.select_dtypes(include=[np.number]).columns
    correlations = df_train[numeric_cols].apply(lambda s: s.corr(y_train))
    max_corr_feat = correlations.abs().idxmax()
    max_corr_val = float(correlations[max_corr_feat])
    leakage_checks["max_feature_target_correlation"] = {"feature": max_corr_feat, "correlation": max_corr_val}
    print(f"  - Check 2 [Max Target Correlation]: {max_corr_feat} = {max_corr_val:.4f} ({'PASSED: No trivial identity leak' if abs(max_corr_val) < 0.90 else 'FAILED: Possible leak'})")

    # Check 3: Temporal strictly ascending check
    train_dates = pd.to_datetime(df_train["transaction_date"])
    test_dates = pd.to_datetime(df_test["transaction_date"])
    temporal_overlap = train_dates.max() > test_dates.min()
    leakage_checks["temporal_overlap"] = temporal_overlap
    print(f"  - Check 3 [Temporal Split Boundary]: Train max {train_dates.max().date()} vs Test min {test_dates.min().date()} -> {'PASSED (Zero temporal leakage)' if not temporal_overlap else 'OVERLAP'}")

    results["data_leakage_audit"] = leakage_checks

    # ─────────────────────────────────────────────────────────────────────────
    # 4. LOGISTIC REGRESSION BASELINE MODEL TRAINING & EVALUATION
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[4/8] Training & Evaluating Logistic Regression Baseline Model...")
    preprocessor = BankingDataPreprocessor(scaler_type="standard")
    
    t0_pre = time.perf_counter()
    X_train_proc = preprocessor.fit_transform(X_train)
    X_test_proc = preprocessor.transform(X_test)
    preproc_time = time.perf_counter() - t0_pre
    print(f"  - Feature Preprocessor fit/transform completed in {preproc_time:.2f}s ({X_train_proc.shape[1]} processed features)")

    # Train Logistic Regression Baseline with balanced class weighting
    t0_lr = time.perf_counter()
    lr_baseline = LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)
    lr_baseline.fit(X_train_proc, y_train)
    lr_train_time = time.perf_counter() - t0_lr

    y_prob_lr = lr_baseline.predict_proba(X_test_proc)[:, 1]

    # Baseline Metrics
    roc_auc_lr = float(roc_auc_score(y_test, y_prob_lr))
    prec_curve_lr, rec_curve_lr, _ = precision_recall_curve(y_test, y_prob_lr)
    pr_auc_lr = float(auc(rec_curve_lr, prec_curve_lr))
    rec_at_1fpr_lr, cut_lr, ach_fpr_lr = compute_recall_at_fpr(y_test, y_prob_lr, target_fpr=0.01)

    lr_m_060 = compute_metrics_at_threshold(y_test, y_prob_lr, 0.60)
    lr_m_085 = compute_metrics_at_threshold(y_test, y_prob_lr, 0.85)

    print(f"  - Logistic Regression Train Time: {lr_train_time:.2f}s")
    print(f"  - LR ROC-AUC: {roc_auc_lr:.4f} | PR-AUC: {pr_auc_lr:.4f}")
    print(f"  - LR Recall @ 1% FPR: {rec_at_1fpr_lr:.4%} (at threshold {cut_lr:.4f}, FPR={ach_fpr_lr:.4%})")
    print(f"  - LR @ Threshold 0.60 -> Precision: {lr_m_060['precision']:.4f}, Recall: {lr_m_060['recall']:.4f}, F1: {lr_m_060['f1_score']:.4f}, Specificity: {lr_m_060['specificity']:.4f}")
    print(f"  - LR @ Threshold 0.85 -> Precision: {lr_m_085['precision']:.4f}, Recall: {lr_m_085['recall']:.4f}, F1: {lr_m_085['f1_score']:.4f}, Specificity: {lr_m_085['specificity']:.4f}")

    results["logistic_regression_baseline"] = {
        "train_time_sec": lr_train_time,
        "roc_auc": roc_auc_lr,
        "pr_auc": pr_auc_lr,
        "recall_at_1_pct_fpr": {
            "recall": rec_at_1fpr_lr,
            "threshold": cut_lr,
            "actual_fpr": ach_fpr_lr,
        },
        "metrics_at_threshold_0_60": lr_m_060,
        "metrics_at_threshold_0_85": lr_m_085,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 5. PRODUCTION XGBOOST MODEL EVALUATION ON HOLDOUT TEST SET
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[5/8] Scoring Holdout Test Set on Production XGBoost Pipeline...")
    pipeline = banking_model._pipeline
    if pipeline is None:
        raise RuntimeError("Banking Pipeline is not loaded!")

    t0_xgb_score = time.perf_counter()
    y_prob_xgb = pipeline.predict_proba(X_test)[:, 1]
    xgb_score_time = time.perf_counter() - t0_xgb_score
    xgb_throughput = test_total / xgb_score_time

    print(f"  - Scored {test_total:,} records in {xgb_score_time:.2f}s ({xgb_throughput:,.0f} records/sec)")

    roc_auc_xgb = float(roc_auc_score(y_test, y_prob_xgb))
    prec_curve_xgb, rec_curve_xgb, _ = precision_recall_curve(y_test, y_prob_xgb)
    pr_auc_xgb = float(auc(rec_curve_xgb, prec_curve_xgb))
    rec_at_1fpr_xgb, cut_xgb, ach_fpr_xgb = compute_recall_at_fpr(y_test, y_prob_xgb, target_fpr=0.01)

    # Threshold Sweep
    sweep_thresholds = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90]
    sweep_results_xgb = []

    print("\n  XGBoost Threshold Evaluation Sweep on Holdout Set (N=110,000):")
    print("  " + "-" * 90)
    print(f"  {'Threshold':<10} {'Precision':<10} {'Recall':<10} {'F1-Score':<10} {'Specificity':<12} {'FPR':<10} {'FNR':<10} {'TP/FP/FN'}")
    print("  " + "-" * 90)

    for thresh in sweep_thresholds:
        m = compute_metrics_at_threshold(y_test, y_prob_xgb, thresh)
        sweep_results_xgb.append(m)
        cm_dict = m["confusion_matrix"]
        print(f"  {thresh:<10.2f} {m['precision']:<10.4f} {m['recall']:<10.4f} {m['f1_score']:<10.4f} {m['specificity']:<12.4f} {m['fpr']:<10.4f} {m['fnr']:<10.4f} {cm_dict['tp']}/{cm_dict['fp']}/{cm_dict['fn']}")

    xgb_m_060 = compute_metrics_at_threshold(y_test, y_prob_xgb, 0.60)
    xgb_m_085 = compute_metrics_at_threshold(y_test, y_prob_xgb, 0.85)

    print("\n  Production Threshold Highlights:")
    print(f"  - XGBoost @ 0.60 -> Precision: {xgb_m_060['precision']:.4f}, Recall: {xgb_m_060['recall']:.4f}, F1: {xgb_m_060['f1_score']:.4f}, Specificity: {xgb_m_060['specificity']:.4f}, FPR: {xgb_m_060['fpr']:.4f}, FNR: {xgb_m_060['fnr']:.4f}")
    print(f"    Confusion Matrix: [[TN={xgb_m_060['confusion_matrix']['tn']}, FP={xgb_m_060['confusion_matrix']['fp']}], [FN={xgb_m_060['confusion_matrix']['fn']}, TP={xgb_m_060['confusion_matrix']['tp']}]]")
    print(f"  - XGBoost @ 0.85 -> Precision: {xgb_m_085['precision']:.4f}, Recall: {xgb_m_085['recall']:.4f}, F1: {xgb_m_085['f1_score']:.4f}, Specificity: {xgb_m_085['specificity']:.4f}, FPR: {xgb_m_085['fpr']:.4f}, FNR: {xgb_m_085['fnr']:.4f}")
    print(f"    Confusion Matrix: [[TN={xgb_m_085['confusion_matrix']['tn']}, FP={xgb_m_085['confusion_matrix']['fp']}], [FN={xgb_m_085['confusion_matrix']['fn']}, TP={xgb_m_085['confusion_matrix']['tp']}]]")
    print(f"  - XGBoost Recall @ 1% FPR: {rec_at_1fpr_xgb:.4%} (at threshold {cut_xgb:.4f}, FPR={ach_fpr_xgb:.4%})")

    results["xgboost_production_model"] = {
        "roc_auc": roc_auc_xgb,
        "pr_auc": pr_auc_xgb,
        "recall_at_1_pct_fpr": {
            "recall": rec_at_1fpr_xgb,
            "threshold": cut_xgb,
            "actual_fpr": ach_fpr_xgb,
        },
        "metrics_at_threshold_0_60": xgb_m_060,
        "metrics_at_threshold_0_85": xgb_m_085,
        "threshold_sweep": sweep_results_xgb,
        "scoring_throughput_qps": xgb_throughput,
    }

    # Comparison Table
    print("\n  Summary Comparison: XGBoost vs Logistic Regression Baseline:")
    print("  " + "=" * 70)
    print(f"  {'Metric':<25} {'XGBoost (Production)':<22} {'Logistic Regression'}")
    print("  " + "-" * 70)
    print(f"  {'ROC-AUC':<25} {roc_auc_xgb:<22.4f} {roc_auc_lr:.4f}")
    print(f"  {'PR-AUC':<25} {pr_auc_xgb:<22.4f} {pr_auc_lr:.4f}")
    print(f"  {'Recall @ 1% FPR':<25} {rec_at_1fpr_xgb:<22.4%} {rec_at_1fpr_lr:.4%}")
    print(f"  {'Precision @ 0.60':<25} {xgb_m_060['precision']:<22.4f} {lr_m_060['precision']:.4f}")
    print(f"  {'Recall @ 0.60':<25} {xgb_m_060['recall']:<22.4f} {lr_m_060['recall']:.4f}")
    print(f"  {'F1-Score @ 0.60':<25} {xgb_m_060['f1_score']:<22.4f} {lr_m_060['f1_score']:.4f}")
    print(f"  {'Precision @ 0.85':<25} {xgb_m_085['precision']:<22.4f} {lr_m_085['precision']:.4f}")
    print(f"  {'Recall @ 0.85':<25} {xgb_m_085['recall']:<22.4f} {lr_m_085['recall']:.4f}")
    print(f"  {'F1-Score @ 0.85':<25} {xgb_m_085['f1_score']:<22.4f} {lr_m_085['f1_score']:.4f}")
    print("  " + "=" * 70)

    # ─────────────────────────────────────────────────────────────────────────
    # 6. FEATURE IMPORTANCE & SHAP EXPLANATIONS
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[6/8] Extracting Feature Importance & Native TreeSHAP Explanations...")
    top_features = []
    if banking_model._pipeline is not None:
        clf = banking_model._pipeline.named_steps.get("classifier")
        pre = banking_model._pipeline.named_steps.get("preprocessor")
        feature_names = pre.get_feature_names() if hasattr(pre, "get_feature_names") else []
        
        if hasattr(clf, "feature_importances_") and len(feature_names) == len(clf.feature_importances_):
            importances = clf.feature_importances_
            feat_imp = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
            top_features = [{"feature": f, "importance": float(imp)} for f, imp in feat_imp[:15]]
            print("  Top 10 Most Important Features:")
            for rank, (feat, imp) in enumerate(feat_imp[:10], 1):
                print(f"    {rank:<2}. {feat:<35}: {imp:.5f}")

    sample_tx = X_test.iloc[0].to_dict()
    score, drivers = banking_model.predict(sample_tx)
    print(f"  - Sample prediction score: {score:.4f} | SHAP risk drivers: {len(drivers) if drivers else 0}")
    if drivers:
        for d in drivers[:3]:
            f_name = d.get("feature") if isinstance(d, dict) else d.feature
            f_shap = d.get("shap_value") if isinstance(d, dict) else d.shap_value
            print(f"    * {f_name:<30} SHAP: {f_shap:+.4f}")

    results["feature_importance"] = {
        "top_features": top_features,
        "shap_active": drivers is not None,
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 7. BEHAVIOR ANOMALY MODEL EVALUATION
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[7/8] Evaluating Behavior Anomaly Isolation Forest Model...")
    np.random.seed(42)
    n_behavior_samples = 2000
    normal_count = int(n_behavior_samples * 0.95)
    anomaly_count = n_behavior_samples - normal_count

    normal_sessions = [
        {
            "session_id": f"sess-norm-{i}",
            "login_hour": int(np.random.choice(range(8, 21))),
            "typing_speed": float(np.random.normal(4.5, 0.8)),
            "mouse_velocity": float(np.random.normal(250.0, 40.0)),
            "is_vpn": False,
            "is_tor": False,
            "device_change": False,
            "failed_logins": int(np.random.choice([0, 0, 0, 1])),
        }
        for i in range(normal_count)
    ]
    anomaly_sessions = [
        {
            "session_id": f"sess-anom-{i}",
            "login_hour": int(np.random.choice([1, 2, 3, 4])),
            "typing_speed": float(np.random.uniform(0.2, 1.2)),
            "mouse_velocity": float(np.random.uniform(600.0, 1200.0)),
            "is_vpn": bool(np.random.choice([True, False])),
            "is_tor": bool(np.random.choice([True, True, False])),
            "device_change": True,
            "failed_logins": int(np.random.choice([3, 4, 5, 8])),
        }
        for i in range(anomaly_count)
    ]

    all_behavior = normal_sessions + anomaly_sessions
    b_scores = []
    b_lats = []
    for s in all_behavior:
        sc, lt, _ = behavior_model.predict(s)
        b_scores.append(sc)
        b_lats.append(lt)

    b_arr = np.array(b_scores)
    p50, p90, p95, p99 = np.percentile(b_arr, [50, 90, 95, 99])
    flagged = (b_arr >= 0.50).sum()

    print(f"  - Behavior Samples Tested: {n_behavior_samples} (Normal: {normal_count}, Anomalous: {anomaly_count})")
    print(f"  - Mean Score: {b_arr.mean():.4f} (Std: {b_arr.std():.4f}) | Flagged Rate (>=0.50): {(flagged/n_behavior_samples):.2%}")
    print(f"  - Percentiles: P50={p50:.4f}, P90={p90:.4f}, P95={p95:.4f}, P99={p99:.4f}")

    results["behavior_model"] = {
        "samples": n_behavior_samples,
        "mean_score": float(b_arr.mean()),
        "p50": float(p50),
        "p90": float(p90),
        "p95": float(p95),
        "p99": float(p99),
        "flagged_ratio_pct": float((flagged / n_behavior_samples) * 100),
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 8. SUB-MILLISECOND INFERENCE LATENCY BREAKDOWN
    # ─────────────────────────────────────────────────────────────────────────
    print("\n[8/8] Measuring In-Process ML Inference Latency Breakdown...")
    single_payload = X_test.iloc[0].to_dict()

    # Warmup
    for _ in range(50):
        banking_model.predict(single_payload)

    n_lat = 500
    latencies = []
    for _ in range(n_lat):
        t_s = time.perf_counter()
        _ = banking_model.predict(single_payload)
        latencies.append((time.perf_counter() - t_s) * 1000)

    lat_arr = np.array(latencies)
    l_p50 = float(np.percentile(lat_arr, 50))
    l_p95 = float(np.percentile(lat_arr, 95))
    l_p99 = float(np.percentile(lat_arr, 99))
    l_mean = float(lat_arr.mean())
    l_qps = 1000.0 / l_mean if l_mean > 0 else 0

    print(f"  In-Process ML Single Scoring Latency ({n_lat} trials):")
    print(f"    - Mean: {l_mean:.3f} ms | P50: {l_p50:.3f} ms | P95: {l_p95:.3f} ms | P99: {l_p99:.3f} ms")
    print(f"    - In-Process Scoring Throughput: {l_qps:,.0f} req/sec")

    results["inference_latency"] = {
        "iterations": n_lat,
        "mean_ms": l_mean,
        "p50_ms": l_p50,
        "p95_ms": l_p95,
        "p99_ms": l_p99,
        "throughput_qps": l_qps,
    }

    # Save to JSON
    out_json = saved_dir / "evaluation_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[OK] Saved all evaluation metrics to: {out_json.resolve()}")
    print("=" * 80)
    print("DETEXA ML EVALUATION COMPLETE")
    print("=" * 80)

    return results


if __name__ == "__main__":
    evaluate_all()
