# Detexa ML Model Training & Evaluation Report

## 1. Executive Summary

The Detexa Credit Card Fraud Detection model has been trained and evaluated using an end-to-end gradient boosted decision tree pipeline (**XGBoost**) integrated with automated feature engineering, outlier-resistant scaling, and cost-sensitive class weighting.

### Key Performance Highlights:
- **Primary Metric (PR-AUC / Average Precision)**: `0.8097` on unseen holdout test set (5-Fold CV Mean: `0.8524 ± 0.0286`)
- **ROC-AUC**: `0.9737` (5-Fold CV Mean: `0.9818 ± 0.0072`)
- **F1-Score @ Optimal Decision Threshold (0.5242)**: `0.8409`
- **Precision**: `91.36%` (Only 7 false alarms out of 56,651 legitimate transactions $\rightarrow$ **99.988% Specificity**)
- **Recall**: `77.89%` (Captured 74 out of 95 fraud cases in holdout test set)
- **Model Version**: `v2.0.0`
- **Training Time**: `6.69 seconds` for 226,980 training transactions

```
                  ┌─────────────────────────────────────────────────────────┐
                  │                 Raw Dataset (284,807)                   │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                      [Deduplication]
                                               │
                  ┌────────────────────────────▼────────────────────────────┐
                  │            Unique Clean Dataset (283,726)               │
                  └────────────────────────────┬────────────────────────────┘
                                               │
                                 [Stratified 80/20 Split]
                                               │
                     ┌─────────────────────────┴─────────────────────────┐
                     │ 80% (226,980 txns)                                │ 20% (56,746 txns)
           ┌─────────▼─────────┐                               ┌─────────▼─────────┐
           │   Training Set    │                               │ Holdout Test Set  │
           └─────────┬─────────┘                               └─────────┬─────────┘
                     │                                                   │
          [5-Fold Stratified CV]                                         │
                     │                                                   │
          [Feature Engineering:                                          │
           Diurnal Time + Log Amount +                                   │
           PCA Interactions + Norm]                                      │
                     │                                                   │
             [RobustScaler]                                              │
                     │                                                   │
          [XGBoost Classifier] ──────────────────────────────────────────┘
                     │                                            (Unseen Test Inference)
           ┌─────────▼─────────┐                                         │
           │  Saved Pipeline   │                               ┌─────────▼─────────┐
           │      (v2.0.0)     │                               │  PR-AUC = 0.8097  │
           └───────────────────┘                               │  F1     = 0.8409  │
                                                               └───────────────────┘
```

---

## 2. Dataset Preprocessing & Leakage Prevention

### 2.1 Deduplication
- **Raw Instances**: `284,807`
- **Duplicate Rows Removed**: `1,081` (0.38%)
- **Clean Instances**: `283,726` (`283,253` Legitimate, `473` Fraudulent)
- **Leakage Prevention**: Exact duplicates were pruned **prior to splitting** to guarantee that identical transactions could never exist simultaneously in both training and test folds.

### 2.2 Leakage-Free Stratified Splitting
- **Training Set (80%)**: `226,980` transactions (`378` fraud instances, $0.1665\%$ rate)
- **Holdout Test Set (20%)**: `56,746` transactions (`95` fraud instances, $0.1674\%$ rate)
- **Random Seed**: `42` for exact mathematical reproducibility.

---

## 3. Feature Engineering & Scaling Pipeline

The input feature dimension was expanded from **30 raw inputs** to **43 engineered features**:

### 3.1 Transformations:
1. **Logarithmic Amount Compression**:
   $$\text{log\_amount} = \ln(1 + \max(0, \text{Amount}))$$
   $$\text{amount\_sq} = \text{Amount}^2$$
2. **Diurnal Cyclical Time Encoding**:
   $$\text{hour\_of\_day} = \frac{\text{Time} \pmod{86400}}{3600}$$
   $$\text{sin\_time} = \sin\left(\frac{2\pi \times \text{hour}}{24}\right), \quad \text{cos\_time} = \cos\left(\frac{2\pi \times \text{hour}}{24}\right)$$
   $$\text{is\_night\_txn} = \mathbb{I}(\text{hour} < 6 \lor \text{hour} \ge 22)$$
3. **High-Impact Non-Linear Interaction Pairs**:
   - $V_{14} \times V_{12}$
   - $V_{14} \times V_{17}$
   - $V_{12} \times V_{10}$
   - $V_{17} \times V_{12}$
   - $V_4 \times V_{11}$
   - $V_1 \times V_2$
   - $V_3 \times V_7$
4. **PCA Vector Magnitude**:
   $$\|\mathbf{V}\|_2 = \sqrt{\sum_{i=1}^{28} V_i^2}$$
5. **Robust Scaling**:
   Features scaled via `RobustScaler()`, centering data on median and scaling by Interquartile Range ($Q_3 - Q_1$) to prevent extreme outlier fraud values from distorting normal bounds.

