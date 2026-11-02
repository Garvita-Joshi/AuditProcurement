"""AuditAI main ML pipeline — Colab-ready.

The script locates audit_anomalies_joined_dataset.csv in Colab or Drive, then
verifies it before training. It trains only on normal records and
evaluates Autoencoder + Isolation Forest on a later, untouched test period.
"""
# %% [markdown]
# Install once in Google Colab if needed:
# !pip -q install pandas scikit-learn torch matplotlib seaborn joblib

# %% Imports and configuration
from pathlib import Path
import copy
import random

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import torch
import torch.nn as nn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    PrecisionRecallDisplay,
    RocCurveDisplay,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Optional: set this only when you know the precise location. Leave as None to
# search /content and mounted Google Drive automatically.
DATA_PATH = None
DATASET_FILENAME = "audit_anomalies_joined_dataset.csv"

SEED = 42
EPOCHS = 80
BATCH_SIZE = 256
LEARNING_RATE = 1e-3
LATENT_DIM = 16
ISOLATION_CONTAMINATION = 0.05
AE_WEIGHT = 0.40
IF_WEIGHT = 0.60

random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print("Using device:", DEVICE)


# %% Locate, verify, and load the provided combined AuditAI dataset
def locate_dataset() -> Path:
    """Find the CSV in Colab, mounted Drive, or prompt for a direct upload."""
    if DATA_PATH:
        explicit_path = Path(DATA_PATH)
        if explicit_path.is_file():
            return explicit_path
        print(f"Configured DATA_PATH was not found: {explicit_path}")

    candidates = [
        Path("/content") / DATASET_FILENAME,
        Path("/content/drive/MyDrive") / DATASET_FILENAME,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate

    drive_root = Path("/content/drive/MyDrive")
    if drive_root.is_dir():
        matches = list(drive_root.rglob(DATASET_FILENAME))
        if matches:
            return matches[0]

    # This branch runs only in Colab and opens its normal file-upload control.
    try:
        from google.colab import files
        print(f"Could not find {DATASET_FILENAME}. Select it in the upload dialog.")
        uploaded = files.upload()
        if not uploaded:
            raise FileNotFoundError("No CSV was uploaded.")
        for uploaded_name in uploaded:
            uploaded_path = Path("/content") / uploaded_name
            if uploaded_path.suffix.lower() == ".csv":
                return uploaded_path
    except ImportError as exc:
        raise FileNotFoundError(
            f"Could not find {DATASET_FILENAME}. Set DATA_PATH to its full path."
        ) from exc
    raise FileNotFoundError("Upload audit_anomalies_joined_dataset.csv and run again.")


resolved_dataset_path = locate_dataset()
print("Dataset path:", resolved_dataset_path)
print("Dataset exists:", resolved_dataset_path.is_file())
if not resolved_dataset_path.is_file():
    raise FileNotFoundError(f"Dataset not found: {resolved_dataset_path}")

df = pd.read_csv(resolved_dataset_path, low_memory=False)
print("Dataset loaded successfully:", df.shape)
required_columns = {
    "transaction_date", "transaction_time", "amount", "is_anomaly",
    "ocr_extracted_amount", "receipt_claimed_amount",
}
missing_required = required_columns - set(df.columns)
if missing_required:
    raise ValueError(f"This is not the expected AuditAI dataset. Missing: {sorted(missing_required)}")
df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
parsed_time = pd.to_datetime(df["transaction_time"], format="%H:%M:%S", errors="coerce")

# These are allowed input features because they are available before prediction.
df["hour"] = parsed_time.dt.hour
df["day_of_week"] = df["transaction_date"].dt.dayofweek
df["month"] = df["transaction_date"].dt.month
df["is_weekend"] = (df["day_of_week"] >= 5).astype(float)
df["ocr_mismatch_ratio"] = (
    (df["ocr_extracted_amount"] - df["receipt_claimed_amount"]).abs()
    / df["receipt_claimed_amount"].replace(0, np.nan)
).fillna(0).clip(0, 10)
df["log_amount"] = np.log1p(df["amount"].clip(lower=0))

# IMPORTANT: exclude labels and human-created risk outputs. Including them would
# leak the answer into the model and create fake, unrealistically high metrics.
TARGET = "is_anomaly"
LEAKAGE_COLUMNS = {
    TARGET, "risk_category", "risk_severity", "risk_score",
    "detected_risk_signals", "audit_explanation",
}

numeric_features = [
    "amount", "ocr_extracted_amount", "receipt_claimed_amount",
    "hour", "day_of_week", "month", "is_weekend",
    "ocr_mismatch_ratio", "log_amount",
]
categorical_features = [
    "entry_type", "general_ledger_account", "currency", "vendor_id",
    "vendor_name", "employee_id", "department_id", "department_name",
    "approved_by_id", "payment_mode",
]

# Keep only columns which genuinely exist, so this notebook remains resilient.
numeric_features = [c for c in numeric_features if c in df.columns]
categorical_features = [c for c in categorical_features if c in df.columns]
df = df.dropna(subset=["transaction_date", TARGET]).sort_values("transaction_date").reset_index(drop=True)
assert set(LEAKAGE_COLUMNS).isdisjoint(numeric_features + categorical_features)
print(f"Transactions: {len(df):,}; anomaly rate: {df[TARGET].mean():.1%}")


# %% Time-based train/validation/test split
# Older records train the model; later records evaluate it. This avoids learning
# from the future, which is critical for an audit/fraud use case.
n = len(df)
train_end, validation_end = int(n * 0.70), int(n * 0.85)
train_df = df.iloc[:train_end].copy()
validation_df = df.iloc[train_end:validation_end].copy()
test_df = df.iloc[validation_end:].copy()

# The unsupervised models see ONLY normal entries when learning "normal".
normal_train_df = train_df[train_df[TARGET] == 0].copy()
print("Split sizes:", len(train_df), len(validation_df), len(test_df))
print("Normal records used to train anomaly models:", len(normal_train_df))


# %% Convert transaction fields into numeric ML features
preprocessor = ColumnTransformer(
    transformers=[
        ("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), numeric_features),
        ("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            # Groups very rare categorical values to control feature width.
            ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=5, sparse_output=False)),
        ]), categorical_features),
    ],
    remainder="drop",
)

