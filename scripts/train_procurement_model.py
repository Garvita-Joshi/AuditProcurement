"""Train the requested decoded-AE -> Isolation Forest procurement pipeline.

Run: python -m scripts.train_procurement_model
All records are synthetic. Test metrics describe this simulator, not real fraud.
"""
import json
from pathlib import Path
import numpy as np
import torch
import joblib
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score, confusion_matrix
from backend.app.config import TRAINED_MODELS_DIR, DATA_DIR
from backend.app.ml.autoencoder import ExpenseAutoencoder
from backend.app.procurement.risk import FEATURE_NAMES


def population(count, seed, anomalous=False):
    rng = np.random.default_rng(seed)
    items = rng.integers(1, 6, count)
    qty = items * rng.integers(1, 35, count)
    typical_unit = rng.choice([12, 25, 70, 180], count)
    amount = qty * typical_unit * rng.lognormal(0, .13, count)
    delivery = rng.uniform(0, .06, count)
    tax = rng.choice([0, .05, .10], count)
    history = rng.integers(5, 160, count)
    ratio = rng.lognormal(0, .22, count)
    mismatch = np.zeros(count)
    x = np.column_stack([np.log1p(amount), items, qty, delivery, tax, mismatch, history, ratio]).astype(float)
    # Legitimate bulk purchases remain in the normal population.
    bulk = rng.choice(count, max(1, count//12), replace=False)
    x[bulk, 0] += np.log(2)
    x[bulk, 2] *= 2
    x[bulk, 7] *= 1.8
    if anomalous:
        kinds = rng.integers(0, 4, count)
        for i, kind in enumerate(kinds):
            if kind == 0:  # unapproved fee / changed invoice
                x[i, 5] = rng.uniform(.15, .8)
                x[i, 3] += rng.uniform(.15, .4)
            elif kind == 1:  # unusual purchase even when its PO agrees
                x[i, 0] += np.log(rng.uniform(4, 12))
                x[i, 7] *= rng.uniform(5, 15)
            elif kind == 2:  # new supplier, high ticket and no comparable history
                x[i, 6] = 0
                x[i, 7] = 0
                x[i, 0] += np.log(rng.uniform(3, 7))
            else:  # extreme quantity compared with normal purchasing
                x[i, 2] *= rng.uniform(5, 15)
                x[i, 0] += np.log(4)
                x[i, 7] *= 4
    return x


def main():
    torch.manual_seed(42)
    np.random.seed(42)
    torch.set_num_threads(2)
    train = population(6000, 42)
    validation = population(1500, 84)
    test = np.vstack([population(1500, 126), population(500, 168, True)])
    labels = np.r_[np.zeros(1500), np.ones(500)]
    scaler = MinMaxScaler().fit(train)
    train_x = scaler.transform(train).astype('float32')
    model = ExpenseAutoencoder(len(FEATURE_NAMES), latent_dim=3)
    optimizer = torch.optim.Adam(model.parameters(), lr=.002)
    loader = torch.utils.data.DataLoader(torch.tensor(train_x), batch_size=128, shuffle=True)
    model.train()
    for epoch in range(60):
        losses = []
        for batch in loader:
            optimizer.zero_grad()
            loss = torch.mean((batch - model(batch)) ** 2)
            loss.backward()
            optimizer.step()
            losses.append(loss.item())
        if epoch in {0, 19, 39, 59}:
            print(f"Epoch {epoch+1}/60 · reconstruction MSE {np.mean(losses):.6f}")
    model.eval()
    def decode(raw):
        scaled = scaler.transform(raw).astype('float32')
        with torch.no_grad():
            output = model(torch.tensor(scaled)).numpy()
        return scaled, output
    _, decoded_train = decode(train)
    forest = IsolationForest(n_estimators=200, contamination='auto', random_state=42, n_jobs=2).fit(decoded_train)
    val_x, val_decoded = decode(validation)
    ae_reference = np.sort(np.mean((val_x-val_decoded)**2, axis=1))
    if_reference = np.sort(-forest.score_samples(val_decoded))
    def scores(raw):
        x, decoded = decode(raw)
        ae = np.mean((x-decoded)**2, axis=1)
        isolation = -forest.score_samples(decoded)
        return .4*np.searchsorted(ae_reference, ae, side='right')/len(ae_reference) + .6*np.searchsorted(if_reference, isolation, side='right')/len(if_reference)
    threshold = float(np.quantile(scores(validation), .975))
    scored = scores(test)
    predicted = scored >= threshold
    tn, fp, fn, tp = confusion_matrix(labels, predicted).ravel()
    report = {
        "data_source":"Synthetic procurement simulator; not real fraud validation",
        "architecture":"8 features -> Autoencoder decoded output -> Isolation Forest; 0.4 AE percentile + 0.6 IF percentile",
        "split":"Independent random seeds; normal-only training and validation; held-out normal and injected anomalies for testing",
        "training_rows":len(train),"validation_rows":len(validation),"test_rows":len(test),"test_anomalies":int(labels.sum()),
        "threshold":threshold,"precision":float(precision_score(labels,predicted,zero_division=0)),
        "recall":float(recall_score(labels,predicted)),"f1":float(f1_score(labels,predicted)),
        "average_precision":float(average_precision_score(labels,scored)),
        "false_positive_rate":float(fp/(fp+tn)),
        "confusion_matrix":{"true_negative":int(tn),"false_positive":int(fp),"false_negative":int(fn),"true_positive":int(tp)},
        "feature_names":FEATURE_NAMES,
        "limitations":["Synthetic feature distributions and hand-designed anomalies can overstate real-world usefulness.",
                      "Missing supplier history may be unusual; new suppliers require human review, not a fraud conclusion.",
                      "No real-world fraud probability calibration, independent field validation or drift evaluation."]}
    target = TRAINED_MODELS_DIR
    target.mkdir(parents=True, exist_ok=True)
    bundle = {"version":"procurement-v1-synthetic", "feature_names":FEATURE_NAMES,"scaler":scaler,
              "latent_dim":3,"ae_state":model.state_dict(),"isolation_forest":forest,
              "if_input":"decoded", "ae_weight":.4,"ae_reference":ae_reference,"if_reference":if_reference,"threshold":threshold,
              "training_source":"synthetic", "evaluation":report}
    joblib.dump(bundle, target/'procurement_bundle.joblib')
    (target/'procurement_evaluation.json').write_text(json.dumps(report, indent=2))
    folder=DATA_DIR/'procurement'
    folder.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(folder/'synthetic_evaluation.npz', features=test, labels=labels, scores=scored)
    print(json.dumps({k:report[k] for k in ('precision','recall','false_positive_rate','threshold')},indent=2))
    print('Saved model bundle and synthetic evaluation report.')


if __name__ == '__main__':
    main()
