import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { StatCard } from '../../src/components/common/StatCard';
import { Shield } from 'lucide-react';

describe('StatCard Component', () => {
  it('renders title and value properly', () => {
    render(
      <StatCard
        title="Total Processed"
        value="₹12,48,500.00"
        subtitle="+12% from yesterday"
        icon={Shield}
      />
    );
    expect(screen.getByText('Total Processed')).toBeInTheDocument();
    expect(screen.getByText('₹12,48,500.00')).toBeInTheDocument();
    expect(screen.getByText('+12% from yesterday')).toBeInTheDocument();
  });
});
