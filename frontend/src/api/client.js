import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

let accessToken = null;
let refreshPromise = null;
export const setAccessToken = (token) => { accessToken = token; };

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const isAuthRequest = original?.url?.startsWith('/auth/');
    if (error.response?.status !== 401 || original?._retried || isAuthRequest) return Promise.reject(error);
    original._retried = true;
    try {
      refreshPromise ??= api.post('/auth/refresh').then(({ data }) => {
        setAccessToken(data.access_token); return data.access_token;
      }).finally(() => { refreshPromise = null; });
      const token = await refreshPromise;
      original.headers.Authorization = `Bearer ${token}`;
      return api(original);
    } catch (refreshError) {
      setAccessToken(null); window.dispatchEvent(new Event('auditai:session-expired'));
      return Promise.reject(refreshError);
    }
  },
);

export const authApi = {
  requestOtp: (payload) => api.post('/auth/request-otp', payload),
  verifyOtp: (payload) => api.post('/auth/verify-otp', payload),
  refresh: () => api.post('/auth/refresh'),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
};

export const claimsApi = {
  list: (params) => api.get('/claims', { params }), getDetail: (claimId) => api.get(`/claims/${claimId}`),
  upload: (formData) => api.post('/claims/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  uploadReceipt: (claimId, formData) => api.post(`/receipts/upload?claim_id=${claimId}`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
};
export const fraudApi = { summary: () => api.get('/fraud/summary'), score: () => api.post('/fraud/score'), train: () => api.post('/fraud/train') };
export const reportsApi = { generate: (claimId) => api.post(`/reports/generate/${claimId}`), generateAll: () => api.post('/reports/generate-all') };
export const casesApi = {
  list: (params) => api.get('/cases', { params }), makerRecommend: (claimId, action, notes, makerId) => api.post(`/cases/${claimId}/maker-recommend`, null, { params: { action, notes, maker_id: makerId } }),
  checkerSignoff: (claimId, action, notes, checkerId) => api.post(`/cases/${claimId}/checker-signoff`, null, { params: { action, notes, checker_id: checkerId } }), getTrail: (claimId) => api.get(`/cases/${claimId}/trail`),
};
export const controlPointsApi = {
  init: () => api.post('/control-points/init'),
  transactions: (sortByRisk = true) => api.get('/transactions', { params: { sort_by_risk: sortByRisk } }),
  forTransaction: (id) => api.get(`/transactions/${id}/control-points`),
  evaluate: (id) => api.post(`/transactions/${id}/control-points/evaluate`),
  assertionRisks: () => api.get('/accounts/assertion-risk'),
  trend: (id) => api.get(`/ratios/${id}/trend`),
  uploadLedger: (formData, sourceName) => api.post(`/ledger/upload?source_name=${encodeURIComponent(sourceName)}`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
};
export const analyticsApi = { benford: () => api.get('/analytics/benford'), relatedParties: () => api.get('/analytics/related-parties'), sodViolations: () => api.get('/analytics/sod-violations'), caseMetrics: () => api.get('/analytics/case-metrics') };
export default api;

export const procurementApi = {
  extractQuote: (file) => { const data = new FormData(); data.append('file', file); return api.post('/procurement/extract-quote', data, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 60000 }); },
  list: () => api.get('/procurement/requests'),
  detail: (id) => api.get(`/procurement/requests/${id}`),
  create: (payload) => api.post('/procurement/requests', payload),
  decision: (id, payload) => api.post(`/procurement/requests/${id}/decision`, payload),
  updateStep: (requestId, stepId, payload) => api.patch(`/procurement/requests/${requestId}/steps/${stepId}`, payload),
  decideStep: (requestId, stepId, payload) => api.post(`/procurement/requests/${requestId}/steps/${stepId}/decision`, payload),
  updateSubtask: (requestId, stepId, subtaskId, payload) => api.patch(`/procurement/requests/${requestId}/steps/${stepId}/subtasks/${subtaskId}`, payload),
  reviewers: () => api.get('/procurement/reviewers'),
  notifications: () => api.get('/procurement/notifications'),
  readNotification: (id) => api.post(`/procurement/notifications/${id}/read`),
  comment: (id, note) => api.post(`/procurement/requests/${id}/comments`, { note }),
  resubmit: (id, note) => api.post(`/procurement/requests/${id}/resubmit`, { note }),
  invoice: (id, payload) => api.post(`/procurement/orders/${id}/invoices`, payload),
  correct: (id, payload) => api.post(`/procurement/invoices/${id}/correct`, payload),
  correction: (id) => api.post(`/procurement/invoices/${id}/request-correction`),
  review: (id, note) => api.post(`/procurement/invoices/${id}/review`, { note }),
  revisions: (id) => api.get(`/procurement/invoices/${id}/revisions`),
  upload: (id, file, kind = 'supporting') => { const data = new FormData(); data.append('file', file); return api.post(`/procurement/requests/${id}/documents?kind=${kind}`, data, { headers: { 'Content-Type': 'multipart/form-data' } }); },
  download: (id) => api.get(`/procurement/documents/${id}`, { responseType: 'blob' }),
  paymentConfig: () => api.get('/procurement/payment-config'),
  checkout: (id) => api.post(`/procurement/invoices/${id}/checkout`),
  capture: (id) => api.post(`/procurement/invoices/${id}/capture`),
  paymentStatus: (id) => api.post(`/procurement/invoices/${id}/payment-status`),
};

export const sourcingApi = {
  workflow: id => api.post(`/sourcing/${id}/workflow`, {}, {timeout:60000}),
  search: (id,version) => api.post(`/sourcing/${id}/search`,{version}),
  searches: id => api.get(`/sourcing/${id}/searches`),
  document: (id,file,version) => {const body=new FormData();body.append('file',file);body.append('version',version);return api.post(`/sourcing/${id}/instruction-document`,body,{headers:{'Content-Type':'multipart/form-data'},timeout:60000});},
  contractDocuments: id => api.get(`/sourcing/${id}/contract-documents`),
  uploadContractDocument: (id,kind,file) => {const body=new FormData();body.append('kind',kind);body.append('file',file);return api.post(`/sourcing/${id}/contract-documents`,body,{headers:{'Content-Type':'multipart/form-data'}});},
  config: () => api.get('/sourcing/config'),
  list: () => api.get('/sourcing'),
  create: () => api.post('/sourcing'),
  message: (id, text, version) => api.post(`/sourcing/${id}/messages`, {text, version}, {timeout:60000}),
  save: (id, requirements, version, confirm=false) => api.put(`/sourcing/${id}`, {requirements, version, confirm}),
  startAgent: id => api.post(`/sourcing/${id}/agent/runs`, {}, {timeout:120000}),
  latestAgentRun: id => api.get(`/sourcing/${id}/agent/runs/latest`),
  agentConfig: () => api.get('/sourcing/agent/config'),
  sendAgentOutreach: (id,runId,vendorIds) => api.post(`/sourcing/${id}/agent/runs/${runId}/outreach`, {vendor_ids:vendorIds,confirm_send:true}, {timeout:60000}),
  recordAgentReply: (id,runId,vendorId,text) => api.post(`/sourcing/${id}/agent/runs/${runId}/vendors/${vendorId}/reply`, {text}),
  externalSearch: (id, query, location) => api.post(`/sourcing/${id}/agent/external-search`, {query, location}, {timeout:60000}),
  addVendor: (id, runId, payload) => api.post(`/sourcing/${id}/agent/runs/${runId}/vendors`, payload),
  reviewRfq: (id, runId, vendorId, payload) =>
    api.put(`/sourcing/${id}/agent/runs/${runId}/vendors/${vendorId}/rfq-review`, payload),
  sendAiRfqs: (id, runId, vendorIds) =>
    api.post(`/sourcing/${id}/agent/runs/${runId}/send-rfqs`, { vendor_ids: vendorIds, compose_with_ai: false, confirm_send: true }, { timeout: 120000 }),
  analyzeResponses: (id, runId) =>
    api.post(`/sourcing/${id}/agent/runs/${runId}/analyze`, {}, { timeout: 90000 }),
  getAgentRun: (id, runId) => api.get(`/sourcing/${id}/agent/runs/${runId}`),
  activityStreamUrl: (id, runId, token) =>
    `${api.defaults.baseURL}/sourcing/${id}/agent/runs/${runId}/activity-stream?token=${token}`,
  getSmtpStatus: () => api.get('/sourcing/smtp/status'),
  saveSmtpConfig: payload => api.post('/sourcing/smtp/config', payload),
  testSmtp: payload => api.post('/sourcing/smtp/test', payload),
  testInbox: () => api.post('/sourcing/smtp/test-inbox', {}),
  simulateVendorQuote: (id, runId, vendorId) => api.post(`/sourcing/${id}/agent/runs/${runId}/vendors/${vendorId}/simulate-quote`),
  simulateAllQuotes: (id, runId) => api.post(`/sourcing/${id}/agent/runs/${runId}/simulate-quotes`),
  getNegotiationReport: (id, runId) => api.post(`/sourcing/${id}/agent/runs/${runId}/negotiation-report`, {}, { timeout: 90000 }),
  checkInbox: (id, runId) => api.post(`/sourcing/${id}/agent/runs/${runId}/check-inbox`, {}, { timeout: 60000 }),
  sendCounteroffer: (id, runId, vendorId, payload) =>
    api.post(`/sourcing/${id}/agent/runs/${runId}/vendors/${vendorId}/send-counteroffer`, payload, { timeout: 60000 }),
};
