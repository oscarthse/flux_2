'use client';

import { useState, useEffect } from 'react';
import { api, Promotion, ExploreCandidate } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Tag,
  RefreshCcw,
  TrendingUp,
  Beaker,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle
} from 'lucide-react';
import { format, parseISO, isFuture, isPast } from 'date-fns';

interface PromotionsListProps {
  onSelectPromotion?: (promotion: Promotion) => void;
}

type StatusFilter = 'all' | 'active' | 'draft' | 'completed' | 'cancelled';

export function PromotionsList({ onSelectPromotion }: PromotionsListProps) {
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [exploreCandidates, setExploreCandidates] = useState<ExploreCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);

    const [promoResult, candidatesResult] = await Promise.all([
      api.promotions.list(),
      api.promotions.exploreCandidates(),
    ]);

    if (promoResult.data) {
      setPromotions(promoResult.data.promotions);
    } else {
      setError(promoResult.error || 'Failed to load promotions');
    }

    if (candidatesResult.data) {
      setExploreCandidates(candidatesResult.data.candidates);
    }

    setIsLoading(false);
  };

  const filteredPromotions = statusFilter === 'all'
    ? promotions
    : promotions.filter(p => p.status === statusFilter);

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
      {/* Explore Candidates Alert */}
      {exploreCandidates.length > 0 && (
        <Card className="bg-muted/50 border-border">
          <div className="p-5 flex items-start gap-4">
            <div className="p-2 bg-muted rounded-lg shrink-0">
              <Beaker className="w-5 h-5 text-foreground" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-foreground">
                {exploreCandidates.length} items need price testing
              </h3>
              <p className="text-sm text-muted-foreground mt-1">
                These menu items don't have enough discount data to calculate accurate price elasticity.
                Running small test promotions helps Flux learn how price changes affect demand.
              </p>
              <div className="flex flex-wrap gap-2 mt-3">
                {exploreCandidates.slice(0, 5).map(c => (
                  <Badge key={c.menu_item_id} variant="secondary">
                    {c.name}
                  </Badge>
                ))}
                {exploreCandidates.length > 5 && (
                  <Badge variant="outline">
                    +{exploreCandidates.length - 5} more
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Promotions List */}
      <Card className="overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <Tag className="w-5 h-5 text-foreground" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">Promotions</h2>
              <p className="text-sm text-muted-foreground">Manage discounts and track performance</p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={isLoading}
          >
            <RefreshCcw className="w-4 h-4" />
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="px-6 py-3 bg-destructive/10 border-b border-destructive/20 text-destructive text-sm">
            {error}
          </div>
        )}

        {/* Filter Tabs */}
        <div className="px-6 py-3 border-b border-border flex gap-2 overflow-x-auto">
          {(['all', 'active', 'draft', 'completed', 'cancelled'] as StatusFilter[]).map(status => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-3 py-1.5 text-sm rounded-full transition-colors whitespace-nowrap ${statusFilter === status
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>

        {/* Promotions Grid */}
        <div className="p-6">
          {filteredPromotions.length === 0 ? (
            <div className="text-center py-12">
              <Tag className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground font-medium">No promotions yet</p>
              <p className="text-sm text-muted-foreground/80 mt-1">
                Create promotions from the inventory page or let Flux suggest them.
              </p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {filteredPromotions.map(promo => (
                <PromotionCard
                  key={promo.id}
                  promotion={promo}
                  onClick={() => onSelectPromotion?.(promo)}
                />
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

interface PromotionCardProps {
  promotion: Promotion;
  onClick?: () => void;
}

function PromotionCard({ promotion, onClick }: PromotionCardProps) {
  // Map status to semantic Badge variants
  // Active = default (primary), Completed = secondary, Cancelled = destructive, Draft = outline
  const statusVariant = {
    draft: 'outline',
    active: 'default',
    completed: 'secondary',
    cancelled: 'destructive'
  } as const;

  const StatusIcon = {
    draft: Clock,
    active: TrendingUp,
    completed: CheckCircle,
    cancelled: XCircle
  }[promotion.status];


  const isActive = isFuture(parseISO(promotion.end_date)) && isPast(parseISO(promotion.start_date));

  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-xl border transition-all cursor-pointer bg-card hover:bg-muted/50 ${isActive
        ? 'border-primary/50 ring-1 ring-primary/20'
        : 'border-border hover:border-foreground/20'
        }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-medium text-foreground truncate">
              {promotion.name || 'Unnamed Promotion'}
            </h3>
            {promotion.is_exploration && (
              <Badge variant="secondary" className="text-xs shrink-0">
                <Beaker className="w-3 h-3 mr-1" />
                Test
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {promotion.discount_type === 'percentage'
              ? `${promotion.discount_value}% off`
              : `$${promotion.discount_value} off`
            }
          </p>
        </div>
        <Badge variant={statusVariant[promotion.status] as any} className="flex items-center gap-1">
          <StatusIcon className="w-3 h-3" />
          {promotion.status.charAt(0).toUpperCase() + promotion.status.slice(1)}
        </Badge>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {format(parseISO(promotion.start_date), 'MMM d')} — {format(parseISO(promotion.end_date), 'MMM d, yyyy')}
        </span>
        {promotion.actual_lift !== null && (
          <span className={promotion.actual_lift > 0 ? 'text-green-600 dark:text-green-400 font-medium' : ''}>
            {promotion.actual_lift > 0 ? '+' : ''}{promotion.actual_lift}% lift
          </span>
        )}
      </div>
    </div>
  );
}
