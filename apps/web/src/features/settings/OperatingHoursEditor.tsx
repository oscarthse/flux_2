'use client';

import { useState, useEffect } from 'react';
import { api, DaySchedule, WeeklySchedule } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RefreshCcw, Save, Clock, Info } from 'lucide-react';

interface OperatingHoursEditorProps {
  onSaveSuccess?: () => void;
}

export function OperatingHoursEditor({ onSaveSuccess }: OperatingHoursEditorProps) {
  const [schedule, setSchedule] = useState<DaySchedule[]>([]);
  const [source, setSource] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    loadSchedule();
  }, []);

  const loadSchedule = async () => {
    setIsLoading(true);
    setError(null);
    const result = await api.settings.getOperatingHours();
    if (result.data) {
      setSchedule(result.data.schedule);
      setSource(result.data.source);
      setHasChanges(false);
    } else {
      setError(result.error || 'Failed to load schedule');
    }
    setIsLoading(false);
  };

  const handleTimeChange = (dayIndex: number, field: 'open_time' | 'close_time', value: string) => {
    setSchedule(prev => prev.map((day, i) =>
      i === dayIndex ? { ...day, [field]: value || null } : day
    ));
    setHasChanges(true);
  };

  const handleClosedToggle = (dayIndex: number) => {
    setSchedule(prev => prev.map((day, i) =>
      i === dayIndex
        ? {
          ...day,
          is_closed: !day.is_closed,
          open_time: !day.is_closed ? null : day.open_time,
          close_time: !day.is_closed ? null : day.close_time
        }
        : day
    ));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    const result = await api.settings.updateOperatingHours({ schedule });
    if (result.data) {
      setSource('manual');
      setHasChanges(false);
      onSaveSuccess?.();
    } else {
      setError(result.error || 'Failed to save schedule');
    }
    setIsSaving(false);
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
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border flex items-center justify-between bg-muted/30">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-muted rounded-lg">
            <Clock className="w-5 h-5 text-foreground" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-foreground">Operating Hours</h2>
            <p className="text-sm text-muted-foreground">Set your weekly schedule</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={loadSchedule}
            disabled={isLoading}
          >
            <RefreshCcw className="w-4 h-4" />
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={!hasChanges || isSaving}
            variant="default"
          >
            {isSaving ? (
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-primary-foreground border-t-transparent" />
            ) : (
              <>
                <Save className="w-4 h-4 mr-1" />
                Save
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-6 py-3 bg-destructive/10 border-b border-destructive/20 text-destructive text-sm">
          {error}
        </div>
      )}

      {/* Source Badge */}
      {source === 'inferred' && (
        <div className="px-6 py-3 bg-blue-50/50 border-b border-blue-200/50 flex items-center gap-2 dark:bg-blue-900/20 dark:border-blue-900/30">
          <Info className="w-4 h-4 text-blue-600 dark:text-blue-400" />
          <span className="text-sm text-blue-800 dark:text-blue-300">
            Hours inferred from your sales data. Edit to correct if needed.
          </span>
        </div>
      )}

      {/* Schedule Grid */}
      <div className="p-6">
        <div className="space-y-3">
          {schedule.map((day, index) => (
            <div
              key={day.day_of_week}
              className={`flex items-center gap-4 p-4 rounded-xl transition-all border ${day.is_closed
                ? 'bg-muted/50 border-transparent opacity-80'
                : 'bg-card border-border hover:border-foreground/20'
                }`}
            >
              {/* Day Name */}
              <div className="w-28 font-medium text-foreground">
                {day.day_name}
              </div>

              {/* Time Inputs */}
              <div className={`flex items-center gap-2 flex-1 ${day.is_closed ? 'opacity-40' : ''}`}>
                <input
                  type="time"
                  value={day.open_time || ''}
                  onChange={(e) => handleTimeChange(index, 'open_time', e.target.value)}
                  disabled={day.is_closed}
                  className="px-3 py-2 border border-input rounded-lg text-sm bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-input disabled:bg-muted"
                />
                <span className="text-muted-foreground">—</span>
                <input
                  type="time"
                  value={day.close_time || ''}
                  onChange={(e) => handleTimeChange(index, 'close_time', e.target.value)}
                  disabled={day.is_closed}
                  className="px-3 py-2 border border-input rounded-lg text-sm bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-input disabled:bg-muted"
                />
              </div>

              {/* Open/Closed Toggle */}
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <div
                  className={`relative w-10 h-6 rounded-full transition-colors ${!day.is_closed ? 'bg-primary' : 'bg-input'
                    }`}
                  onClick={() => handleClosedToggle(index)}
                >
                  <div
                    className={`absolute top-1 left-1 w-4 h-4 rounded-full bg-background shadow transition-transform ${!day.is_closed ? 'translate-x-4' : ''
                      }`}
                  />
                </div>
                <span className={`text-sm font-medium ${!day.is_closed ? 'text-primary' : 'text-muted-foreground'}`}>
                  {day.is_closed ? 'Closed' : 'Open'}
                </span>
              </label>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
