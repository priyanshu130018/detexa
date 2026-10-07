import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { DecisionBadge } from '../../src/components/common/DecisionBadge';

describe('DecisionBadge Component', () => {
  it('renders ALLOW decision with green styling', () => {
    render(<DecisionBadge decision="ALLOW" />);
    const badge = screen.getByText('ALLOW');
    expect(badge).toBeInTheDocument();
  });

  it('renders BLOCK decision correctly', () => {
    render(<DecisionBadge decision="BLOCK" />);
    const badge = screen.getByText('BLOCK');
    expect(badge).toBeInTheDocument();
  });

  it('renders CHALLENGE decision correctly', () => {
    render(<DecisionBadge decision="CHALLENGE" />);
    const badge = screen.getByText('CHALLENGE');
    expect(badge).toBeInTheDocument();
  });

  it('renders REVIEW decision correctly', () => {
    render(<DecisionBadge decision="REVIEW" />);
    const badge = screen.getByText('REVIEW');
    expect(badge).toBeInTheDocument();
  });
});
