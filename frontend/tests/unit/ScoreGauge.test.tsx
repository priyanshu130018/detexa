import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { ScoreGauge } from '../../src/components/common/ScoreGauge';

describe('ScoreGauge Component', () => {
  it('renders low risk score percentage correctly', () => {
    render(<ScoreGauge score={0.12} />);
    expect(screen.getByText('12.0%')).toBeInTheDocument();
  });

  it('renders high risk score percentage correctly', () => {
    render(<ScoreGauge score={0.88} />);
    expect(screen.getByText('88.0%')).toBeInTheDocument();
  });
});