---

## 4. Model Architecture & Hyperparameters

### Model: `XGBoostClassifier`
- **Objective**: `binary:logistic`
- **Evaluation Metric**: `aucpr` (Area under Precision-Recall Curve)
- **Tree Method**: `hist` (Histogram-based binning for high throughput)
- **Number of Estimators**: `200`
- **Max Depth**: `5`
- **Learning Rate ($\eta$)**: `0.05`
- **Subsample Ratio**: `0.80`
- **Column Subsample (by tree)**: `0.80`
- **Class Weighting (`scale_pos_weight`)**: `15.00` (Cost-sensitive compensation for 598:1 class imbalance)
- **Random Seed**: `42`

---

## 5. Stratified 5-Fold Cross-Validation Performance

Cross-validation was performed strictly on the 80% training set (226,980 rows) using `StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`:

| Fold | PR-AUC (Avg Precision) | ROC-AUC | F1-Score |
|---|---|---|---|
| **Fold 1** | `0.8514` | `0.9785` | `0.8696` |
| **Fold 2** | `0.8681` | `0.9711` | `0.8873` |
| **Fold 3** | `0.7982` | `0.9810` | `0.8143` |
| **Fold 4** | `0.8803` | `0.9862` | `0.8627` |
| **Fold 5** | `0.8637` | `0.9924` | `0.8800` |
| **Mean ± Std** | **`0.8524 ± 0.0286`** | **`0.9818 ± 0.0072`** | **`0.8628 ± 0.0257`** |

---

## 6. Holdout Test Set Evaluation (Unseen Data)

Evaluated on 56,746 holdout transactions (95 fraud, 56,651 legitimate):

| Metric | Optimal Threshold (0.5242) | Default Threshold (0.5000) |
|---|---|---|
| **PR-AUC (Average Precision)** | **`0.8097`** | **`0.8097`** |
| **ROC-AUC** | `0.9737` | `0.9737` |
| **F1-Score** | `0.8409` | `0.8409` |
| **Precision** | `91.36%` | `91.36%` |
| **Recall (Sensitivity)** | `77.89%` | `77.89%` |
| **Specificity** | `99.988%` | `99.988%` |

### Confusion Matrix on Holdout Set ($N = 56,746$):

$$\begin{array}{c|cc}
& \textbf{Predicted Legit (0)} & \textbf{Predicted Fraud (1)} \\
\hline
\textbf{Actual Legit (0)} & 56,644 \text{ (TN)} & 7 \text{ (FP)} \\
\textbf{Actual Fraud (1)} & 21 \text{ (FN)} & 74 \text{ (TP)} \\
\end{array}$$

- **True Negatives (TN)**: `56,644`
- **False Positives (FP)**: `7` (Only 7 false alarms out of 56,651 transactions!)
- **False Negatives (FN)**: `21`
- **True Positives (TP)**: `74`

---

## 7. Feature Importance & SHAP Drivers

The top 12 most influential features identified by the model:

| Rank | Feature | Importance Score | Rationale & Contribution |
|---|---|---|---|
| **1** | **`V14_V12_interaction`** | **`0.4924`** | Strongest compound discriminator; extreme values in both V14 and V12 strongly indicate coordinated fraud |
| **2** | **`V14`** | **`0.1316`** | Primary individual PCA component |
| **3** | **`V12_V10_interaction`** | **`0.0260`** | Joint anomaly signature |
| **4** | **`V17`** | **`0.0193`** | Strong individual linear and non-linear correlation |
| **5** | **`V12`** | **`0.0180`** | Primary individual PCA component |
| **6** | **`V4`** | **`0.0171`** | Positive correlation driver |
| **7** | **`V14_V17_interaction`** | **`0.0164`** | Multi-component interaction |
| **8** | **`V17_V12_interaction`** | **`0.0160`** | Compound interaction |
| **9** | **`V10`** | **`0.0145`** | Negative correlation driver |
| **10** | **`v_norm`** | **`0.0114`** | Composite geometric distance from PCA centroid |
| **11** | **`V8`** | **`0.0103`** | Anomaly variance |
| **12** | **`V1_V2_interaction`** | **`0.0099`** | Base component interaction |

---

## 8. Persisted Artifacts & Reproducibility

The trained pipeline and metadata have been serialized to:
- **Pipeline Pickle**: [`backend/app/ml/saved/credit_fraud_pipeline.pkl`](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/backend/app/ml/saved/credit_fraud_pipeline.pkl)
- **Model Metadata**: [`backend/app/ml/saved/credit_fraud_pipeline_metadata.json`](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/backend/app/ml/saved/credit_fraud_pipeline_metadata.json)
- **Feature Metadata**: [`backend/app/ml/saved/feature_metadata.json`](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/backend/app/ml/saved/feature_metadata.json)

### Re-running Training:
```bash
cd backend
python scripts/train_credit_fraud_model.py
```
