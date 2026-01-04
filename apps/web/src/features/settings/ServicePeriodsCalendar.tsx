'use client';

import { useState, useEffect } from 'react';
import { api, ServicePeriod, ServicePeriodCreate } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CalendarDays, Plus, Trash2, X } from 'lucide-react';
import { format, parseISO, isFuture, isToday } from 'date-fns';

export function ServicePeriodsCalendar() {
  const [periods, setPeriods] = useState<ServicePeriod[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    loadPeriods();
  }, []);

  const loadPeriods = async () => {
    setIsLoading(true);
    setError(null);
    const result = await api.settings.getServicePeriods();
    if (result.data) {
      setPeriods(result.data.periods);
    } else {
      setError(result.error || 'Failed to load service periods');
    }
    setIsLoading(false);
  };

  const handleDelete = async (id: string) => {
    const result = await api.settings.deleteServicePeriod(id);
    if (!result.error) {
      setPeriods(prev => prev.filter(p => p.id !== id));
    } else {
      setError(result.error || 'Failed to delete');
    }
  };

  const handleAdd = async (data: ServicePeriodCreate) => {
    const result = await api.settings.createServicePeriod(data);
    if (result.data) {
      setPeriods(prev => [result.data!, ...prev].sort((a, b) =>
        new Date(a.date).getTime() - new Date(b.date).getTime()
      ));
      setShowAddModal(false);
    } else {
      setError(result.error || 'Failed to add period');
    }
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="flex items-center justify-center h-48">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-200 border-t-amber-900" />
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card className="overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-amber-100 flex items-center justify-between bg-gradient-to-r from-orange-50 to-red-50">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-orange-100 rounded-lg">
              <CalendarDays className="w-5 h-5 text-orange-700" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-stone-900">Holidays & Closures</h2>
              <p className="text-sm text-stone-500">Schedule exceptions to regular hours</p>
            </div>
          </div>
          <Button
            size="sm"
            onClick={() => setShowAddModal(true)}
            className="bg-orange-600 hover:bg-orange-700"
          >
            <Plus className="w-4 h-4 mr-1" />
            Add
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="px-6 py-3 bg-red-50 border-b border-red-100 text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Periods List */}
        <div className="p-6">
          {periods.length === 0 ? (
            <div className="text-center py-8">
              <CalendarDays className="w-12 h-12 text-stone-300 mx-auto mb-3" />
              <p className="text-stone-500 font-medium">No scheduled closures</p>
              <p className="text-sm text-stone-400 mt-1">
                Forecasts will assume regular operating hours.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {periods.map(period => (
                <div
                  key={period.id}
                  className={`flex items-center justify-between p-4 rounded-xl transition-all ${isFuture(parseISO(period.date)) || isToday(parseISO(period.date))
                      ? 'bg-orange-50/50 hover:bg-orange-50'
                      : 'bg-stone-50/50 opacity-60'
                    }`}
                >
                  <div className="flex items-center gap-4">
                    <div className="text-center min-w-[60px]">
                      <div className="text-xs font-medium text-stone-500 uppercase">
                        {format(parseISO(period.date), 'MMM')}
                      </div>
                      <div className="text-2xl font-bold text-stone-800">
                        {format(parseISO(period.date), 'd')}
                      </div>
                    </div>
                    <div>
                      <div className="font-medium text-stone-800">
                        {period.reason || 'Custom Hours'}
                      </div>
                      <div className="text-sm text-stone-500">
                        {period.is_closed
                          ? 'Closed all day'
                          : `${period.open_time} — ${period.close_time}`
                        }
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleDelete(period.id)}
                    className="p-2 text-stone-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Add Modal */}
      {showAddModal && (
        <AddPeriodModal
          onClose={() => setShowAddModal(false)}
          onAdd={handleAdd}
        />
      )}
    </>
  );
}

interface AddPeriodModalProps {
  onClose: () => void;
  onAdd: (data: ServicePeriodCreate) => void;
}

function AddPeriodModal({ onClose, onAdd }: AddPeriodModalProps) {
  const [date, setDate] = useState('');
  const [reason, setReason] = useState('');
  const [isClosed, setIsClosed] = useState(true);
  const [openTime, setOpenTime] = useState('');
  const [closeTime, setCloseTime] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!date) return;

    setIsSubmitting(true);
    await onAdd({
      date,
      reason: reason || null,
      is_closed: isClosed,
      open_time: isClosed ? null : openTime || null,
      close_time: isClosed ? null : closeTime || null,
    });
    setIsSubmitting(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 animate-in fade-in">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 animate-in zoom-in-95">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">Add Holiday or Closure</h3>
          <button onClick={onClose} className="p-1 hover:bg-stone-100 rounded">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
              className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Reason (optional)</label>
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Christmas Day, Private Event"
              className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            />
          </div>

          <div>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={isClosed}
                onChange={(e) => setIsClosed(e.target.checked)}
                className="w-4 h-4 text-amber-600 rounded"
              />
              <span className="text-sm text-stone-700">Closed all day</span>
            </label>
          </div>

          {!isClosed && (
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">Open</label>
                <input
                  type="time"
                  value={openTime}
                  onChange={(e) => setOpenTime(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-stone-700 mb-1">Close</label>
                <input
                  type="time"
                  value={closeTime}
                  onChange={(e) => setCloseTime(e.target.value)}
                  className="w-full px-3 py-2 border border-stone-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                />
              </div>
            </div>
          )}

          <div className="flex gap-3 pt-2">
            <Button type="button" variant="outline" onClick={onClose} className="flex-1">
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!date || isSubmitting}
              className="flex-1 bg-amber-600 hover:bg-amber-700"
            >
              {isSubmitting ? 'Adding...' : 'Add'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
