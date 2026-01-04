'use client';

import { useState } from 'react';
import { PromotionsList, PromotionCalendar, ElasticityCard } from '@/features/promotions';
import { Tag, Calendar, TrendingDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

type ViewMode = 'list' | 'calendar' | 'elasticity';

export default function PromotionsPage() {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [menuItems, setMenuItems] = useState<{ id: string; name: string }[]>([]);
  const [isLoadingItems, setIsLoadingItems] = useState(false);

  const loadMenuItems = async () => {
    setIsLoadingItems(true);
    const result = await api.menu.list();
    if (result.data) {
      setMenuItems(result.data.items);
    }
    setIsLoadingItems(false);
  };

  // Load menu items when switching to elasticity view
  const handleViewChange = (mode: ViewMode) => {
    setViewMode(mode);
    if (mode === 'elasticity' && menuItems.length === 0) {
      loadMenuItems();
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-muted rounded-lg">
            <Tag className="w-6 h-6 text-foreground" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-foreground">Promotions & Pricing</h1>
            <p className="text-muted-foreground">Track discounts and analyze price elasticity</p>
          </div>
        </div>

        {/* View Toggle */}
        <div className="flex gap-2">
          <Button
            variant={viewMode === 'list' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleViewChange('list')}
          >
            <Tag className="w-4 h-4 mr-2" />
            List
          </Button>
          <Button
            variant={viewMode === 'calendar' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleViewChange('calendar')}
          >
            <Calendar className="w-4 h-4 mr-2" />
            Calendar
          </Button>
          <Button
            variant={viewMode === 'elasticity' ? 'default' : 'outline'}
            size="sm"
            onClick={() => handleViewChange('elasticity')}
          >
            <TrendingDown className="w-4 h-4 mr-2" />
            Elasticity
          </Button>
        </div>
      </div>

      {/* Info Box */}
      {viewMode === 'elasticity' ? (
        <div className="bg-muted/50 border border-border rounded-xl p-6">
          <h3 className="font-semibold text-foreground mb-2">Price Elasticity of Demand</h3>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Price elasticity measures how sensitive customer demand is to price changes.
            A value of -1.2 means that a 1% price increase leads to a 1.2% decrease in demand.
            Higher confidence scores indicate more reliable estimates based on your historical data.
          </p>
        </div>
      ) : (
        <div className="bg-muted/50 border border-border rounded-xl p-6">
          <h3 className="font-semibold text-foreground mb-2">Understanding promotions</h3>
          <p className="text-sm text-muted-foreground leading-relaxed">
            Flux automatically detects promotions from your POS data using multiple methods:
            explicit discount columns, keywords in item names, and statistical price pattern analysis.
            This data helps build accurate demand forecasts and optimize future pricing strategies.
          </p>
        </div>
      )}

      {/* Content */}
      {viewMode === 'list' && <PromotionsList />}

      {viewMode === 'calendar' && <PromotionCalendar />}

      {viewMode === 'elasticity' && (
        <div>
          {isLoadingItems ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-muted border-t-foreground" />
            </div>
          ) : menuItems.length === 0 ? (
            <div className="text-center py-12 bg-muted/30 rounded-xl border border-border">
              <Tag className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground font-medium">No menu items found</p>
              <p className="text-sm text-muted-foreground/80 mt-1">
                Upload transaction data to see price elasticity estimates.
              </p>
            </div>
          ) : (
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {menuItems.map(item => (
                <ElasticityCard
                  key={item.id}
                  menuItemId={item.id}
                  menuItemName={item.name}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
