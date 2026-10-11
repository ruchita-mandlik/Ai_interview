import React, { useEffect, useState } from 'react';
import { OverviewAnalyticsResponse } from '../types';
import { analyticsAPI } from '../services/api';
import { Radar, Bar } from 'react-chartjs-2';
import { Chart as ChartJS, RadialLinearScale, CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend } from 'chart.js';

ChartJS.register(RadialLinearScale, CategoryScale, LinearScale, BarElement, PointElement, LineElement, Title, Tooltip, Legend);

export const Analytics: React.FC = () => {
  const [data, setData] = useState<OverviewAnalyticsResponse | null>(null);

  useEffect(() => {
    analyticsAPI.getOverview().then(setData).catch(() => {});
  }, []);

  const radarData = {
    labels: data?.topic_performance.map(t => t.topic) || ['Java', 'OOP', 'DBMS', 'OS', 'System Design'],
    datasets: [{
      label: 'Mastery Score %',
      data: data?.topic_performance.map(t => t.score) || [85, 80, 65, 60, 75],
      backgroundColor: 'rgba(139, 92, 246, 0.25)',
      borderColor: '#8B5CF6',
      borderWidth: 2,
      pointBackgroundColor: '#EC4899'
    }]
  };

  const barData = {
    labels: data?.difficulty_performance.map(d => d.difficulty) || ['Easy', 'Medium', 'Hard', 'Adaptive'],
    datasets: [{
      label: 'Average Score',
      data: data?.difficulty_performance.map(d => d.score) || [90, 80, 70, 82],
      backgroundColor: ['#10B981', '#3B82F6', '#EF4444', '#8B5CF6'],
      borderRadius: 8
    }]
  };

  return (
    <section>
      <div className="glass-card" style={{ marginBottom: '24px' }}>
        <h2>Telemetry Analytics & Skill Breakdown</h2>
        <p style={{ color: '#9CA3AF', fontSize: '14px' }}>Deep dive telemetry into topic mastery and difficulty thresholds.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <div className="glass-card" style={{ minHeight: '380px' }}>
          <h3 style={{ marginBottom: '16px' }}>Topic Mastery Breakdown</h3>
          <div style={{ height: '300px' }}>
            <Radar data={radarData} options={{ responsive: true, maintainAspectRatio: false }} />
          </div>
        </div>

        <div className="glass-card" style={{ minHeight: '380px' }}>
          <h3 style={{ marginBottom: '16px' }}>Difficulty Performance</h3>
          <div style={{ height: '300px' }}>
            <Bar data={barData} options={{ responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }} />
          </div>
        </div>
      </div>
    </section>
  );
};
