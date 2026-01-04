'use client';

import { useState, useEffect } from 'react';
import { api, InventorySnapshot, DetectedStockout } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  RefreshCcw,
  Search,
  Calendar,
  TrendingDown,
  Package
} from 'lucide-react';
import { format, parseISO, subDays, isToday, isYesterday } from 'date-fns';

export function StockoutDashboard() {
  const [stockouts, setStockouts] = useState<InventorySnapshot[]>([]);
  const [detectedStockouts, setDetectedStockouts] = useState<DetectedStockout[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDetecting, setIsDetecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);

    const today = new Date();
    const thirtyDaysAgo = subDays(today, 30);

    const result = await api.inventory.listStockouts({
      start_date: format(thirtyDaysAgo, 'yyyy-MM-dd'),
      end_date: format(today, 'yyyy-MM-dd'),
    });

    if (result.data) {
      setStockouts(result.data.stockouts);
    } else {
      setError(result.error || 'Failed to load stockouts');
    }

    setIsLoading(false);
  };

  const handleDetect = async () => {
    setIsDetecting(true);
    setError(null);

    const result = await api.inventory.detectStockouts(30, false);

    if (result.data) {
      setDetectedStockouts(result.data.detected_stockouts);
    } else {
      setError(result.error || 'Detection failed');
    }

    setIsDetecting(false);
  };

  const handleSaveDetected = async () => {
    setIsDetecting(true);

    const result = await api.inventory.detectStockouts(30, true);

    if (result.data) {
      setDetectedStockouts([]);
      await loadData();
    } else {
      setError(result.error || 'Failed to save');
    }

    setIsDetecting(false);
  };

  const formatDate = (dateStr: string) => {
    const date = parseISO(dateStr);
    if (isToday(date)) return 'Today';
    if (isYesterday(date)) return 'Yesterday';
    return format(date, 'MMM d');
  };

  // Group stockouts by week
  const thisWeekStockouts = stockouts.filter(s => {
    const date = parseISO(s.date);
    return date >= subDays(new Date(), 7);
  });

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
      {/* Detected Stockouts Alert */}
      {detectedStockouts.length > 0 && (
        <Card className="bg-muted/50 border-border">
          <div className="p-5">
            <div className="flex items-start gap-4">
              <div className="p-2 bg-muted rounded-lg shrink-0">
                <Search className="w-5 h-5 text-foreground" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-foreground">
                  {detectedStockouts.length} potential stockouts detected
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Based on sales velocity analysis, these items may have sold out.
                </p>

                <div className="mt-4 space-y-2">
                  {detectedStockouts.slice(0, 5).map((d, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-card rounded-lg border border-border">
                      <div>
                        <span className="font-medium text-foreground">{d.item_name}</span>
                        <span className="text-sm text-muted-foreground ml-2">{formatDate(d.detected_date)}</span>
                      </div>
                      <Badge variant="secondary">
                        {Math.round(d.confidence * 100)}% confident
                      </Badge>
                    </div>
                  ))}
                </div>

                <div className="flex gap-2 mt-4">
                  <Button
                    size="sm"
                    onClick={handleSaveDetected}
                    disabled={isDetecting}
                    variant="default"
                  >
                    Confirm & Save All
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDetectedStockouts([])}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Summary Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <AlertTriangle className="w-5 h-5 text-destructive" />
            </div>
            <div>
              <div className="text-2xl font-bold text-foreground">{thisWeekStockouts.length}</div>
              <div className="text-sm text-muted-foreground">This week</div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <TrendingDown className="w-5 h-5 text-foreground" />
            </div>
            <div>
              <div className="text-2xl font-bold text-foreground">{stockouts.length}</div>
              <div className="text-sm text-muted-foreground">Last 30 days</div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <Package className="w-5 h-5 text-foreground" />
            </div>
            <div>
              <div className="text-2xl font-bold text-foreground">
                {new Set(stockouts.map(s => s.menu_item_id)).size}
              </div>
              <div className="text-sm text-muted-foreground">Items affected</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Stockouts List */}
      <Card className="overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <AlertTriangle className="w-5 h-5 text-destructive" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">Stockout History</h2>
              <p className="text-sm text-muted-foreground">Items that sold out recently</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDetect}
              disabled={isDetecting}
            >
              {isDetecting ? (
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-muted border-t-foreground" />
              ) : (
                <>
                  <Search className="w-4 h-4 mr-1" />
                  Detect
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              disabled={isLoading}
            >
              <RefreshCcw className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="px-6 py-3 bg-destructive/10 border-b border-destructive/20 text-destructive text-sm">
            {error}
          </div>
        )}

        {/* List */}
        <div className="p-6">
          {stockouts.length === 0 ? (
            <div className="text-center py-12">
              <Package className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground font-medium">No stockouts recorded</p>
              <p className="text-sm text-muted-foreground/80 mt-1">
                Click "Detect" to analyze recent sales for potential stockouts.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {stockouts.map(stockout => (
                <div
                  key={stockout.id}
                  className="flex items-center justify-between p-4 rounded-xl bg-card hover:bg-muted/50 transition-colors border border-border"
                >
                  <div className="flex items-center gap-4">
                    <div className="text-center min-w-[50px]">
                      <div className="text-xs font-medium text-muted-foreground uppercase">
                        {format(parseISO(stockout.date), 'MMM')}
                      </div>
                      <div className="text-xl font-bold text-foreground">
                        {format(parseISO(stockout.date), 'd')}
                      </div>
                    </div>
                    <div>
                      <div className="font-medium text-foreground">
                        Item #{stockout.menu_item_id.slice(0, 8)}...
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Source: {stockout.source}
                      </div>
                    </div>
                  </div>
                  <Badge variant="destructive">
                    Sold Out
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}
