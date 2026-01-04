'use client';

import { useState, useEffect } from 'react';
import { api, Promotion } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Tag,
  ChevronLeft,
  ChevronRight,
  Calendar as CalendarIcon,
  Beaker,
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
  isWithinInterval,
} from 'date-fns';

export function PromotionCalendar() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [promotions, setPromotions] = useState<Promotion[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadPromotions();
  }, []);

  const loadPromotions = async () => {
    setIsLoading(true);
    setError(null);

    const result = await api.promotions.list();

    if (result.data) {
      setPromotions(result.data.promotions);
    } else {
      setError(result.error || 'Failed to load promotions');
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

  // Get promotions active on a specific day
  const getDayPromotions = (day: Date) => {
    return promotions.filter(promo => {
      const startDate = parseISO(promo.start_date);
      const endDate = parseISO(promo.end_date);
      return isWithinInterval(day, { start: startDate, end: endDate });
    });
  };

  const getConfidenceColor = (confidence: number | null | undefined) => {
    if (!confidence) return 'bg-gray-500';
    if (confidence >= 0.7) return 'bg-green-500';
    if (confidence >= 0.4) return 'bg-yellow-500';
    return 'bg-orange-500';
  };

  const weekDays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

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
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border bg-muted/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <CalendarIcon className="w-5 h-5 text-foreground" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-foreground">
                Promotion Calendar
              </h2>
              <p className="text-sm text-muted-foreground">
                {format(currentMonth, 'MMMM yyyy')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreviousMonth}
            >
              <ChevronLeft className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleToday}
            >
              Today
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNextMonth}
            >
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
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
        {/* Week day headers */}
        <div className="grid grid-cols-7 gap-2 mb-2">
          {weekDays.map(day => (
            <div
              key={day}
              className="text-center text-sm font-medium text-muted-foreground py-2"
            >
              {day}
            </div>
          ))}
        </div>

        {/* Calendar days */}
        <div className="grid grid-cols-7 gap-2">
          {calendarDays.map(day => {
            const dayPromotions = getDayPromotions(day);
            const isCurrentMonth = isSameMonth(day, currentMonth);
            const isCurrentDay = isToday(day);

            return (
              <div
                key={day.toISOString()}
                className={`min-h-24 p-2 rounded-lg border transition-colors ${isCurrentMonth
                  ? isCurrentDay
                    ? 'bg-primary/10 border-primary'
                    : 'bg-card border-border hover:bg-muted/50'
                  : 'bg-muted/30 border-border/50'
                  }`}
              >
                <div className="text-sm font-medium mb-1 text-foreground">
                  {format(day, 'd')}
                </div>

                <div className="space-y-1">
                  {dayPromotions.slice(0, 3).map(promo => {
                    // Determine color based on detection method/confidence
                    let dotColor = 'bg-blue-500';
                    if (promo.is_exploration) {
                      dotColor = 'bg-purple-500';
                    } else if (promo.status === 'completed') {
                      dotColor = 'bg-gray-500';
                    } else if (promo.status === 'active') {
                      dotColor = 'bg-green-500';
                    }

                    return (
                      <div
                        key={promo.id}
                        className="text-xs flex items-start gap-1.5 group cursor-pointer"
                        title={`${promo.name || 'Promotion'} - ${promo.discount_type === 'percentage' ? `${promo.discount_value}%` : `$${promo.discount_value}`} off`}
                      >
                        <div className={`w-2 h-2 rounded-full ${dotColor} shrink-0 mt-0.5`} />
                        <span className="text-muted-foreground group-hover:text-foreground truncate leading-tight">
                          {promo.name || 'Promo'}
                        </span>
                      </div>
                    );
                  })}
                  {dayPromotions.length > 3 && (
                    <div className="text-xs text-muted-foreground">
                      +{dayPromotions.length - 3} more
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Legend */}
      <div className="px-6 py-4 border-t border-border bg-muted/30">
        <div className="flex flex-wrap gap-4 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-muted-foreground">Active</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span className="text-muted-foreground">Draft</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-gray-500" />
            <span className="text-muted-foreground">Completed</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-purple-500" />
            <span className="text-muted-foreground">Exploration Test</span>
          </div>
        </div>
      </div>
    </Card>
  );
}
