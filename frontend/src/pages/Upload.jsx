import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { claimsApi, fraudApi } from '../api/client';
import FileUpload from '../components/FileUpload';
import { Play } from 'lucide-react';

export default function Upload() {
  const [csvUploadState, setCsvUploadState] = useState('idle');
  const [rcpUploadState, setRcpUploadState] = useState('idle');
  const [rcpClaimId, setRcpClaimId] = useState('');
  const [message, setMessage] = useState(null);
  
  const navigate = useNavigate();

  const handleCsvUpload = async (file) => {
    setCsvUploadState('uploading');
    setMessage(null);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await claimsApi.upload(formData);
      setCsvUploadState('complete');
      setMessage({ type: 'success', text: res.data.message });
    } catch (err) {
      console.error(err);
      setCsvUploadState('error');
      setMessage({ 
        type: 'error', 
        text: err.response?.data?.detail || "Upload failed. Check file format." 
      });
    }
  };

  const handleReceiptUpload = async (file) => {
    setRcpUploadState('processing');
    setMessage(null);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await claimsApi.uploadReceipt(rcpClaimId, formData);
      setRcpUploadState('complete');
      setMessage({ type: 'success', text: `Receipt uploaded and processed: ${res.data.receipt_id}` });
    } catch (err) {
      console.error(err);
      setRcpUploadState('error');
      setMessage({ type: 'error', text: err.response?.data?.detail || "Receipt upload failed." });
    }
  };

  const runScoring = async () => {
    setMessage({ type: 'info', text: 'Running Autoencoder + Isolation Forest scoring pipeline...' });
    try {
      const res = await fraudApi.score();
      setMessage({ 
        type: 'success', 
        text: `Scoring complete! Scored ${res.data.scored_count} claims. Found ${res.data.flagged_count} anomalies.` 
      });
      setTimeout(() => navigate('/claims'), 3000);
    } catch (err) {
      console.error(err);
      setMessage({ type: 'error', text: err.response?.data?.detail || "Scoring pipeline failed." });
    }
  };

  return (
    <div className="main-content">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl">Data Ingestion</h1>
      </div>
      
      {message && (
        <div className={`glass-card mb-6 flex items-center p-4 border-l-4 ${
          message.type === 'error' ? 'border-status-danger' : 
          message.type === 'success' ? 'border-status-success' : 'border-accent-primary'
        }`}>
          <span>{message.text}</span>
        </div>
      )}
      
      <div className="grid-cols-2 mb-6">
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-2">1. Upload Expense Claims</h3>
          <p className="text-secondary text-sm mb-6">Upload a CSV containing employee expense claim metadata.</p>
          
          <FileUpload 
            label="Upload claims.csv" 
            accept=".csv,.json"
            onUpload={handleCsvUpload}
            uploadState={csvUploadState}
          />
          
          {csvUploadState === 'complete' && (
            <div className="mt-6 text-center">
              <button className="btn btn-primary w-full" onClick={runScoring}>
                <Play size={18} />
                Run Fraud Scoring Pipeline
              </button>
            </div>
          )}
        </div>
        
        <div className="glass-card">
          <h3 className="text-lg font-semibold mb-2">2. Upload Receipt (Optional)</h3>
          <p className="text-secondary text-sm mb-6">Attach a receipt image to an existing claim for OCR extraction.</p>
          
          <div className="mb-4">
            <label className="text-sm text-secondary mb-1 block">Target Claim ID</label>
            <input 
              type="text" 
              className="input" 
              placeholder="e.g. CLM-00001"
              value={rcpClaimId}
              onChange={(e) => setRcpClaimId(e.target.value)}
            />
          </div>
          
          <FileUpload 
            label="Upload receipt image/PDF" 
            accept="image/*,application/pdf"
            onUpload={handleReceiptUpload}
            uploadState={rcpUploadState}
          />
        </div>
      </div>
      
      <div className="glass-card">
        <h3 className="text-lg font-semibold mb-4">Pipeline Status</h3>
        <div className="flex items-center justify-between text-sm">
          <div className={`flex flex-col items-center ${csvUploadState === 'complete' ? 'text-status-success' : 'text-muted'}`}>
            <div className="w-4 h-4 rounded-full bg-current mb-2"></div>
            <span>Data Ingestion</span>
          </div>
          <div className="h-px bg-border-light flex-1 mx-4"></div>
          <div className="flex flex-col items-center text-muted">
            <div className="w-4 h-4 rounded-full bg-current mb-2"></div>
            <span>OCR Extraction</span>
          </div>
          <div className="h-px bg-border-light flex-1 mx-4"></div>
          <div className="flex flex-col items-center text-muted">
            <div className="w-4 h-4 rounded-full bg-current mb-2"></div>
            <span>Feature Engineering</span>
          </div>
          <div className="h-px bg-border-light flex-1 mx-4"></div>
          <div className="flex flex-col items-center text-muted">
            <div className="w-4 h-4 rounded-full bg-current mb-2"></div>
            <span>ML Scoring</span>
          </div>
        </div>
      </div>
    </div>
  );
}
