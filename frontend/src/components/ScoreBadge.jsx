import React from 'react';

export default function ScoreBadge({ score, size = 'md' }) {
  if (score === null || score === undefined) {
    return <span className="badge badge-gray">N/A</span>;
  }
  
  let colorClass = 'badge-green';
  if (score >= 0.85) {
    colorClass = 'badge-red';
  } else if (score >= 0.70) {
    colorClass = 'badge-orange';
  } else if (score >= 0.50) {
    colorClass = 'badge-amber';
  } else if (score >= 0.30) {
    colorClass = 'badge-blue';
  }
  
  const percentage = Math.round(score * 100);
  
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5'
  };
  
  return (
    <span className={`badge ${colorClass} ${sizeClasses[size]}`}>
      {percentage}%
    </span>
  );
}
