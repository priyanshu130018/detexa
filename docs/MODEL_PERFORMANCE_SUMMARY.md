# Detexa Machine Learning Model Performance Summary

**Evaluation Date:** October 6, 2026  
**Artifact Directory:** `backend/app/ml/saved/`  
**Dataset Ground Truth:** `backend/data/creditcard.csv` (ULB Kaggle Credit Card Dataset, 283,726 deduplicated records)  
**Evaluation Slice:** Stratified Held-out Test Set ($N = 56,746$; 56,651 Legitimate, 95 Fraudulent)

---

## 1. Executive Performance Summary Table

| Model Component | Framework & Estimator | Target Task | Primary Metric(s) | Latency (Raw / End-to-End) | Throughput | Artifact Status | Final Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **Credit Card Fraud Model** | `scikit-learn` 1.4.2<br>`xgboost` 2.0.3<br>(43 Features) | Real-time Payment Fraud Classification | **ROC-AUC:** `0.9737`<br>**PR-AUC:** `0.8093`<br>**F1-Score (@ 0.50):** `0.7937`<br>**Recall (@ 0.50):** `78.95%`<br>**Precision (@ 0.50):** `79.79%`<br>**FPR (@ 0.50):** `0.0335%` | **Raw C++ Booster:** `0.35 ms`<br>**With SHAP Attribution:** `54.83 ms (P50)` | **3,571 items/sec** (Batch 500)<br>**292,732 items/sec** (Vectorized) | Verified (`credit_fraud_pipeline.pkl`<br>`credit_fraud_booster.json`) | **PASS** |
| **Behavior Anomaly Model** | `scikit-learn` 1.4.2<br>`IsolationForest`<br>(12 Features) | Session & Account Anomaly Detection | **Mean Score:** `0.4690` ($\sigma = 0.0198$)<br>**Outlier Ratio (@ 0.50):** `0.05%`<br>**Deterministic Output:** `100%` | **Inference:** `< 2.5 ms` | **> 1,200 items/sec** | Verified (`behavior_pipeline.pkl`) | **PASS WITH LIMITATIONS** *(Unsupervised model evaluated on distribution bounds without labeled ground-truth session labels)* |
| **ONNX Runtime Model** | `onnxruntime`<br>(43 Input Tensors) | Edge / Non-Python Microservice Runtime | N/A (Native C++ XGBoost booster used instead) | N/A | N/A | Missing (`credit_fraud_model.onnx` not present in `saved/`) | **FAIL / NOT DEPLOYED** *(Native booster provides sub-millisecond parity; ONNX is optional)* |

---

## 2. Decision Threshold Matrix (Credit Card Model)

| Threshold | Precision | Recall | F1-Score | Accuracy | False Positive Rate | TP | FP | FN | TN | Operational Recommendation |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **0.30** | 62.90% | **82.11%** | 0.7123 | 99.889% | 0.0812% | 78 | 46 | 17 | 56,605 | Sensitive Screening / Trigger 3DS OTP |
| **0.40** | 71.70% | 80.00% | 0.7562 | 99.914% | 0.0530% | 76 | 30 | 19 | 56,621 | High Risk Monitoring |
| **0.50** | **79.79%** | **78.95%** | **0.7937** | **99.931%** | **0.0335%** | **75** | **19** | **20** | **56,632** | **Standard Production Baseline** |
| **0.60** | 81.52% | 78.95% | 0.8021 | 99.935% | 0.0300% | 75 | 17 | 20 | 56,634 | High Precision Screening |
| **0.70** | 84.09% | 77.89% | 0.8087 | 99.938% | 0.0247% | 74 | 14 | 21 | 56,637 | Low Customer Friction Mode |
| **0.75** | 87.06% | 77.89% | 0.8222 | 99.944% | 0.0194% | 74 | 11 | 21 | 56,640 | Automated Hard Decline Tier |
| **0.80** | 88.10% | 77.89% | 0.8268 | 99.945% | 0.0177% | 74 | 10 | 21 | 56,641 | High Confidence Autonomous Action |
| **0.90** | **91.25%** | 76.84% | **0.8343** | **99.949%** | **0.0124%** | 73 | 7 | 22 | 56,644 | Immediate Account Freeze & Alert |

---

## 3. Key Model Insights

1. **Top Risk Discriminators:** The top 3 features by XGBoost gain are interaction and PCA components:
   - `V14_V12_interaction` (`f37`): **49.24%** contribution
   - `V14` (`f13`): **13.16%** contribution
   - `V12_V10_interaction` (`f36`): **2.60%** contribution
2. **Explainability:** SHAP `TreeExplainer` is fully initialized and operational, outputting the top 4 risk drivers for flagged transactions.
3. **Robustness:** 100% of tested edge cases (micro-amounts, extreme values up to \$5,000,000, all-zero feature vectors, $\pm 50\sigma$ outliers) passed without exceptions, producing valid bounded probabilities in $[0.0, 1.0]$.
4. **Detailed Reference:** See [`MODEL_EVALUATION_REPORT.md`](./MODEL_EVALUATION_REPORT.md) for the full 19-section analytical breakdown.
