'use client';

import { OperatingHoursEditor, ServicePeriodsCalendar, FeatureSettings } from '@/features/settings';
import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-muted rounded-lg">
          <Settings className="w-6 h-6 text-foreground" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-muted-foreground">Configure your restaurant profile and features</p>
        </div>
      </div>

      {/* Feature Settings */}
      <FeatureSettings />

      {/* Why This Matters */}
      <div className="bg-muted/50 border border-border rounded-xl p-6">
        <h3 className="font-semibold text-foreground mb-2">Why accurate hours matter</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Operating hours directly impact forecast accuracy. When Flux knows your actual hours,
          it can normalize demand correctly—preventing a half-day closure from being misinterpreted
          as low demand. Accurate holidays prevent forecast errors on special days.
        </p>
      </div>

      {/* Operating Hours */}
      <OperatingHoursEditor />

      {/* Service Periods */}
      <ServicePeriodsCalendar />
    </div>
  );
}
