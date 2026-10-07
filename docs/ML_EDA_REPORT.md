# Detexa ML Exploratory Data Analysis (EDA) & Preprocessing Specification

## 1. Executive Summary & Dataset Structure

The credit card fraud dataset (`creditcard.csv`) contains real transactions made by European cardholders in September 2013 over a span of two consecutive days (172,792 seconds $\approx$ 48 hours).

### Key Dataset Dimensions:
- **Total Records ($N$)**: `284,807`
- **Total Features**: `30` input features + `1` binary target label (`Class`)
- **Memory Footprint**: `67.36 MB` (in-memory uncompressed)
- **Time Span**: `0.0` to `172,792.0` seconds
- **Data Source Structure**:
  - `Time`: Elapsed seconds between this transaction and the first transaction in the dataset.
  - `V1` – `V28`: 28 principal components obtained via PCA (dimensionality reduction performed by original data providers for confidentiality).
  - `Amount`: Monetary value of the transaction.
  - `Class`: Binary target variable (`0` = Legitimate, `1` = Fraudulent).

```
   284,807 Transactions
   ├── Legitimate (Class 0): 284,315 (99.8273%)
   └── Fraudulent (Class 1):     492 ( 0.1727%)  [Imbalance: 577.88 : 1]
```

---

## 2. Data Types & Schema Inspection

All 31 columns are strictly numerical (`float64` for PCA features, `int64` for target label):

| Column Name | Data Type | Description |
|---|---|---|
| `Time` | `float64` | Continuous seconds offset (0 to 172,792) |
| `V1` .. `V28` | `float64` | Orthogonal PCA transformed continuous features |
| `Amount` | `float64` | Continuous transaction amount in USD/EUR ($0.00 to $25,691.16) |
| `Class` | `int64` | Binary ground truth label (0 or 1) |

---

## 3. Missing Value & Infinite Value Analysis

- **Total Null / NaN Count**: `0` across all 31 columns ($0.00\%$).
- **Total Infinite ($\pm\infty$) Count**: `0` across all 31 columns ($0.00\%$).
- **Zero-Value Transactions**: `1,825` transactions have `Amount == 0.0` (card authorization checks / token validation pings).
- **Finding**: No imputation required. The dataset is fully complete.

---

## 4. Duplicate Records Analysis

- **Total Exact Duplicates**: `1,081` rows ($0.38\%$ of the dataset).
- **Duplicate Breakdown by Class**:
  - `Class 0` (Legitimate): `1,062` duplicate instances
  - `Class 1` (Fraudulent): `19` duplicate instances
- **Analytical Assessment**: In high-frequency transaction streams, identical amounts and PCA vectors at the same second offset can occur due to automated card retry loops, batch card verification pings, or repeated webhook web calls.
- **Preprocessing Decision**: When splitting into training and validation sets, duplicates must be preserved or systematically deduplicated **prior to stratification** to prevent identical duplicate rows from spanning both training and test folds.

---

## 5. Class Distribution & Extreme Imbalance Analysis

| Target Class | Record Count | Percentage | Imbalance Ratio |
|---|---|---|---|
| **Class 0 (Legitimate)** | `284,315` | `99.8273%` | $1 : 1$ |
| **Class 1 (Fraudulent)** | `492` | `0.1727%` | $1 : 577.88$ |
| **Total** | `284,807` | `100.0000%` | — |

### Critical Modeling Implications:
1. **Accuracy is Unusable**: A trivial dummy classifier predicting `0` for all transactions achieves `99.83%` accuracy while capturing `0%` of fraud.
2. **Primary Evaluation Metric**: **Precision-Recall Area Under Curve (PR-AUC / Average Precision)** and **F1-Score at optimal decision threshold**.
3. **Secondary Metric**: **Recall at $\ge 90\%$ Precision** and **Cost-Weighted Financial Loss**.
4. **Validation Strategy**: Strict **Stratified 5-Fold Cross-Validation** (`StratifiedKFold(n_splits=5, shuffle=True, random_state=42)`).

