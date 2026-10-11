import React, { useEffect, useState } from 'react';
import { PreparationPlanResponse } from '../types';
import { recommendationAPI } from '../services/api';
import { Calendar, Clock, RotateCw } from 'lucide-react';

export const StudyPlan: React.FC = () => {
  const [plan, setPlan] = useState<PreparationPlanResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchPlan();
  }, []);

  const fetchPlan = async () => {
    setLoading(true);
    try {
      const res = await recommendationAPI.getPlan();
      setPlan(res);
    } catch (err: any) {
    } finally {
      setLoading(false);
    }
  };

  return (
    <section>
      <div className="glass-card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2><Calendar className="gradient-icon" size={24} style={{ display: 'inline', marginRight: '8px' }} /> 7-Day Personalized AI Preparation Plan</h2>
          <p style={{ color: '#9CA3AF', fontSize: '14px', marginTop: '4px' }}>
            {plan?.overall_readiness_assessment || "Loading assessment..."}
          </p>
        </div>
        <button className="btn btn-secondary" onClick={fetchPlan} disabled={loading}>
          <RotateCw size={16} /> Refresh
        </button>
      </div>

      <div className="plan-days-grid">
        {plan?.plan.map(day => (
          <div key={day.day} className="glass-card day-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <span style={{ fontSize: '12px', fontWeight: 800, color: '#8B5CF6' }}>DAY {day.day}</span>
              <span style={{ fontSize: '11px', color: '#6B7280' }}><Clock size={12} style={{ display: 'inline', marginRight: '4px' }} /> {day.estimated_time}</span>
            </div>

            <h4 style={{ fontSize: '17px', fontWeight: 700, marginBottom: '12px' }}>{day.topic}</h4>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '16px' }}>
              {day.concepts.map((c, i) => (
                <span key={i} style={{ fontSize: '11px', background: 'rgba(255, 255, 255, 0.05)', padding: '3px 8px', borderRadius: '4px', color: '#9CA3AF' }}>
                  {c}
                </span>
              ))}
            </div>

            <ul style={{ listStyle: 'none' }}>
              {day.practice_questions.map((q, idx) => (
                <li key={idx} style={{ fontSize: '13px', color: '#9CA3AF', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <input type="checkbox" id={`chk_${day.day}_${idx}`} />
                  <label htmlFor={`chk_${day.day}_${idx}`}>{q}</label>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
};
