import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Filter, Search } from 'lucide-react';
import { claimsApi } from '../api/client';
import DataTable from '../components/DataTable';
import ScoreBadge from '../components/ScoreBadge';

export default function ClaimsTable() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  
  // Filters & Pagination
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('submitted_at');
  const [sortOrder, setSortOrder] = useState('desc');
  
  const navigate = useNavigate();

  const fetchClaims = async () => {
    setLoading(true);
    try {
      const params = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (statusFilter) params.status = statusFilter;
      
      const response = await claimsApi.list(params);
      setData(response.data.claims);
      setTotal(response.data.total);
    } catch (error) {
      console.error("Failed to fetch claims:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClaims();
  }, [page, statusFilter, sortBy, sortOrder]);

  const handleSort = (key) => {
    if (sortBy === key) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(key);
      setSortOrder('desc');
    }
  };

  const columns = [
    { key: 'claim_id', label: 'Claim ID', sortable: true, render: (val) => <span className="font-medium text-accent-primary">{val}</span> },
    { key: 'employee_name', label: 'Employee', sortable: true },
    { 
      key: 'vendor_name', 
      label: 'Vendor', 
      sortable: true,
      render: (val, row) => (
        <div className="flex items-center gap-2">
          <span>{val}</span>
          {row.closest_vendor_match && (
            <span 
              className="badge badge-amber text-xs flex items-center gap-1 cursor-help"
              title={`⚠ ${Math.round(row.vendor_similarity_score * 100)}% match to '${row.closest_vendor_match}' — possible typosquat`}
            >
              ⚠ Typo
            </span>
          )}
        </div>
      )
    },
    { key: 'claimed_date', label: 'Date', sortable: true },
    { key: 'claimed_amount', label: 'Amount', sortable: true, render: (val) => `₹${val.toLocaleString(undefined, {minimumFractionDigits: 2})}` },
    { key: 'status', label: 'Status', sortable: true, render: (val) => (
        <span className={`badge ${
          val === 'approved' ? 'badge-green' : 
          val === 'flagged' || val === 'rejected' ? 'badge-red' : 
          val === 'scored' ? 'badge-blue' : 'badge-amber'
        }`}>{val}</span>
      )
    },
    { key: 'fraud_score', label: 'Fraud Score', sortable: false, render: (val) => <ScoreBadge score={val} /> },
  ];

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="main-content">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl">Expense Claims</h1>
      </div>
      
      <div className="glass-card mb-6">
        <div className="flex justify-between items-center mb-4">
          <div className="flex gap-4 items-center">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted" size={16} />
              <input type="text" className="input pl-10" placeholder="Search claims..." style={{ width: 250 }} />
            </div>
            
            <div className="flex items-center gap-2">
              <Filter className="text-muted" size={16} />
              <select 
                className="input py-2" 
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                style={{ width: 160 }}
              >
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="processing">Processing</option>
                <option value="scored">Scored</option>
                <option value="flagged">Flagged</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
          </div>
          
          <div className="text-sm text-secondary">
            Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, total)} of {total} claims
          </div>
        </div>
        
        <DataTable 
          columns={columns} 
          data={data} 
          onRowClick={(row) => navigate(`/claims/${row.claim_id}`)}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSort={handleSort}
          loading={loading}
        />
        
        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div className="flex justify-center gap-2 mt-6">
            <button 
              className="btn btn-secondary" 
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
            >
              Previous
            </button>
            <span className="flex items-center px-4 text-sm text-secondary">
              Page {page} of {totalPages}
            </span>
            <button 
              className="btn btn-secondary" 
              disabled={page === totalPages}
              onClick={() => setPage(p => p + 1)}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
