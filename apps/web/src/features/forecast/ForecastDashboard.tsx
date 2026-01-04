import { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, TrendingUp, AlertTriangle } from "lucide-react";
import { api, ForecastPoint, HistoryPoint } from "@/lib/api";
import { ProbabilisticChart } from "./ProbabilisticChart";

interface ChartDataPoint {
  date: string;
  actual?: number;
  p10?: number;
  p50?: number;
  p90?: number;
  range?: [number, number]; // For area chart
}

export default function ForecastDashboard() {
  const [items, setItems] = useState<string[]>([]);
  const [selectedItem, setSelectedItem] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [hasData, setHasData] = useState(true);

  // 1. Load Items (using menu endpoint)
  useEffect(() => {
    async function loadItems() {
      setLoading(true);
      const res = await api.menu.list();
      if (res.data) {
        const itemNames = res.data.items.map(i => i.name).sort();
        setItems(itemNames);
        setHasData(itemNames.length > 0);
        if (itemNames.length > 0 && !selectedItem) {
          setSelectedItem(itemNames[0]);
        }
      } else {
        const errorMsg = typeof res.error === 'string'
          ? res.error
          : JSON.stringify(res.error) || 'Failed to load menu items';
        setError(errorMsg);
        setHasData(false);
      }
      setLoading(false);
    }
    loadItems();
  }, []);

  // 2. Load Data when item selected
  useEffect(() => {
    if (!selectedItem) return;

    async function fetchData() {
      setLoading(true);
      setError(null); // Clear previous errors
      const res = await api.forecast.get(selectedItem);
      setLoading(false);

      if (res.data) {
        processData(res.data.history, res.data.forecast);
      } else if (res.error) {
        const errorMsg = typeof res.error === 'string'
          ? res.error
          : JSON.stringify(res.error);
        console.error('Forecast fetch error:', errorMsg);
        // Don't set error state here - it's okay if no forecast exists yet
      }
    }
    fetchData();
  }, [selectedItem]);

  function processData(history: HistoryPoint[], forecast: ForecastPoint[]) {
    // Merge history and forecast into unified timeline
    const data: ChartDataPoint[] = [];

    // History
    history.forEach(h => {
      data.push({
        date: h.date, // 'YYYY-MM-DD'
        actual: h.quantity
      });
    });

    // Forecast
    forecast.forEach(f => {
      // If date already exists (today?), merge?
      // Forecast usually starts tomorrow.
      // But if user generated forecast for today?
      const existing = data.find(d => d.date === f.date);
      if (existing) {
        existing.p10 = f.p10;
        existing.p50 = f.p50;
        existing.p90 = f.p90;
        existing.range = [f.p10, f.p90];
      } else {
        data.push({
          date: f.date,
          p10: f.p10,
          p50: f.p50,
          p90: f.p90,
          range: [f.p10, f.p90]
        });
      }
    });

    // Sort by date
    data.sort((a, b) => a.date.localeCompare(b.date));
    setChartData(data);
  }

  async function handleGenerate() {
    if (!selectedItem) return;
    setGenerating(true);
    setError(null); // Clear previous errors

    try {
      // Generate new forecast
      const genRes = await api.forecast.generate(selectedItem);

      if (genRes.error) {
        const errorMsg = typeof genRes.error === 'string'
          ? genRes.error
          : JSON.stringify(genRes.error);
        setError(errorMsg);
        setGenerating(false);
        return;
      }

      // Refresh view
      const res = await api.forecast.get(selectedItem);
      if (res.data) {
        processData(res.data.history, res.data.forecast);
      } else if (res.error) {
        const errorMsg = typeof res.error === 'string'
          ? res.error
          : JSON.stringify(res.error);
        setError(errorMsg);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate forecast');
    }

    setGenerating(false);
  }

  // Show empty state if no data
  if (!loading && !hasData) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Demand Intelligence</h2>
          <p className="text-muted-foreground mt-1">
            Probabilistic forecasting with confidence bands for inventory planning.
          </p>
        </div>

        <Card className="border-2 border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mb-4">
              <TrendingUp className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2">No Data Available</h3>
            <p className="text-sm text-muted-foreground max-w-md mb-6">
              Upload your sales data to generate demand forecasts. You'll need at least 30 days of transaction history to get started.
            </p>
            <Button asChild>
              <a href="/dashboard/data">Upload Sales Data</a>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Demand Intelligence</h2>
          <p className="text-muted-foreground mt-1">
            7-day ahead forecasts with 90% confidence intervals for inventory planning.
          </p>
        </div>

        <div className="flex gap-2 items-center">
          <select
            className="h-10 w-[250px] rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            value={selectedItem}
            onChange={(e) => setSelectedItem(e.target.value)}
            disabled={loading || items.length === 0}
          >
            {items.length === 0 ? (
              <option>Loading...</option>
            ) : (
              items.map(name => (
                <option key={name} value={name}>{name}</option>
              ))
            )}
          </select>

          <Button
            onClick={handleGenerate}
            disabled={generating || !selectedItem || loading}
            className="min-w-[140px]"
          >
            {generating ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <TrendingUp className="mr-2 h-4 w-4" />
                Generate Forecast
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <Card className="border-destructive/50 bg-destructive/10">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertTriangle className="h-5 w-5 text-destructive shrink-0" />
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Main Chart */}
      {selectedItem ? (
        <ProbabilisticChart data={chartData} itemName={selectedItem} />
      ) : (
        <Card>
          <CardContent className="h-[400px] flex items-center justify-center text-muted-foreground">
            Please select a menu item to view forecasts.
          </CardContent>
        </Card>
      )}

      {/* Actionable Insights */}
      {chartData.length > 0 && chartData.some(d => d.p50 !== undefined) && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Next 7 Days</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {chartData.filter(d => d.p50 !== undefined).reduce((sum, d) => sum + (d.p50 || 0), 0).toFixed(0)} units
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Expected total demand (median)
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Peak Day</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(() => {
                  const forecast = chartData.filter(d => d.p50 !== undefined);
                  if (forecast.length === 0) return '-';
                  const peak = forecast.reduce((max, d) => (d.p50 || 0) > (max.p50 || 0) ? d : max);
                  return new Date(peak.date).toLocaleDateString('en-US', { weekday: 'short' });
                })()}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Highest forecasted demand
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Safety Stock</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(() => {
                  const forecast = chartData.filter(d => d.p90 !== undefined);
                  if (forecast.length === 0) return '-';
                  const maxP90 = Math.max(...forecast.map(d => d.p90 || 0));
                  return maxP90.toFixed(0);
                })()}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Maximum daily prep needed (90% level)
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Helpful Tips */}
      {chartData.length > 0 && chartData.some(d => d.p50 !== undefined) && (
        <Card className="bg-muted/30 border-border">
          <CardHeader>
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              How to use these forecasts
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>• <strong>Expected Demand:</strong> Use the median (p50) line for average prep planning</p>
            <p>• <strong>Safety Stock:</strong> Prep to the upper bound (p90) on peak days to avoid stockouts</p>
            <p>• <strong>Confidence Band:</strong> The shaded area shows likely demand range (80% probability)</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
