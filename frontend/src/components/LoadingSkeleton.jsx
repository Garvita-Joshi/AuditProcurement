import React from 'react';
import './LoadingSkeleton.css';

export default function LoadingSkeleton({ type = 'card', count = 1 }) {
  const renderSkeleton = () => {
    switch (type) {
      case 'card':
        return (
          <div className="glass-card">
            <div className="flex justify-between mb-4">
              <div className="skeleton h-4 w-24 rounded"></div>
              <div className="skeleton h-8 w-8 rounded"></div>
            </div>
            <div className="skeleton h-8 w-16 mb-2 rounded"></div>
            <div className="skeleton h-3 w-32 rounded"></div>
          </div>
        );
      
      case 'table-row':
        return (
          <div className="flex gap-4 p-4 border-b border-glass">
            <div className="skeleton h-4 w-1/6 rounded"></div>
            <div className="skeleton h-4 w-1/4 rounded"></div>
            <div className="skeleton h-4 w-1/4 rounded"></div>
            <div className="skeleton h-4 w-1/6 rounded"></div>
            <div className="skeleton h-4 w-1/6 rounded"></div>
          </div>
        );

      case 'detail':
        return (
          <div className="glass-card">
            <div className="skeleton h-6 w-1/3 mb-6 rounded"></div>
            <div className="skeleton h-4 w-full mb-3 rounded"></div>
            <div className="skeleton h-4 w-full mb-3 rounded"></div>
            <div className="skeleton h-4 w-2/3 rounded"></div>
          </div>
        );
        
      default:
        return <div className="skeleton h-12 w-full rounded"></div>;
    }
  };

  return (
    <>
      {Array(count).fill(0).map((_, i) => (
        <React.Fragment key={i}>
          {renderSkeleton()}
        </React.Fragment>
      ))}
    </>
  );
}
