'use client';

import { StockoutDashboard } from '@/features/inventory';
import { Package } from 'lucide-react';

export default function InventoryPage() {
  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-muted rounded-lg">
          <Package className="w-6 h-6 text-foreground" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Inventory</h1>
          <p className="text-muted-foreground">Track stockouts and availability</p>
        </div>
      </div>

      {/* Why This Matters */}
      <div className="bg-muted/50 border border-border rounded-xl p-6">
        <h3 className="font-semibold text-foreground mb-2">Why stockouts matter for forecasting</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          When an item sells out, sales drop to zero—but that doesn't mean demand disappeared.
          Flux uses stockout data to "unconstrain" demand, estimating what sales would have been
          if you had enough inventory. This prevents systematic underforecasting.
        </p>
      </div>

      {/* Stockout Dashboard */}
      <StockoutDashboard />
    </div>
  );
}
