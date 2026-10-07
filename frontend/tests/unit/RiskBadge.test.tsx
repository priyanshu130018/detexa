import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { RiskBadge } from '../../src/components/common/RiskBadge';

describe('RiskBadge Component', () => {
  it('renders Low risk badge correctly', () => {
    render(<RiskBadge level="Low" />);
    expect(screen.getByText('Low')).toBeInTheDocument();
  });

  it('renders Medium risk badge correctly', () => {
    render(<RiskBadge level="Medium" />);
    expect(screen.getByText('Medium')).toBeInTheDocument();
  });

  it('renders High risk badge correctly', () => {
    render(<RiskBadge level="High" />);
    expect(screen.getByText('High')).toBeInTheDocument();
  });
});
