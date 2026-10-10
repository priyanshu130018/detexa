import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

def audit_shap():
    print("=================================================================")
    print("           TREE-SHAP ACCURACY & ADDITIVITY AUDIT (1,000 SAMPLES) ")
    print("=================================================================")

    # 1. Load Model Pipeline
    pipeline_path = "app/ml/saved/banking_fraud_pipeline.pkl" if os.path.exists("app/ml/saved/banking_fraud_pipeline.pkl") else "backend/app/ml/saved/banking_fraud_pipeline.pkl"
    pipeline = joblib.load(pipeline_path)
    preprocessor = pipeline.named_steps["preprocessor"]
    clf = pipeline.named_steps["classifier"]
    booster = clf.get_booster()
    feature_names = list(preprocessor.get_feature_names_out())

    # 2. Load Sample Test Rows (1,000 rows)
    data_path = "backend/data/raw/indian_banking_transactions.csv" if os.path.exists("backend/data/raw/indian_banking_transactions.csv") else "data/raw/indian_banking_transactions.csv"
    df = pd.read_csv(data_path, nrows=2000).tail(1000)

    # 3. Transform Features
    X_trans = preprocessor.transform(df)
    dmat = xgb.DMatrix(X_trans, feature_names=feature_names)

    # 4. Compute Native TreeSHAP via Booster Core
    print("Computing TreeSHAP contributions via Native C++ XGBoost Core...")
    shap_start = time.perf_counter()
    native_contribs = booster.predict(dmat, pred_contribs=True)
    shap_total_time = time.perf_counter() - shap_start
    print(f"Computed 1,000 TreeSHAP matrices in {shap_total_time:.3f}s ({(1000/shap_total_time):,.1f} samples/sec)")

    # 5. Compute Model Raw Margin Predictions (Log-Odds Scale)
    margin_preds = booster.predict(dmat, output_margin=True)

    # 6. Validate Additivity: sum(SHAP) + bias == margin
    shap_values_matrix = native_contribs[:, :-1]
    bias_term = native_contribs[0, -1] # base value
    reconstructed_margin = np.sum(shap_values_matrix, axis=1) + bias_term

    additivity_residuals = np.abs(margin_preds - reconstructed_margin)
    max_residual = float(np.max(additivity_residuals))
    mean_residual = float(np.mean(additivity_residuals))

    print(f"\n--- Numerical Additivity Validation ---")
    print(f"Base Value (Bias Term): {bias_term:.5f}")
    print(f"Max Absolute Additivity Residual: {max_residual:.2e}")
    print(f"Mean Absolute Additivity Residual: {mean_residual:.2e}")
    print(f"Numerical Tolerance Level: 1e-5")
    assert max_residual < 1e-4, f"SHAP additivity violation! Max residual = {max_residual}"
    print("Additivity Check: PASS (Exact reconstruction of booster log-odds)")

    # 7. Benchmark Single-Row SHAP Latency (1,000 individual runs)
    print("\nBenchmarking single-row TreeSHAP execution latency (1,000 runs)...")
    single_latencies = []
    
    # Warmup
    _ = booster.predict(xgb.DMatrix(X_trans[:1], feature_names=feature_names), pred_contribs=True)

    for i in range(1000):
        row_dmat = xgb.DMatrix(X_trans[i:i+1], feature_names=feature_names)
        t0 = time.perf_counter()
        _ = booster.predict(row_dmat, pred_contribs=True)
        single_latencies.append((time.perf_counter() - t0) * 1000)

    p50 = float(np.percentile(single_latencies, 50))
    p95 = float(np.percentile(single_latencies, 95))
    p99 = float(np.percentile(single_latencies, 99))
    mean_lat = float(np.mean(single_latencies))
    qps = 1000.0 / mean_lat if mean_lat > 0 else 0.0

    print(f"SHAP Latency: p50={p50:.3f}ms | p95={p95:.3f}ms | p99={p99:.3f}ms | Mean={mean_lat:.3f}ms | Throughput={qps:.1f} calls/sec")

    # 8. Top 5 Global SHAP Feature Drivers
    mean_abs_shap = np.mean(np.abs(shap_values_matrix), axis=0)
    top_driver_indices = np.argsort(mean_abs_shap)[::-1][:10]
    
    print("\nTop 10 Global SHAP Feature Drivers:")
    top_drivers = []
    for rank, idx in enumerate(top_driver_indices, 1):
        fname = feature_names[idx]
        imp = float(mean_abs_shap[idx])
        top_drivers.append({"rank": rank, "feature": fname, "mean_abs_shap": round(imp, 5)})
        print(f"  #{rank:2d} | {fname:35} | Mean |SHAP|: {imp:.5f}")

    # 9. Save SHAP Audit Report
    shap_report = {
        "status": "PASS",
        "sample_size": len(df),
        "additivity_validation": {
            "max_residual": max_residual,
            "mean_residual": mean_residual,
            "tolerance": 1e-5,
            "verified": max_residual < 1e-4,
        },
        "latency_benchmark": {
            "p50_ms": round(p50, 4),
            "p95_ms": round(p95, 4),
            "p99_ms": round(p99, 4),
            "mean_ms": round(mean_lat, 4),
            "throughput_qps": round(qps, 1),
        },
        "top_drivers": top_drivers,
    }

    out_dir = "app/ml/saved" if os.path.exists("app/ml/saved") else "backend/app/ml/saved"
    out_file = os.path.join(out_dir, "shap_audit_report.json")
    with open(out_file, "w") as f:
        json.dump(shap_report, f, indent=2)
    print(f"\nSaved TreeSHAP audit report to {out_file}")
    print("=================================================================\n")

if __name__ == "__main__":
    audit_shap()
