"""Adapters that expose existing expense-claim analytics as Control Points."""
import math
from .framework import Category, Status, result

class OutlierAnomaly:
    id="outlier_anomaly"; name="Outlier Anomaly"; description="Uses the existing Autoencoder and Isolation Forest model score."; category=Category.STATISTICAL
    def evaluate(self, claim, context):
        prediction=claim.prediction; score=float(prediction.combined_fraud_score) if prediction else None
        if score is None: return result(self,Status.PASS,0,"This claim has not been scored by the ML pipeline yet.")
        status=Status.FAIL_HIGH if score>=.75 else Status.FAIL_MEDIUM if score>=.6 else Status.FAIL_LOW if score>=.4 else Status.PASS
        return result(self,status,score*100,f"Existing Autoencoder + Isolation Forest score: {score:.2f}.",reconstruction_error=float(prediction.reconstruction_error or 0),isolation_forest_score=float(prediction.isolation_forest_score or 0),shap_values=prediction.shap_values or {})

class ClaimRelatedParty:
    id="related_party"; name="Related Party"; description="Checks meaningful overlap between claimant and vendor names."; category=Category.RELATED_PARTY
    def evaluate(self,claim,context):
        words={x.lower() for x in claim.employee_name.split() if len(x)>=3}; matched=sorted(x for x in words if x in claim.vendor_name.lower())
        return result(self,Status.FAIL_HIGH if matched else Status.PASS,88 if matched else 0,f"Claimant and vendor share: {', '.join(matched)}." if matched else "No meaningful claimant-vendor name overlap found.",matched_terms=matched)

class ClaimBenford:
    id="benford_first_digit"; name="Benford First Digit"; description="Shows the claim's contribution to first-digit population deviation."; category=Category.STATISTICAL
    def evaluate(self,claim,context):
        digits=[int(str(int(float(c.claimed_amount))).lstrip("0")[0]) for c in context if float(c.claimed_amount)>0]
        if len(digits)<30:return result(self,Status.PASS,0,"At least 30 claims are required for Benford analysis.")
        digit=int(str(int(float(claim.claimed_amount))).lstrip("0")[0]); observed=digits.count(digit)/len(digits); expected=math.log10(1+1/digit); deviation=abs(observed-expected)/expected
        return result(self,Status.FAIL_LOW if deviation>.35 else Status.PASS,min(85,deviation*100) if deviation>.35 else 0,f"Leading digit {digit}: {observed:.1%} observed vs {expected:.1%} expected.",digit=digit,observed=observed,expected=expected)

CLAIM_CONTROLS=(OutlierAnomaly(),ClaimRelatedParty(),ClaimBenford())
