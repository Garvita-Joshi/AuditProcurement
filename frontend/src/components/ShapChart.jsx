import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

export default function ShapChart({ shapValues, maxFeatures = 10 }) {
  if (!shapValues || Object.keys(shapValues).length === 0) {
    return (
      <div className="glass-card text-center py-12">
        <p className="text-secondary">No explanation data available.</p>
      </div>
    );
  }

  // Convert to array and sort by absolute magnitude
  const data = Object.entries(shapValues)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value))
    .slice(0, maxFeatures)
    .reverse(); // Reverse for horizontal chart (biggest at top)

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="glass-card" style={{ padding: '12px' }}>
          <p className="font-semibold">{data.name}</p>
          <p className={data.value > 0 ? "text-status-danger" : "text-status-success"}>
            Impact: {data.value.toFixed(4)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="glass-card h-full">
      <h3 className="text-lg font-semibold mb-6">Feature Importance (SHAP)</h3>
      <div style={{ height: '300px', width: '100%' }}>
        <ResponsiveContainer>
          <BarChart
            layout="vertical"
            data={data}
            margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" />
            <YAxis 
              type="category" 
              dataKey="name" 
              tick={{ fontSize: 12 }} 
              width={140}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {data.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={entry.value > 0 ? 'var(--status-danger)' : 'var(--status-success)'} 
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex justify-center gap-6 mt-4 text-sm">
        <div className="flex items-center gap-2">
          <div style={{ width: 12, height: 12, background: 'var(--status-danger)', borderRadius: 2 }}></div>
          <span className="text-secondary">Pushes toward Fraud</span>
        </div>
        <div className="flex items-center gap-2">
          <div style={{ width: 12, height: 12, background: 'var(--status-success)', borderRadius: 2 }}></div>
          <span className="text-secondary">Pushes toward Normal</span>
        </div>
      </div>
    </div>
  );
}