---

## 6. Outlier & Extreme Value Analysis

An Interquartile Range (IQR) outlier evaluation ($\text{Outliers} = X < Q_1 - 1.5 \times \text{IQR} \lor X > Q_3 + 1.5 \times \text{IQR}$) reveals high outlier rates in PCA features:

| Feature | $Q_1$ (25%) | Median (50%) | $Q_3$ (75%) | IQR | Outlier Count | Outlier % |
|---|---|---|---|---|---|---|
| `Amount` | $5.60 | $22.00 | $77.16 | $71.56 | `31,904` | **11.20%** |
| `V1` | -0.920 | 0.018 | 1.316 | 2.236 | `7,062` | 2.48% |
| `V2` | -0.599 | 0.065 | 0.804 | 1.403 | `13,526` | 4.75% |
| `V8` | -0.208 | 0.022 | 0.324 | 0.532 | `22,696` | 7.97% |
| `V10` | -0.535 | -0.093 | 0.454 | 0.989 | `18,496` | 6.49% |
| `V12` | -0.406 | 0.140 | 0.618 | 1.024 | `15,368` | 5.40% |
| `V14` | -0.426 | 0.051 | 0.493 | 0.919 | `14,149` | 4.97% |
| `V17` | -0.483 | -0.066 | 0.399 | 0.882 | `7,420` | 2.61% |
| `Time` | 54,201.5 | 84,692.0 | 139,320.5 | 85,119.0 | `0` | **0.00%** |

### Outlier Insight:
Unlike typical tabular datasets where outliers are considered measurement noise to be trimmed, in credit card fraud detection **the outliers often are the fraud cases**. Trimming outliers will eliminate positive fraud instances. Therefore, **RobustScaler** (using median and IQR rather than mean and standard deviation) is the required scaling mechanism.

---

## 7. Feature Distribution & Skewness Analysis

### 7.1 Monetary Amount Distribution
- **Overall**: Mean = `$88.35`, Median = `$22.00`, Min = `$0.00`, Max = `$25,691.16`, Std = `$250.12`.
- **Skewness**: `16.98` (severe positive skew).
- **Kurtosis**: `845.09` (leptokurtic, extremely heavy-tailed).
- **Class 0 (Legitimate)**: Mean = `$88.29`, Median = `$22.00`, 75th percentile = `$77.05`, Max = `$25,691.16`.
- **Class 1 (Fraudulent)**: Mean = `$122.21`, Median = `$9.25`, 75th percentile = `$105.89`, Max = `$2,125.87`.

