# Procurement model contract

The model is a review aid. Hard agreement mismatches always block payment.

Feature order (procurement-v1):

1. `amount_log`: log(1 + invoice total).
2. `item_count`: distinct invoice item count.
3. `quantity_total`: sum of item quantities.
4. `delivery_ratio`: delivery / max(total, 1).
5. `tax_ratio`: tax / max(total, 1).
6. `po_difference_ratio`: absolute difference / max(PO total, 1).
7. `supplier_history_count`: count of prior paid invoices in this workspace.
8. `supplier_amount_ratio`: invoice total / max(median prior paid amounts, 1);
   zero when no paid supplier history exists.

Processing: fitted MinMaxScaler -> autoencoder -> decoded output -> Isolation
Forest. The AE reconstruction error is also retained. Each raw anomaly score is
mapped to its percentile in the saved normal validation distribution. These
percentiles are not fraud probabilities. No scaling is fitted during inference.

The current model is trained on synthetic feature distributions. Each split uses
an independent random seed. This is not evidence of temporal generalization or
performance on real supplier invoices. Normal simulation includes some bulk
orders; injected anomalies include fee discrepancies, large purchases, new
suppliers with unusually large invoices, and extreme quantities.

Training script: `python -m scripts.train_procurement_model`. Evaluate before
using a different feature schema or dataset; do not silently reuse expense-model
weights for supplier invoices. The app reports unavailable when the artifact is
missing or incompatible and still requires independent finance review.

The initial synthetic test produced 226 true positives, 274 false negatives,
45 false positives and 1,455 true negatives. The substantial missed-anomaly count
is a practical limitation. Exact invoice rules and human review remain necessary.
