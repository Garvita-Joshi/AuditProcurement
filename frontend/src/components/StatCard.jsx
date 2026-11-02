import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'blue' }) {
  const colorMap = {
    blue: 'var(--accent-primary)',
    green: 'var(--status-success)',
    amber: 'var(--status-warning)',
    red: 'var(--status-danger)',
  };
  
  const activeColor = colorMap[color] || colorMap.blue;
  
  return (
    <div className="glass-card stat-card" style={{ borderLeftColor: activeColor, borderLeftWidth: '4px' }}>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-secondary text-sm font-medium uppercase tracking-wider">{title}</h3>
        <div className="stat-icon" style={{ color: activeColor, background: `${activeColor}15`, padding: '8px', borderRadius: '8px' }}>
          <Icon size={20} />
        </div>
      </div>
      <div>
        <div className="text-2xl font-bold mb-1">{value}</div>
        {subtitle && <div className="text-sm text-muted">{subtitle}</div>}
      </div>
    </div>
  );
}
