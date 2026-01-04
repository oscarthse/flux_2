'use client';

import { useState, useEffect } from 'react';
import { api, ProfitabilityItemResponse } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  TrendingUp,
  TrendingDown,
  Star,
  HelpCircle,
  RefreshCcw,
  DollarSign,
  AlertTriangle
} from 'lucide-react';

export function ProfitabilityDashboard() {
  const [items, setItems] = useState<ProfitabilityItemResponse[]>([]);
  const [avgMargin, setAvgMargin] = useState(0);
  const [lowMarginCount, setLowMarginCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'margin' | 'price' | 'cogs' | 'waste'>('margin');
  const [wasteFactorsEnabled, setWasteFactorsEnabled] = useState(true);

  useEffect(() => {
    loadData();
    loadFeatureSettings();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    const result = await api.recipes.getProfitability();
    if (result.data) {
      setItems(result.data.items);
      setAvgMargin(result.data.average_margin);
      setLowMarginCount(result.data.low_margin_count);
    } else {
      setError(result.error || 'Failed to load profitability data');
    }
    setIsLoading(false);
  };

  const loadFeatureSettings = async () => {
    const result = await api.settings.getFeatures();
    if (result.data) {
      setWasteFactorsEnabled(result.data.waste_factors_enabled);
    }
  };

  const calculateWasteCost = (item: ProfitabilityItemResponse) => {
    if (!wasteFactorsEnabled) return 0;
    return item.ingredient_breakdown.reduce((sum, ing) => {
      const baseCost = Number(ing.base_cost);
      const wasteFactor = Number(ing.waste_factor || 0);
      return sum + (baseCost * wasteFactor);
    }, 0);
  };

  const sortedItems = [...items].sort((a, b) => {
    switch (sortBy) {
      case 'margin': return a.margin_percentage - b.margin_percentage;
      case 'price': return b.menu_item_price - a.menu_item_price;
      case 'cogs': return b.total_cogs - a.total_cogs;
      case 'waste': return calculateWasteCost(b) - calculateWasteCost(a);
      default: return 0;
    }
  });

  const bcgConfig: Record<string, { icon: typeof Star; label: string; color: string; action: string }> = {
    star: { icon: Star, label: 'Star', color: 'bg-yellow-100 text-yellow-700', action: 'Promote heavily' },
    puzzle: { icon: HelpCircle, label: 'Puzzle', color: 'bg-purple-100 text-purple-700', action: 'Market more' },
    plow_horse: { icon: TrendingDown, label: 'Plow Horse', color: 'bg-blue-100 text-blue-700', action: 'Re-engineer recipe' },
    dog: { icon: AlertTriangle, label: 'Dog', color: 'bg-red-100 text-red-700', action: 'Consider removing' },
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-muted border-t-foreground" />
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <TrendingUp className="w-5 h-5 text-foreground" />
            </div>
            <div>
              <div className="text-2xl font-bold text-foreground">{Number(avgMargin).toFixed(1)}%</div>
              <div className="text-sm text-muted-foreground">Avg Margin</div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <DollarSign className="w-5 h-5 text-foreground" />
            </div>
            <div>
              <div className="text-2xl font-bold text-foreground">{items.length}</div>
              <div className="text-sm text-muted-foreground">Menu Items</div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className={`p-2 bg-muted rounded-lg`}>
              <AlertTriangle className={`w-5 h-5 ${lowMarginCount > 0 ? 'text-destructive' : 'text-foreground'}`} />
            </div>
            <div>
              <div className="text-2xl font-bold text-foreground">{lowMarginCount}</div>
              <div className="text-sm text-muted-foreground">Low Margin (&lt;20%)</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Error */}
      {error && (
        <Card className="p-4 bg-destructive/10 border-destructive/20 text-destructive">
          {error}
        </Card>
      )}

      {/* Items Table */}
      <Card className="overflow-hidden">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <DollarSign className="w-5 h-5 text-foreground" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">Menu Profitability</h2>
              <p className="text-sm text-muted-foreground">COGS and margin analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as 'margin' | 'price' | 'cogs' | 'waste')}
              className="text-sm border border-input rounded-lg px-3 py-1.5 bg-background text-foreground"
            >
              <option value="margin">Sort by Margin</option>
              <option value="price">Sort by Price</option>
              <option value="cogs">Sort by COGS</option>
              {wasteFactorsEnabled && <option value="waste">Sort by Waste Cost</option>}
            </select>
            <Button variant="outline" size="sm" onClick={loadData}>
              <RefreshCcw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        <div className="p-6">
          {items.length === 0 ? (
            <div className="text-center py-12">
              <DollarSign className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground font-medium">No profitability data yet</p>
              <p className="text-sm text-muted-foreground/80 mt-1">
                Confirm recipes to see COGS calculations
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {sortedItems.map(item => (
                <ProfitabilityRow
                  key={item.menu_item_id}
                  item={item}
                  bcgConfig={bcgConfig}
                  wasteCost={calculateWasteCost(item)}
                  wasteFactorsEnabled={wasteFactorsEnabled}
                />
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

interface ProfitabilityRowProps {
  item: ProfitabilityItemResponse;
  bcgConfig: Record<string, { icon: typeof Star; label: string; color: string; action: string }>;
  wasteCost: number;
  wasteFactorsEnabled: boolean;
}

function ProfitabilityRow({ item, bcgConfig, wasteCost, wasteFactorsEnabled }: ProfitabilityRowProps) {
  const marginColor =
    item.margin_percentage >= 35 ? 'text-green-600 dark:text-green-400' :
      item.margin_percentage >= 20 ? 'text-yellow-600 dark:text-yellow-400' :
        'text-destructive';

  const bcg = item.bcg_quadrant ? bcgConfig[item.bcg_quadrant] : null;

  // Calculate waste percentage of total COGS
  const wastePercentage = (wasteCost / Number(item.total_cogs)) * 100;
  const hasSignificantWaste = wasteFactorsEnabled && wasteCost > 0.5; // More than $0.50 waste

  return (
    <div className="flex items-center justify-between p-4 rounded-xl bg-card hover:bg-muted/50 transition-colors border border-transparent hover:border-border">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-foreground truncate">{item.menu_item_name}</span>
          {bcg && (
            <Badge variant="secondary">
              {bcg.label}
            </Badge>
          )}
          {hasSignificantWaste && (
            <Badge variant="outline" className="bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-800">
              ${wasteCost.toFixed(2)} waste
            </Badge>
          )}
        </div>
        <div className="text-sm text-muted-foreground">
          {item.recipe_source === 'none' ? (
            <span className="text-amber-600 dark:text-amber-400">No recipe linked</span>
          ) : (
            <span>Source: {item.recipe_source}</span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-6 text-sm">
        <div className="text-right">
          <div className="text-muted-foreground">Price</div>
          <div className="font-medium text-foreground">${Number(item.menu_item_price).toFixed(2)}</div>
        </div>
        <div className="text-right">
          <div className="text-muted-foreground">COGS</div>
          <div className="font-medium text-foreground">${Number(item.total_cogs).toFixed(2)}</div>
          {wasteFactorsEnabled && wasteCost > 0 && (
            <div className="text-xs text-amber-600 dark:text-amber-400">
              {wastePercentage.toFixed(0)}% waste
            </div>
          )}
        </div>
        <div className="text-right min-w-[60px]">
          <div className="text-muted-foreground">Margin</div>
          <div className={`font-bold ${marginColor}`}>
            {Number(item.margin_percentage).toFixed(1)}%
          </div>
        </div>
      </div>
    </div>
  );
}
