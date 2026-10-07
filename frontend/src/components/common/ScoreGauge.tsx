import React from 'react';
import { RiskLevel } from '../../types';
import { useTheme } from '../../context/ThemeContext';

interface ScoreGaugeProps {
  score: number;
  label?: string;
  riskLevel?: RiskLevel;
}

export const ScoreGauge: React.FC<ScoreGaugeProps> = ({
  score,
  label = 'Fraud Risk Score',
  riskLevel,
}) => {
  const { isDark } = useTheme();
  const normalizedScore = Math.max(0, Math.min(1, score));
  const percentage = Math.round(normalizedScore * 100);

  let color = '#2563eb'; // Blue
  let riskText = 'LOW RISK';
  let badgeBg = 'bg-blue-600/10 text-blue-600 dark:text-blue-400 border-blue-500/30';

  if (normalizedScore >= 0.75 || riskLevel === 'High') {
    color = '#dc2626'; // Red
    riskText = 'HIGH RISK';
    badgeBg = 'bg-red-600/15 text-red-600 dark:text-red-400 border-red-500/40';
  } else if (normalizedScore >= 0.50 || riskLevel === 'Medium') {
    color = '#3b82f6'; // Light Blue
    riskText = 'MEDIUM RISK';
    badgeBg = 'bg-blue-600/20 text-blue-700 dark:text-blue-300 border-blue-500/40';
  }

  // Svg semi-circle calculation (circumference = PI * radius = 3.14159 * 40 ≈ 125.66)
  const strokeDashoffset = 125.66 * (1 - normalizedScore);

  return (
    <div className="bg-white dark:bg-black border border-black/10 dark:border-white/10 rounded-xl p-6 flex flex-col items-center justify-center text-center shadow-sm transition-colors">
      <span className="text-xs font-semibold text-black/60 dark:text-white/60 uppercase tracking-wider mb-2">
        {label}
      </span>
      <div className="relative w-44 h-24 flex items-end justify-center">
        <svg viewBox="0 0 100 55" className="w-full h-full overflow-visible">
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke={isDark ? "rgba(255, 255, 255, 0.15)" : "rgba(0, 0, 0, 0.1)"}
            strokeWidth="8"
            strokeLinecap="round"
          />
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray="125.66"
            strokeDashoffset={strokeDashoffset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute bottom-0 text-center">
          <span className="text-3xl font-extrabold text-black dark:text-white tracking-tight">
            {normalizedScore.toFixed(3)}
          </span>
          <span className="text-xs text-black/60 dark:text-white/60 block -mt-1 font-mono">
            {percentage}%
          </span>
        </div>
      </div>
      <div className={`mt-4 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${badgeBg}`}>
        {riskText}
      </div>
    </div>
  );
};
