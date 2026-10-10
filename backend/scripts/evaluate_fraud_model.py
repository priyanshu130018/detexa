import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

def evaluate_model():
    print("=================================================================")
    print("               DETEXA FRAUD MODEL EVALUATION AUDIT               ")
    print("=================================================================")

    # 1. Load Dataset
    data_path = "backend/data/raw/indian_banking_transactions.csv" if os.path.exists("backend/data/raw/indian_banking_transactions.csv") else "data/raw/indian_banking_transactions.csv"
    print(f"Loading dataset from {data_path}...")
    df = pd.read_csv(data_path)
    total_samples = len(df)
    print(f"Total Rows: {total_samples:,}")

    # Check Class Imbalance
    fraud_count = int(df["is_fraud"].sum())
    legit_count = total_samples - fraud_count
    fraud_prevalence = fraud_count / total_samples
    print(f"Class Distribution: {legit_count:,} Legitimate ({(1-fraud_prevalence)*100:.2f}%), {fraud_count:,} Fraud ({fraud_prevalence*100:.2f}%)")

    # 2. Chronological/Stratified Held-Out Split (Last 20% for Evaluation)
    test_size = int(total_samples * 0.20)
    train_df = df.iloc[:-test_size]
    test_df = df.iloc[-test_size:]
    
    print(f"Train Partition: {len(train_df):,} rows | Test Held-Out Partition: {len(test_df):,} rows")
    y_test = test_df["is_fraud"].values

    # Check overlap
    overlap = len(set(train_df["transaction_id"]).intersection(set(test_df["transaction_id"])))
    print(f"Transaction ID Train/Test Overlap: {overlap} (0 indicates clean partition)")

    # 3. Load Trained Pipeline
    pipeline_path = "app/ml/saved/banking_fraud_pipeline.pkl" if os.path.exists("app/ml/saved/banking_fraud_pipeline.pkl") else "backend/app/ml/saved/banking_fraud_pipeline.pkl"
    print(f"Loading serialized model pipeline from {pipeline_path}...")
    pipeline = joblib.load(pipeline_path)
    preprocessor = pipeline.named_steps["preprocessor"]
    clf = pipeline.named_steps["classifier"]
    
    print(f"Pipeline Classifier: {type(clf).__name__}")
    if hasattr(preprocessor, "get_feature_names_out"):
        feature_names = preprocessor.get_feature_names_out()
        print(f"Total Transformed Features: {len(feature_names)}")

    # 4. Predict on Held-Out Test Split
    print("\nRunning inference over held-out test split (110,000 samples)...")
    eval_start = time.perf_counter()
    y_probs = pipeline.predict_proba(test_df)[:, 1]
    eval_time = time.perf_counter() - eval_start
    print(f"Inference Completed in {eval_time:.2f}s ({len(test_df)/eval_time:,.0f} samples/sec)")

    # 5. Core Classification Metrics
    roc_auc = float(roc_auc_score(y_test, y_probs))
    pr_auc = float(average_precision_score(y_test, y_probs))
    print(f"ROC-AUC: {roc_auc:.4f} | PR-AUC: {pr_auc:.4f}")

    # Threshold Sweep & Calibration Table
    threshold_results = []
    best_f1 = 0.0
    best_thresh = 0.50

    for t in np.arange(0.05, 1.00, 0.05):
        t_float = round(float(t), 2)
        preds = (y_probs >= t_float).astype(int)
        cm = confusion_matrix(y_test, preds)
        tn, fp, fn, tp = cm.ravel()
        
        prec = float(precision_score(y_test, preds, zero_division=0))
        rec = float(recall_score(y_test, preds, zero_division=0))
        f1 = float(f1_score(y_test, preds, zero_division=0))
        spec = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        fpr = float(fp / (tn + fp)) if (tn + fp) > 0 else 0.0
        fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

        if f1 > best_f1:
            best_f1 = f1
            best_thresh = t_float

        threshold_results.append({
            "threshold": t_float,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "specificity": round(spec, 4),
            "fpr": round(fpr, 4),
            "fnr": round(fnr, 4),
            "tp": int(tp),
            "fp": int(fp),
            "tn": int(tn),
            "fn": int(fn),
        })

    # Operational Threshold Metrics (at current 0.50 and optimal threshold)
    op_thresh = 0.50
    op_preds = (y_probs >= op_thresh).astype(int)
    op_cm = confusion_matrix(y_test, op_preds)
    tn, fp, fn, tp = op_cm.ravel()
    op_prec = float(precision_score(y_test, op_preds, zero_division=0))
    op_rec = float(recall_score(y_test, op_preds, zero_division=0))
    op_f1 = float(f1_score(y_test, op_preds, zero_division=0))
    op_spec = float(tn / (tn + fp))
    op_fpr = float(fp / (tn + fp))
    op_fnr = float(fn / (fn + tp))

    # Recall at 1% FPR
    fprs, tprs, threshs = roc_curve(y_test, y_probs)
    rec_at_1pct_fpr = 0.0
    for f, t_rate in zip(fprs, tprs):
        if f <= 0.01:
            rec_at_1pct_fpr = float(t_rate)

    print("\n--- Operational Metrics @ Threshold 0.50 ---")
    print(f"Precision: {op_prec:.4f} | Recall: {op_rec:.4f} | F1: {op_f1:.4f} | Specificity: {op_spec:.4f}")
    print(f"FPR: {op_fpr:.4f} | FNR: {op_fnr:.4f} | Recall @ 1% FPR: {rec_at_1pct_fpr:.4f}")
    print(f"Confusion Matrix: TP={tp}, FP={fp}, TN={tn}, FN={fn}")
    print(f"Optimal Threshold (by F1 score): {best_thresh} (F1: {best_f1:.4f})")

    # 6. Single Prediction Latency Benchmark (1,000 samples)
    print("\nBenchmarking single-row inference latency (1,000 iterations)...")
    sample_records = test_df.head(1000).to_dict(orient="records")
    
    # Warm-up
    for r in sample_records[:10]:
        _ = pipeline.predict_proba(pd.DataFrame([r]))

    latencies = []
    for r in sample_records:
        t0 = time.perf_counter()
        _ = pipeline.predict_proba(pd.DataFrame([r]))
        latencies.append((time.perf_counter() - t0) * 1000)

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    p99 = float(np.percentile(latencies, 99))
    mean_lat = float(np.mean(latencies))
    throughput = 1000.0 / mean_lat if mean_lat > 0 else 0.0

    print(f"Latency: p50={p50:.2f}ms | p95={p95:.2f}ms | p99={p99:.2f}ms | Mean={mean_lat:.2f}ms | Throughput={throughput:.1f} req/sec")

    # 7. Package and Save Results
    results = {
        "model_name": "IndianBankingFraudXGBoost",
        "model_version": "2.0.0",
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "dataset_total_rows": total_samples,
        "held_out_test_rows": len(test_df),
        "fraud_prevalence": round(fraud_prevalence, 6),
        "metrics": {
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "precision": round(op_prec, 4),
            "recall": round(op_rec, 4),
            "f1": round(op_f1, 4),
            "specificity": round(op_spec, 4),
            "fpr": round(op_fpr, 4),
            "fnr": round(op_fnr, 4),
            "recall_at_1pct_fpr": round(rec_at_1pct_fpr, 4),
            "optimal_threshold": best_thresh,
            "best_f1": round(best_f1, 4),
            "confusion_matrix": {
                "tp": int(tp),
                "fp": int(fp),
                "tn": int(tn),
                "fn": int(fn),
            }
        },
        "latency_benchmark": {
            "sample_count": len(sample_records),
            "p50_ms": round(p50, 3),
            "p95_ms": round(p95, 3),
            "p99_ms": round(p99, 3),
            "mean_ms": round(mean_lat, 3),
            "throughput_qps": round(throughput, 1),
            "errors": 0,
        },
        "threshold_calibration": threshold_results,
    }

    out_dir = "app/ml/saved" if os.path.exists("app/ml/saved") else "backend/app/ml/saved"
    out_file = os.path.join(out_dir, "evaluation_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved complete model evaluation to {out_file}")
    print("=================================================================\n")

if __name__ == "__main__":
    evaluate_model()