> **Key Behavioral Insight**: Notice that the median fraudulent transaction is **$9.25** (significantly lower than legitimate transactions' median of **$22.00**). Fraudsters frequently conduct low-dollar test transactions (e.g. $1.00 - $10.00) to confirm card validity before attempting larger charges. The maximum fraud amount is capped at $2,125.87, remaining below bank floor limits.

### 7.2 Time Distribution
- **Overall**: Mean = `94,813.9s`, Median = `84,692.0s`, Skewness = `-0.036` (bimodal uniform-like).
- `Time` exhibits strong cyclical diurnal behavior with lower transaction volume during nighttime hours (02:00–06:00) and elevated volume during peak commercial hours (10:00–18:00).

---

## 8. Correlation Analysis & Feature Usefulness

### 8.1 Linear Correlation with Target `Class`

#### Top 10 Negative Correlated Features (Lower values $\rightarrow$ Higher Fraud Probability):
1. **`V17`**: $r = -0.3265$ (Strongest single linear predictor)
2. **`V14`**: $r = -0.3025$ (Critical fraud discriminator)
3. **`V12`**: $r = -0.2606$
4. **`V10`**: $r = -0.2169$
5. **`V16`**: $r = -0.1965$
6. **`V3`**:  $r = -0.1930$
7. **`V7`**:  $r = -0.1873$
8. **`V18`**: $r = -0.1115$
9. **`V1`**:  $r = -0.1013$
10. **`V9`**:  $r = -0.0977$

#### Top 10 Positive Correlated Features (Higher values $\rightarrow$ Higher Fraud Probability):
1. **`V11`**: $r = +0.1549$
2. **`V4`**:  $r = +0.1334$
3. **`V2`**:  $r = +0.0913$
4. **`V21`**: $r = +0.0404$
5. **`V19`**: $r = +0.0348$
6. **`V20`**: $r = +0.0201$
7. **`V8`**:  $r = +0.0199$
8. **`V27`**: $r = +0.0176$
9. **`V28`**: $r = +0.0095$
10. **`Amount`**: $r = +0.0056$

### 8.2 Multicollinearity & Orthogonality
- Because $V_1$ through $V_{28}$ are PCA principal components, their pairwise mutual Pearson correlation is exactly `0.0000`. There is **zero multicollinearity** among the raw PCA features.
- Non-linear interactions ($V_{14} \times V_{17}$, $V_{12} \times V_{10}$, $V_4 \times V_{11}$) expose high-order interaction surfaces that tree ensembles leverage.

---

## 9. Target Leakage Checks

- **Zero Direct Leakage**: No feature possesses correlation $> 0.35$ with `Class`.
- **Anonymity Verification**: PCA transformations have masked raw card identifiers, eliminating PII data leakage risks.
- **Timestamp Integrity**: `Time` is monotonic and relative, preventing future-dated signal leakage.

---

## 10. Preprocessing & Feature Engineering Specification

### Recommended Transformations:
1. **Monetary Amount Transformation**:
   $$\text{log\_amount} = \ln(1 + \max(0, \text{Amount}))$$
   $$\text{amount\_sq} = \text{Amount}^2$$
2. **Diurnal Time Transformations**:
   $$\text{hour} = \frac{\text{Time} \pmod{86400}}{3600}$$
   $$\text{sin\_time} = \sin\left(\frac{2\pi \times \text{hour}}{24}\right), \quad \text{cos\_time} = \cos\left(\frac{2\pi \times \text{hour}}{24}\right)$$
   $$\text{is\_night\_txn} = \mathbb{I}(\text{hour} < 6 \lor \text{hour} \ge 22)$$
3. **Interaction Features**:
   - $V_{14} \times V_{17}$
   - $V_{12} \times V_{10}$
   - $V_{14} \times V_{12}$
   - $V_{17} \times V_{12}$
   - $V_4 \times V_{11}$
   - $V_1 \times V_2$
   - $V_3 \times V_7$
4. **PCA Vector Norm**:
   $$\|\mathbf{V}\|_2 = \sqrt{\sum_{i=1}^{28} V_i^2}$$
5. **Feature Scaling**:
   `RobustScaler()` applied across all features to preserve outlier signatures while centering against median and IQR.

---

## 11. Reusable Modular Architecture

The preprocessing and training modules have been constructed in:
- [**`app/ml/pipelines/data_preprocessor.py`**](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/backend/app/ml/pipelines/data_preprocessor.py): `CreditCardDataPreprocessor`, `DatasetLoader`, `DatasetSplits`.
- [**`app/ml/pipelines/training_pipeline.py`**](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/backend/app/ml/pipelines/training_pipeline.py): `ModelTrainingPipeline`, `EvaluationMetrics`, Stacking Ensemble (XGBoost + LightGBM + Logistic Regression meta-learner).
- [**`app/ml/pipelines/feature_engineering.py`**](file:///c:/Users/13ver/Desktop/New%20folder/project/Detexa/backend/app/ml/pipelines/feature_engineering.py): Scikit-Learn transformers for credit and behavioral anomaly pipelines.
