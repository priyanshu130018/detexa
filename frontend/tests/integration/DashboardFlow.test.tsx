import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { DecisionBadge } from '../../src/components/common/DecisionBadge';
import { RiskBadge } from '../../src/components/common/RiskBadge';
import { StatCard } from '../../src/components/common/StatCard';
import { Activity } from 'lucide-react';

describe('Dashboard Integration Flow Components', () => {
  it('renders composite dashboard telemetry tiles cohesively', () => {
    render(
      <BrowserRouter>
        <div data-testid="dashboard-summary">
          <StatCard title="Fraud Rate" value="0.14%" subtitle="Target < 0.20%" icon={Activity} />
          <RiskBadge level="High" />
          <DecisionBadge decision="BLOCK" />
        </div>
      </BrowserRouter>
    );

    expect(screen.getByText('Fraud Rate')).toBeInTheDocument();
    expect(screen.getByText('0.14%')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('BLOCK')).toBeInTheDocument();
  });
});
