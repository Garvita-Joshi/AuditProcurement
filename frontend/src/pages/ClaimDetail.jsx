import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Check, X, Shield, Clock, FileText, ClipboardList } from 'lucide-react';
import { claimsApi, casesApi } from '../api/client';
import ScoreGauge from '../components/ScoreGauge';
import ShapChart from '../components/ShapChart';
import LoadingSkeleton from '../components/LoadingSkeleton';

export default function ClaimDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [auditTrail, setAuditTrail] = useState([]);
  
  // Case Action Fields
  const [role, setRole] = useState('maker'); // 'maker' or 'checker' (mock user switcher)
  const [notes, setNotes] = useState('');
  const [submittingAction, setSubmittingAction] = useState(false);

  const fetchDetail = async () => {
    try {
      const response = await claimsApi.getDetail(id);
      setData(response.data);
      
      // Fetch case audit trail
      const trailResponse = await casesApi.getTrail(id);
      setAuditTrail(trailResponse.data);
    } catch (error) {
      console.error("Failed to fetch claim detail:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  const handleCaseAction = async (actionType) => {
    if (!notes || notes.length < 5) {
      alert("Please provide explanatory notes (minimum 5 characters).");
      return;
    }
    setSubmittingAction(true);
    try {
      if (role === 'maker') {
        await casesApi.makerRecommend(id, actionType, notes, "Auditor (Maker)");
      } else {
        await casesApi.checkerSignoff(id, actionType, notes, "Manager (Checker)");
      }
      setNotes('');
      await fetchDetail(); // refresh data & timeline
    } catch (error) {
      console.error("Case action failed:", error);
      alert(error.response?.data?.detail || "Action failed.");
    } finally {
      setSubmittingAction(false);
    }
  };

  if (loading) {
    return (
      <div className="main-content">
        <LoadingSkeleton type="detail" count={3} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="main-content text-center py-20">
        <h2 className="text-2xl mb-4">Claim Not Found</h2>
        <button className="btn btn-secondary" onClick={() => navigate('/claims')}>Back to Claims</button>
      </div>
    );
  }

  const { claim, ocr_result, prediction, audit_report } = data;

  return (
    <div className="main-content">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-4">
          <button className="text-secondary hover:text-primary" onClick={() => navigate('/claims')}>
            <ArrowLeft size={24} />
          </button>
          <div className="flex flex-col">
            <span className="text-xs text-muted font-medium">APAC Entity · INR</span>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold">{claim.claim_id}</h1>
              <span className={`badge ${
                claim.status === 'approved' ? 'badge-green' : 
                claim.status === 'flagged' || claim.status === 'rejected' ? 'badge-red' : 
                claim.status === 'scored' ? 'badge-blue' : 'badge-amber'
              }`}>{claim.status.toUpperCase()}</span>
            </div>
          </div>
        </div>
        
        {/* Mock Role Switcher */}
        <div className="flex items-center gap-2 glass-card" style={{ padding: '8px 16px', borderRadius: '12px' }}>
          <span className="text-xs text-muted uppercase font-semibold">Active Reviewer Role:</span>
          <select 
            className="input py-1 px-2 text-xs font-semibold"
            value={role}
            onChange={e => setRole(e.target.value)}
            style={{ width: 100, background: 'none', border: '1px solid rgba(255,255,255,0.1)' }}
          >
            <option value="maker">Maker</option>
            <option value="checker">Checker</option>
          </select>
        </div>
      </div>
      
      {/* Top Grid: Metadata, OCR, Risk Gauges */}
      <div className="grid-cols-3 mb-6">
        {/* Left: Metadata */}
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-4 text-accent-primary">Claim Details</h3>
          <div className="flex flex-col gap-3 text-sm">
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Employee</span>
              <span className="font-medium">{claim.employee_name} ({claim.employee_id})</span>
            </div>
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Vendor</span>
              <span className="font-medium flex items-center gap-2">
                {claim.vendor_name}
                {claim.closest_vendor_match && (
                  <span 
                    className="badge badge-amber text-xs flex items-center gap-1 cursor-help"
                    title={`⚠ ${Math.round(claim.vendor_similarity_score * 100)}% match to '${claim.closest_vendor_match}' — possible typosquat`}
                  >
                    ⚠ Typo
                  </span>
                )}
              </span>
            </div>
            {claim.closest_vendor_match && (
              <div className="bg-status-warning/10 border border-status-warning/30 rounded p-2 text-xs text-secondary mt-1">
                ⚠️ Typosquat Alert: Similarity score is {Math.round(claim.vendor_similarity_score * 100)}% compared to known vendor <strong>{claim.closest_vendor_match}</strong>.
              </div>
            )}
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Amount</span>
              <span className="font-medium text-lg">₹{claim.claimed_amount.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
            </div>
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Date</span>
              <span className="font-medium">{claim.claimed_date}</span>
            </div>
            <div className="flex justify-between border-b border-glass pb-2">
              <span className="text-secondary">Category</span>
              <span className="font-medium">{claim.category || 'N/A'}</span>
            </div>
          </div>
        </div>
        
        {/* Center: OCR */}
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-4 text-accent-primary">OCR Extraction</h3>
          {!ocr_result ? (
            <p className="text-secondary italic">No receipt processed for this claim.</p>
          ) : (
            <div className="flex flex-col gap-3 text-sm">
              <div className="flex justify-between border-b border-glass pb-2">
                <span className="text-secondary">Extracted Vendor</span>
                <span className={`font-medium ${ocr_result.extracted_vendor?.toLowerCase() !== claim.vendor_name.toLowerCase() ? 'text-status-warning' : ''}`}>
                  {ocr_result.extracted_vendor || 'None'}
                </span>
              </div>
              <div className="flex justify-between border-b border-glass pb-2">
                <span className="text-secondary">Extracted Amount</span>
                <span className={`font-medium ${ocr_result.extracted_amount && Math.abs(ocr_result.extracted_amount - claim.claimed_amount) > 1 ? 'text-status-danger' : ''}`}>
                  {ocr_result.extracted_amount ? `₹${ocr_result.extracted_amount}` : 'None'}
                </span>
              </div>
              <div className="flex justify-between border-b border-glass pb-2">
                <span className="text-secondary">Extraction Method</span>
                <span className="font-medium">{ocr_result.extraction_method}</span>
              </div>
              <div className="mt-2">
                <span className="text-secondary block mb-1">Raw Text Snippet:</span>
                <div className="mono-pre" style={{ maxHeight: '90px' }}>
                  {ocr_result.raw_ocr_text ? ocr_result.raw_ocr_text.substring(0, 150) + '...' : 'No text'}
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Right: Scores */}
        <div className="glass-card flex flex-col justify-center">
          <h3 className="text-lg font-semibold mb-2 text-center text-accent-primary">Fraud Risk Assessment</h3>
          {!prediction ? (
            <p className="text-secondary text-center italic mt-4">Not scored yet.</p>
          ) : (
            <>
              <div className="flex justify-center mb-6">
                <ScoreGauge label="Combined Score" score={prediction.combined_fraud_score} size={180} />
              </div>
              <div className="flex justify-around">
                <div className="text-center">
                  <div className="text-xs text-secondary uppercase mb-1">Reconstruction Err</div>
                  <div className="font-bold">{(prediction.reconstruction_error * 100).toFixed(1)}%</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-secondary uppercase mb-1">Isolation Forest</div>
                  <div className="font-bold">{(prediction.isolation_forest_score * 100).toFixed(1)}%</div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      
      {/* SHAP explainability */}
      <div className="grid-cols-3 mb-6">
        <div className="col-span-2 h-[380px]" style={{ gridColumn: 'span 2' }}>
          {prediction?.shap_values ? (
            <ShapChart shapValues={prediction.shap_values} maxFeatures={6} />
          ) : (
            <div className="glass-card flex items-center justify-center h-full">
              <p className="text-secondary">SHAP explainability not available.</p>
            </div>
          )}
        </div>

        {/* Maker-Checker Investigation / Action Drawer */}
        <div className="glass-card flex flex-col justify-between">
          <div>
            <h3 className="text-lg font-semibold mb-3 flex items-center gap-2 text-accent-primary">
              <Shield size={20} />
              Case Review
            </h3>
            
            <div className="text-xs text-secondary mb-4">
              <strong>Status:</strong> <span className="badge badge-gray text-xs">{claim.case_status?.replace(/_/g, ' ')}</span>
            </div>

            {/* Display Maker Recommendation to Checker */}
            {role === 'checker' && claim.case_status?.startsWith('maker_recommended') && (
              <div className="bg-bg-surface border border-border-light rounded p-3 mb-4 text-xs">
                <div className="font-semibold text-accent-primary mb-1">Maker Recommendation:</div>
                <div className="text-secondary italic mb-2">"{data.claim.maker_notes || 'No comments left.'}"</div>
                <div>Recommended: <strong>{claim.case_status === 'maker_recommended_approve' ? 'APPROVE' : 'REJECT'}</strong></div>
              </div>
            )}

            <div className="mb-4">
              <label className="text-xs text-secondary mb-1 block">Reviewer Notes / Justification</label>
              <textarea 
                className="input text-xs" 
                rows="4"
                placeholder={`Provide audit commentary justifying your decision...`}
                value={notes}
                onChange={e => setNotes(e.target.value)}
                style={{ resize: 'none' }}
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button 
              className="btn btn-success flex-1 py-2 text-xs"
              onClick={() => handleCaseAction('approve')}
              disabled={submittingAction}
            >
              <Check size={14} /> Recommend Approve
            </button>
            <button 
              className="btn btn-danger flex-1 py-2 text-xs"
              onClick={() => handleCaseAction('reject')}
              disabled={submittingAction}
            >
              <X size={14} /> Recommend Reject
            </button>
          </div>
        </div>
      </div>
      
      {/* Audit Report and Case Audit Trail Timeline */}
      <div className="grid-cols-2 mb-6">
        {/* Left: AI Audit Report */}
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <FileText className="text-accent-primary" />
            AI Audit Report Summary
          </h3>
          
          {audit_report ? (
            <div className="bg-bg-surface p-6 rounded-lg border border-border-light relative overflow-hidden h-[240px] overflow-y-auto">
              <div className="absolute top-0 left-0 w-1 h-full bg-accent-primary"></div>
              <p className="text-sm italic leading-relaxed text-secondary">{audit_report.report_text}</p>
              <div className="mt-4 text-xs text-muted text-right">
                Generated by {audit_report.generated_by}
              </div>
            </div>
          ) : (
            <div className="bg-bg-surface p-6 rounded-lg border border-border-light text-center h-[240px] flex items-center justify-center">
              <p className="text-secondary italic">Audit reports are only generated for flagged claims.</p>
            </div>
          )}
        </div>

        {/* Right: Append-Only Investigation Timeline */}
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <ClipboardList className="text-accent-primary" />
            Audit Case Timeline
          </h3>
          
          <div className="bg-bg-surface p-4 rounded-lg border border-border-light h-[240px] overflow-y-auto">
            {auditTrail.length === 0 ? (
              <p className="text-secondary text-center italic py-10">No investigation timeline logged.</p>
            ) : (
              <div className="timeline">
                {auditTrail.map((log, idx) => (
                  <div key={log.id || idx} className="flex gap-3 mb-4 text-xs">
                    <div className="flex flex-col items-center">
                      <div className="w-3 h-3 rounded-full bg-accent-primary"></div>
                      {idx < auditTrail.length - 1 && <div className="w-0.5 bg-border-light flex-1 my-1"></div>}
                    </div>
                    <div>
                      <div className="font-semibold text-secondary">
                        Action: <span className="text-primary uppercase">{log.action.replace(/_/g, ' ')}</span> by {log.performed_by.toUpperCase()}
                      </div>
                      {log.notes && <div className="text-muted italic mt-1">"{log.notes}"</div>}
                      <div className="text-[10px] text-muted mt-1">{new Date(log.timestamp).toLocaleString()}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
