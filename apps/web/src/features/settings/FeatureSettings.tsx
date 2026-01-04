'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { api, type FeatureSettings as FeatureSettingsType } from '@/lib/api';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

export function FeatureSettings() {
  const [settings, setSettings] = useState<FeatureSettingsType>({ waste_factors_enabled: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    setLoading(true);
    const result = await api.settings.getFeatures();
    if (result.data) {
      setSettings(result.data);
    } else {
      setError(result.error || 'Failed to load feature settings');
    }
    setLoading(false);
  };

  const handleToggleWasteFactors = async (enabled: boolean) => {
    setSaving(true);
    setSaved(false);
    setError(null);

    const newSettings = { ...settings, waste_factors_enabled: enabled };
    setSettings(newSettings);

    const result = await api.settings.updateFeatures(newSettings);
    if (result.data) {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } else {
      setError(result.error || 'Failed to save settings');
      // Revert on error
      setSettings(settings);
    }
    setSaving(false);
  };

  if (loading) {
    return (
      <Card className="p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-muted rounded w-1/3"></div>
          <div className="h-4 bg-muted rounded w-2/3"></div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold text-foreground mb-2">Feature Settings</h2>
          <p className="text-sm text-muted-foreground">
            Enable or disable advanced features for your restaurant
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive text-sm">
            <AlertTriangle className="w-4 h-4" />
            {error}
          </div>
        )}

        {saved && (
          <div className="flex items-center gap-2 p-3 bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800 rounded-lg text-green-700 dark:text-green-400 text-sm">
            <CheckCircle2 className="w-4 h-4" />
            Settings saved successfully
          </div>
        )}

        {/* Waste Factors Toggle */}
        <div className="flex items-start justify-between p-4 border border-border rounded-lg">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-medium text-foreground">Waste Factor Analysis</h3>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                settings.waste_factors_enabled
                  ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
              }`}>
                {settings.waste_factors_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
            <p className="text-sm text-muted-foreground mb-3">
              Calculate true COGS including waste from trimming, spoilage, and prep errors.
              Shows hidden costs that impact margins by 3-6% on average.
            </p>
            <div className="text-xs text-muted-foreground space-y-1">
              <div>• Base cost + waste factor = true COGS</div>
              <div>• Identifies high-waste ingredients</div>
              <div>• Reveals hidden margin impact</div>
            </div>
          </div>

          <div className="flex flex-col items-end gap-2 ml-4">
            <Switch
              checked={settings.waste_factors_enabled}
              onCheckedChange={handleToggleWasteFactors}
              disabled={saving}
            />
            {saving && (
              <span className="text-xs text-muted-foreground">Saving...</span>
            )}
          </div>
        </div>

        {!settings.waste_factors_enabled && (
          <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
            <div className="flex gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
              <div>
                <div className="text-sm font-medium text-amber-900 dark:text-amber-100">
                  Waste factors disabled
                </div>
                <div className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                  COGS calculations will use simple ingredient costs without waste adjustments.
                  This may underestimate true costs and overestimate margins.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
