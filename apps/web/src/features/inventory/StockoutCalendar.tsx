'use client';

import { useState, useEffect } from 'react';
import { api, InventorySnapshot } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Calendar as CalendarIcon,
} from 'lucide-react';
import {
  format,
  parseISO,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  isToday,
  addMonths,
  subMonths,
  startOfWeek,
  endOfWeek,
} from 'date-fns';

export function StockoutCalendar() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [stockouts, setStockouts] = useState<InventorySnapshot[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStockoutsForMonth();
  }, [currentMonth]);

  const loadStockoutsForMonth = async () => {
    setIsLoading(true);
    setError(null);

    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);

    // Expand range to include partial weeks at start/end of month
    const calendarStart = startOfWeek(monthStart);
    const calendarEnd = endOfWeek(monthEnd);

    const result = await api.inventory.listStockouts({
      start_date: format(calendarStart, 'yyyy-MM-dd'),
      end_date: format(calendarEnd, 'yyyy-MM-dd'),
    });

    if (result.data) {
      setStockouts(result.data.stockouts);
    } else {
      setError(result.error || 'Failed to load stockouts');
    }

    setIsLoading(false);
  };

  const handlePreviousMonth = () => {
    setCurrentMonth(prev => subMonths(prev, 1));
  };

  const handleNextMonth = () => {
    setCurrentMonth(prev => addMonths(prev, 1));
  };

  const handleToday = () => {
    setCurrentMonth(new Date());
  };

  // Generate calendar grid
  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(currentMonth);
  const calendarStart = startOfWeek(monthStart);
  const calendarEnd = endOfWeek(monthEnd);

  const calendarDays = eachDayOfInterval({
    start: calendarStart,
    end: calendarEnd,
  });

  // Group stockouts by date
  const stockoutsByDate = stockouts.reduce((acc, stockout) => {
    const dateKey = stockout.date;
    if (!acc[dateKey]) {
      acc[dateKey] = [];
    }
    acc[dateKey].push(stockout);
    return acc;
  }, {} as Record<string, InventorySnapshot[]>);

  const getDayStockouts = (day: Date) => {
    const dateKey = format(day, 'yyyy-MM-dd');
    return stockoutsByDate[dateKey] || [];
  };

  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center h-96">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-muted border-t-foreground" />
        </div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-muted rounded-lg">
            <CalendarIcon className="w-5 h-5 text-foreground" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Stockout Calendar</h2>
            <p className="text-sm text-muted-foreground">
              {format(currentMonth, 'MMMM yyyy')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePreviousMonth}
            className="p-2 hover:bg-muted rounded-lg transition-colors"
            aria-label="Previous month"
          >
            <ChevronLeft className="w-5 h-5 text-foreground" />
          </button>
          <button
            onClick={handleToday}
            className="px-3 py-1.5 text-sm font-medium hover:bg-muted rounded-lg transition-colors text-foreground"
          >
            Today
          </button>
          <button
            onClick={handleNextMonth}
            className="p-2 hover:bg-muted rounded-lg transition-colors"
            aria-label="Next month"
          >
            <ChevronRight className="w-5 h-5 text-foreground" />
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-6 py-3 bg-destructive/10 border-b border-destructive/20 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* Calendar Grid */}
      <div className="p-6">
        {/* Weekday headers */}
        <div className="grid grid-cols-7 gap-2 mb-2">
          {weekDays.map(day => (
            <div
              key={day}
              className="text-center text-sm font-semibold text-muted-foreground py-2"
            >
              {day}
            </div>
          ))}
        </div>

        {/* Calendar days */}
        <div className="grid grid-cols-7 gap-2">
          {calendarDays.map(day => {
            const dayStockouts = getDayStockouts(day);
            const hasStockouts = dayStockouts.length > 0;
            const isCurrentMonth = isSameMonth(day, currentMonth);
            const isDayToday = isToday(day);

            return (
              <div
                key={day.toISOString()}
                className={`
                  min-h-[100px] p-2 rounded-lg border transition-all
                  ${isCurrentMonth ? 'bg-card border-border' : 'bg-muted/30 border-transparent'}
                  ${isDayToday ? 'ring-2 ring-primary' : ''}
                  ${hasStockouts ? 'border-destructive/50 bg-destructive/5' : ''}
                `}
              >
                <div className="flex items-center justify-between mb-1">
                  <span
                    className={`
                      text-sm font-medium
                      ${isCurrentMonth ? 'text-foreground' : 'text-muted-foreground/50'}
                      ${isDayToday ? 'bg-primary text-primary-foreground px-2 py-0.5 rounded-full' : ''}
                    `}
                  >
                    {format(day, 'd')}
                  </span>
                  {hasStockouts && (
                    <Badge
                      variant="destructive"
                      className="h-5 px-1.5 text-xs"
                    >
                      {dayStockouts.length}
                    </Badge>
                  )}
                </div>

                {/* Stockout indicators */}
                {hasStockouts && (
                  <div className="space-y-1">
                    {dayStockouts.slice(0, 2).map((stockout, idx) => (
                      <div
                        key={stockout.id}
                        className="flex items-center gap-1 text-xs"
                      >
                        <AlertTriangle className="w-3 h-3 text-destructive shrink-0" />
                        <span className="text-muted-foreground truncate">
                          {stockout.source === 'auto_detected' ? 'Auto' :
                           stockout.source === 'manual' ? 'Manual' :
                           stockout.source === 'inferred' ? 'Inferred' :
                           stockout.source}
                        </span>
                      </div>
                    ))}
                    {dayStockouts.length > 2 && (
                      <div className="text-xs text-muted-foreground">
                        +{dayStockouts.length - 2} more
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="px-6 py-4 border-t border-border bg-muted/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded border-2 ring-2 ring-primary bg-card" />
              <span className="text-muted-foreground">Today</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded border border-destructive/50 bg-destructive/5" />
              <span className="text-muted-foreground">Has stockouts</span>
            </div>
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-destructive" />
              <span className="text-muted-foreground">Stockout indicator</span>
            </div>
          </div>
          <div className="text-sm text-muted-foreground">
            {stockouts.length} stockout{stockouts.length !== 1 ? 's' : ''} this month
          </div>
        </div>
      </div>
    </Card>
  );
}
