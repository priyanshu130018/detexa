import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ReferenceLine } from 'recharts';
import { SHAPFeature } from '../../types';
import { useTheme } from '../../context/ThemeContext';

interface SHAPChartProps {
  features?: SHAPFeature[];
}

export const SHAPChart: React.FC<SHAPChartProps> = ({ features = [] }) => {
  const { isDark } = useTheme();

  if (!features || features.length === 0) {
    return (
      <div className="text-center py-6 text-black/60 dark:text-white/60 text-sm">
        No feature explanations available for this prediction.
      </div>
    );
  }

  const data = features.slice(0, 8).map((f) => ({
    name: f.feature,
    value: Number(f.shap_value.toFixed(4)),
  }));

  return (
    <div className="w-full h-64 mt-2">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 60, bottom: 5 }}
        >
          <XAxis
            type="number"
            stroke={isDark ? "rgba(255, 255, 255, 0.4)" : "rgba(0, 0, 0, 0.4)"}
            tick={{ fill: isDark ? '#ffffff' : '#000000', fontSize: 11 }}
            domain={['auto', 'auto']}
          />
          <YAxis
            type="category"
            dataKey="name"
            stroke={isDark ? "rgba(255, 255, 255, 0.4)" : "rgba(0, 0, 0, 0.4)"}
            tick={{ fill: isDark ? '#ffffff' : '#000000', fontSize: 12, fontWeight: 500 }}
            width={70}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: isDark ? '#000000' : '#ffffff',
              borderColor: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)',
              borderRadius: '8px',
              color: isDark ? '#ffffff' : '#000000',
              boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
            }}
            itemStyle={{ color: isDark ? '#ffffff' : '#000000' }}
            labelStyle={{ color: isDark ? '#ffffff' : '#000000' }}
            formatter={(value: any) => [
              `${value > 0 ? '+' : ''}${value} impact`,
              'SHAP Contribution',
            ]}
          />
          <ReferenceLine x={0} stroke={isDark ? "rgba(255, 255, 255, 0.2)" : "rgba(0, 0, 0, 0.2)"} strokeDasharray="3 3" />
          <Bar dataKey="value" radius={[4, 4, 4, 4]}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.value > 0 ? '#dc2626' : '#2563eb'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};
