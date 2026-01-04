'use client';

import { useState } from 'react';
import { api, ElasticityEstimate } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  TrendingDown,
  TrendingUp,
  Calculator,
  AlertTriangle,
  CheckCircle,
  Info,
  RefreshCcw
} from 'lucide-react';

interface ElasticityCardProps {
  menuItemId: string;
  menuItemName: string;
  initialEstimate?: ElasticityEstimate | null;
  onEstimateUpdate?: (estimate: ElasticityEstimate) => void;
}

export function ElasticityCard({
  menuItemId,
  menuItemName,
  initialEstimate = null,
  onEstimateUpdate
}: ElasticityCardProps) {
  const [estimate, setEstimate] = useState<ElasticityEstimate | null>(initialEstimate);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadEstimate = async (recalculate: boolean = false) => {
    setIsLoading(true);
    setError(null);

    const result = recalculate
      ? await api.promotions.estimateElasticity(menuItemId)
      : await api.promotions.getElasticity(menuItemId);

    if (result.data) {
      setEstimate(result.data);
      onEstimateUpdate?.(result.data);
    } else {
      // If no saved estimate, try to calculate one
      if (!recalculate && result.error?.includes('not found')) {
        const calcResult = await api.promotions.estimateElasticity(menuItemId);
        if (calcResult.data) {
          setEstimate(calcResult.data);
          onEstimateUpdate?.(calcResult.data);
        } else {
          setError(calcResult.error || 'Failed to estimate elasticity');
        }
      } else {
        setError(result.error || 'Failed to load elasticity estimate');
      }
    }

    setIsLoading(false);
  };

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 0.7) {
      return { variant: 'default' as const, label: 'High Confidence', icon: CheckCircle, color: 'text-green-600 dark:text-green-400' };
    } else if (confidence >= 0.4) {
      return { variant: 'secondary' as const, label: 'Medium Confidence', icon: Info, color: 'text-yellow-600 dark:text-yellow-400' };
    } else {
      return { variant: 'outline' as const, label: 'Low Confidence', icon: AlertTriangle, color: 'text-orange-600 dark:text-orange-400' };
    }
  };

  const getMethodLabel = (method: string) => {
    const labels: Record<string, string> = {
      '2SLS': 'Econometric (2SLS)',
      'bayesian_with_prior': 'Bayesian + Prior',
      'category_pooled': 'Category Pooled',
      'price_tier': 'Price Tier Average',
      'restaurant_avg': 'Restaurant Average',
      'industry_default_category': 'Industry Default (Category)',
      'industry_default_price_tier': 'Industry Default (Price Tier)',
      'saved': 'Saved Estimate'
    };
    return labels[method] || method;
  };

  const formatElasticity = (elasticity: number) => {
    const absElasticity = Math.abs(elasticity);
    return {
      value: elasticity.toFixed(2),
      interpretation: `${absElasticity.toFixed(1)}% demand ${elasticity < 0 ? 'decrease' : 'increase'} per 1% price increase`
    };
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-muted border-t-foreground" />
        </div>
      </Card>
    );
  }

  if (!estimate && !error) {
    return (
      <Card className="p-6">
        <div className="text-center">
          <Calculator className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
          <h3 className="font-semibold text-foreground mb-2">{menuItemName}</h3>
          <p className="text-sm text-muted-foreground mb-4">
            No price elasticity estimate yet
          </p>
          <Button onClick={() => loadEstimate(true)} disabled={isLoading}>
            <Calculator className="w-4 h-4 mr-2" />
            Calculate Elasticity
          </Button>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="p-6 border-destructive/50">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-3" />
          <h3 className="font-semibold text-foreground mb-2">{menuItemName}</h3>
          <p className="text-sm text-destructive mb-4">{error}</p>
          <Button variant="outline" onClick={() => loadEstimate(true)}>
            <RefreshCcw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  const { value, interpretation } = formatElasticity(estimate!.elasticity);
  const confidenceBadge = getConfidenceBadge(estimate!.confidence);
  const ConfidenceIcon = confidenceBadge.icon;

  return (
    <Card className="p-6 hover:shadow-lg transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="font-semibold text-foreground text-lg mb-1">
            {menuItemName}
          </h3>
          <p className="text-sm text-muted-foreground">
            {getMethodLabel(estimate!.method)}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => loadEstimate(true)}
          disabled={isLoading}
        >
          <RefreshCcw className="w-4 h-4" />
        </Button>
      </div>

      {/* Elasticity Value */}
      <div className="mb-4">
        <div className="flex items-baseline gap-2 mb-2">
          {estimate!.elasticity < 0 ? (
            <TrendingDown className="w-6 h-6 text-red-500" />
          ) : (
            <TrendingUp className="w-6 h-6 text-green-500" />
          )}
          <span className="text-3xl font-bold text-foreground">
            {value}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          {interpretation}
        </p>
      </div>

      {/* Confidence Badge */}
      <div className="mb-4">
        <Badge variant={confidenceBadge.variant} className="flex items-center gap-1 w-fit">
          <ConfidenceIcon className="w-3 h-3" />
          {confidenceBadge.label} ({(estimate!.confidence * 100).toFixed(0)}%)
        </Badge>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
        <div>
          <p className="text-xs text-muted-foreground mb-1">Sample Size</p>
          <p className="text-sm font-medium text-foreground">
            {estimate!.sample_size} days
          </p>
        </div>
        {estimate!.r_squared !== undefined && estimate!.r_squared > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">R²</p>
            <p className="text-sm font-medium text-foreground">
              {estimate!.r_squared.toFixed(2)}
            </p>
          </div>
        )}
        {estimate!.std_error > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">Std Error</p>
            <p className="text-sm font-medium text-foreground">
              ±{estimate!.std_error.toFixed(2)}
            </p>
          </div>
        )}
        {estimate!.f_stat !== undefined && estimate!.f_stat > 0 && (
          <div>
            <p className="text-xs text-muted-foreground mb-1">F-Statistic</p>
            <p className="text-sm font-medium text-foreground">
              {estimate!.f_stat.toFixed(1)}
            </p>
          </div>
        )}
      </div>

      {/* Confidence Interval */}
      {estimate!.ci_lower !== 0 && estimate!.ci_upper !== 0 && (
        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-xs text-muted-foreground mb-2">95% Confidence Interval</p>
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{estimate!.ci_lower.toFixed(2)}</span>
            <div className="flex-1 mx-3 h-2 bg-muted rounded-full relative">
              <div
                className="absolute h-full bg-primary rounded-full"
                style={{
                  left: '0%',
                  width: '100%'
                }}
              />
            </div>
            <span className="text-muted-foreground">{estimate!.ci_upper.toFixed(2)}</span>
          </div>
        </div>
      )}

      {/* Weak Instrument Warning */}
      {estimate!.is_weak_instrument && (
        <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-950/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-600 dark:text-yellow-400 shrink-0 mt-0.5" />
            <p className="text-xs text-yellow-800 dark:text-yellow-200">
              Weak instrument detected. Estimates may be less reliable. Consider collecting more price variation data.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