# Fit preprocessing only on normal training transactions.
X_train_normal = preprocessor.fit_transform(normal_train_df).astype("float32")
X_validation = preprocessor.transform(validation_df).astype("float32")
X_test = preprocessor.transform(test_df).astype("float32")
y_validation = validation_df[TARGET].to_numpy()
y_test = test_df[TARGET].to_numpy()
print("Model input features after encoding:", X_train_normal.shape[1])


# %% Autoencoder model
class TransactionAutoencoder(nn.Module):
    """Learns a compact representation of normal transaction feature vectors."""
    def __init__(self, input_dim: int, latent_dim: int = LATENT_DIM):
        super().__init__()
        hidden_1 = max(64, min(256, input_dim * 2))
        hidden_2 = max(32, min(128, input_dim))
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_1), nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(hidden_1, hidden_2), nn.ReLU(),
            nn.Linear(hidden_2, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, hidden_2), nn.ReLU(),
            nn.Linear(hidden_2, hidden_1), nn.ReLU(),
            nn.Linear(hidden_1, input_dim),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


def reconstruction_errors(model, matrix: np.ndarray) -> np.ndarray:
    """Per-row MSE: high error means the entry looks unlike normal training data."""
    model.eval()
    errors = []
    with torch.no_grad():
        for start in range(0, len(matrix), BATCH_SIZE):
            batch = torch.tensor(matrix[start:start + BATCH_SIZE], device=DEVICE)
            reconstructed = model(batch)
            errors.extend(((batch - reconstructed) ** 2).mean(dim=1).cpu().numpy())
    return np.asarray(errors)


# %% Train Autoencoder only on normal transactions
model = TransactionAutoencoder(X_train_normal.shape[1]).to(DEVICE)
optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-5)
loss_fn = nn.MSELoss()
train_tensor = torch.tensor(X_train_normal, device=DEVICE)
best_state, best_loss, patience, wait = None, float("inf"), 10, 0
history = []

for epoch in range(1, EPOCHS + 1):
    model.train()
    permutation = torch.randperm(len(train_tensor), device=DEVICE)
    epoch_losses = []
    for start in range(0, len(train_tensor), BATCH_SIZE):
        batch = train_tensor[permutation[start:start + BATCH_SIZE]]
        optimizer.zero_grad()
        loss = loss_fn(model(batch), batch)
        loss.backward()
        optimizer.step()
        epoch_losses.append(loss.item())
    epoch_loss = float(np.mean(epoch_losses))
    history.append(epoch_loss)
    if epoch_loss < best_loss:
        best_loss, best_state, wait = epoch_loss, copy.deepcopy(model.state_dict()), 0
    else:
        wait += 1
    if epoch == 1 or epoch % 10 == 0:
        print(f"Epoch {epoch:03d} | normal-training reconstruction loss: {epoch_loss:.6f}")
    if wait >= patience:
        print(f"Early stopped at epoch {epoch}; best loss: {best_loss:.6f}")
        break

model.load_state_dict(best_state)
plt.plot(history)
plt.title("Autoencoder training reconstruction loss")
plt.xlabel("Epoch"); plt.ylabel("MSE loss"); plt.show()


# %% Train Isolation Forest on Autoencoder reconstructed normal transactions
def reconstructed_matrix(model, matrix: np.ndarray) -> np.ndarray:
    model.eval()
    output = []
    with torch.no_grad():
        for start in range(0, len(matrix), BATCH_SIZE):
            batch = torch.tensor(matrix[start:start + BATCH_SIZE], device=DEVICE)
            output.append(model(batch).cpu().numpy())
    return np.vstack(output)

