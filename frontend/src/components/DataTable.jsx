import React from 'react';
import { ArrowUp, ArrowDown } from 'lucide-react';

export default function DataTable({ columns, data, onRowClick, sortBy, sortOrder, onSort, loading }) {
  if (loading) {
    return (
      <div className="table-container">
        <table>
          <thead>
            <tr>
              {columns.map(col => <th key={col.key}>{col.label}</th>)}
            </tr>
          </thead>
          <tbody>
            {[1, 2, 3, 4, 5].map(i => (
              <tr key={i}>
                {columns.map(col => (
                  <td key={`${i}-${col.key}`}>
                    <div className="skeleton" style={{ height: '20px', width: '80%', borderRadius: '4px' }}></div>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="glass-card text-center py-12">
        <p className="text-secondary">No data available.</p>
      </div>
    );
  }

  return (
    <div className="table-container">
      <table>
        <thead>
          <tr>
            {columns.map(col => (
              <th 
                key={col.key}
                onClick={() => col.sortable && onSort && onSort(col.key)}
                style={{ cursor: col.sortable ? 'pointer' : 'default' }}
              >
                <div className="flex items-center gap-2">
                  {col.label}
                  {col.sortable && sortBy === col.key && (
                    sortOrder === 'desc' ? <ArrowDown size={14} /> : <ArrowUp size={14} />
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, idx) => (
            <tr 
              key={row.id || idx} 
              onClick={() => onRowClick && onRowClick(row)}
              style={{ cursor: onRowClick ? 'pointer' : 'default' }}
            >
              {columns.map(col => (
                <td key={col.key}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
