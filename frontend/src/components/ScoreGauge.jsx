import React from 'react';

export default function ScoreGauge({ label, score, size = 160 }) {
  const percentage = score !== undefined && score !== null ? Math.round(score * 100) : null;
  
  // Color logic
  let color = 'var(--status-success)';
  if (percentage >= 65) color = 'var(--status-danger)';
  else if (percentage >= 30) color = 'var(--status-warning)';

  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * Math.PI; // Semi-circle
  const strokeDashoffset = percentage !== null 
    ? circumference - (percentage / 100) * circumference 
    : circumference;

  return (
    <div className="flex flex-col items-center">
      <div style={{ width: size, height: size / 2 + 10, position: 'relative' }}>
        <svg width={size} height={size / 2} style={{ transform: 'rotate(180deg)' }}>
          {/* Background Arc */}
          <path
            d={`M ${strokeWidth/2} ${size/2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth/2} ${size/2}`}
            fill="none"
            stroke="var(--border-light)"
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          {/* Value Arc */}
          {percentage !== null && (
            <path
              d={`M ${strokeWidth/2} ${size/2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth/2} ${size/2}`}
              fill="none"
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeDashoffset}
              style={{ transition: 'stroke-dashoffset 1s ease-in-out, stroke 0.5s ease' }}
            />
          )}
        </svg>
        <div 
          className="absolute text-center" 
          style={{ bottom: 0, left: 0, right: 0 }}
        >
          {percentage !== null ? (
            <div className="text-3xl font-bold" style={{ color }}>{percentage}%</div>
          ) : (
            <div className="text-xl font-bold text-muted">N/A</div>
          )}
        </div>
      </div>
      <div className="text-sm text-secondary mt-2 text-center uppercase tracking-wider font-medium">{label}</div>
    </div>
  );
}