X_train_reconstructed = reconstructed_matrix(model, X_train_normal)
isolation_forest = IsolationForest(
    n_estimators=300,
    contamination=ISOLATION_CONTAMINATION,
    random_state=SEED,
    n_jobs=-1,
)
isolation_forest.fit(X_train_reconstructed)


# %% Combine Autoencoder and Isolation Forest anomaly scores
def normalize_from_normal(values, normal_reference):
    """0-1 normalization calibrated only from normal training behaviour."""
    lower = np.quantile(normal_reference, 0.01)
    upper = np.quantile(normal_reference, 0.995)
    return np.clip((values - lower) / max(upper - lower, 1e-9), 0, 1)


train_ae_error = reconstruction_errors(model, X_train_normal)
train_if_score = -isolation_forest.decision_function(X_train_reconstructed)  # higher = more anomalous

def combined_score(matrix):
    ae_error = reconstruction_errors(model, matrix)
    reconstructed = reconstructed_matrix(model, matrix)
    if_score = -isolation_forest.decision_function(reconstructed)
    ae_normalized = normalize_from_normal(ae_error, train_ae_error)
    if_normalized = normalize_from_normal(if_score, train_if_score)
    return AE_WEIGHT * ae_normalized + IF_WEIGHT * if_normalized, ae_error, if_score

validation_score, _, _ = combined_score(X_validation)
test_score, test_ae_error, test_if_score = combined_score(X_test)

# Select a decision threshold on validation data only; never tune it on test data.
candidate_thresholds = np.linspace(0.05, 0.95, 181)
threshold = max(candidate_thresholds, key=lambda t: f1_score(y_validation, validation_score >= t))
y_pred = (test_score >= threshold).astype(int)
print(f"Chosen validation threshold: {threshold:.3f}")


# %% Evaluate on untouched test data
precision = precision_score(y_test, y_pred, zero_division=0)
recall = recall_score(y_test, y_pred, zero_division=0)
f1 = f1_score(y_test, y_pred, zero_division=0)
pr_auc = average_precision_score(y_test, test_score)
roc_auc = roc_auc_score(y_test, test_score)

print("\nAuditAI Autoencoder + Isolation Forest results")
print(f"Precision: {precision:.3f}")
print(f"Recall:    {recall:.3f}")
print(f"F1-score:  {f1:.3f}")
print(f"PR-AUC:    {pr_auc:.3f}")
print(f"ROC-AUC:   {roc_auc:.3f}")
print("\n", classification_report(y_test, y_pred, target_names=["Normal", "Anomaly"], zero_division=0))

fig, axes = plt.subplots(1, 3, figsize=(18, 5))
ConfusionMatrixDisplay(confusion_matrix(y_test, y_pred), display_labels=["Normal", "Anomaly"]).plot(ax=axes[0], colorbar=False)
axes[0].set_title("Confusion matrix")
PrecisionRecallDisplay.from_predictions(y_test, test_score, ax=axes[1])
axes[1].set_title(f"Precision–Recall curve (AP={pr_auc:.3f})")
RocCurveDisplay.from_predictions(y_test, test_score, ax=axes[2])
axes[2].set_title(f"ROC curve (AUC={roc_auc:.3f})")
plt.tight_layout(); plt.show()


# %% Review the most suspicious entries
review_columns = [
    "transaction_id", "transaction_date", "general_ledger_account", "vendor_name",
    "amount", "description", "is_anomaly", "risk_category", "risk_severity",
    "detected_risk_signals",
]
review = test_df[[c for c in review_columns if c in test_df.columns]].copy()
review["autoencoder_error"] = test_ae_error
review["isolation_forest_score"] = test_if_score
review["combined_anomaly_score"] = test_score
review["model_prediction"] = y_pred
review.sort_values("combined_anomaly_score", ascending=False).head(30)


# %% Save trained artifacts for use in AuditAI backend later
OUTPUT_DIR = Path("auditai_model_artifacts")
OUTPUT_DIR.mkdir(exist_ok=True)
torch.save({
    "state_dict": model.state_dict(),
    "input_dim": X_train_normal.shape[1],
    "latent_dim": LATENT_DIM,
    "threshold": float(threshold),
    "ae_weight": AE_WEIGHT,
    "if_weight": IF_WEIGHT,
}, OUTPUT_DIR / "autoencoder.pt")
joblib.dump(preprocessor, OUTPUT_DIR / "preprocessor.joblib")
joblib.dump(isolation_forest, OUTPUT_DIR / "isolation_forest.joblib")
review.to_csv(OUTPUT_DIR / "test_set_model_review.csv", index=False)
print(f"Saved model, preprocessing, Isolation Forest, and review CSV to: {OUTPUT_DIR.resolve()}")
