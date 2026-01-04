import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { format, parseISO } from 'date-fns';

interface ForecastDataPoint {
  date: string;
  actual?: number;
  p10?: number;
  p50?: number; // Median Forecast
  p90?: number;
  range?: [number, number];
}

interface ProbabilisticChartProps {
  data: ForecastDataPoint[];
  itemName: string;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const p50 = payload.find((p: any) => p.dataKey === 'p50')?.value;
    const actual = payload.find((p: any) => p.dataKey === 'actual')?.value;
    const range = payload.find((p: any) => p.dataKey === 'range')?.value;

    return (
      <div className="bg-popover border border-border p-3 rounded-lg shadow-lg">
        <p className="text-sm font-medium mb-2">{format(parseISO(label), 'EEE, MMM d, yyyy')}</p>

        {actual !== undefined && (
          <div className="flex items-center gap-2 text-sm text-emerald-500 font-bold">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            Actual Sales: {actual}
          </div>
        )}

        {p50 !== undefined && (
          <div className="flex items-center gap-2 text-sm text-indigo-500 font-bold">
            <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
            Forecast (Median): {Math.round(p50)}
          </div>
        )}

        {range && (
          <div className="mt-2 pt-2 border-t border-border text-xs text-muted-foreground">
            <span className="font-semibold text-indigo-400">80% Confidence Band</span><br />
            High Risk (P90): {Math.round(range[1])}<br />
            Low Risk (P10): {Math.round(range[0])}
          </div>
        )}
      </div>
    );
  }
  return null;
};

export function ProbabilisticChart({ data, itemName }: ProbabilisticChartProps) {
  // Find last actual data point to draw split line
  const lastHistoryDate = data.filter(d => d.actual !== undefined).pop()?.date;

  return (
    <Card className="col-span-4 shadow-md bg-card/60 backdrop-blur-sm">
      <CardHeader>
        <CardTitle>Forecast Analysis: {itemName}</CardTitle>
        <CardDescription>
          Historical sales vs. Probabilistic demand projection
        </CardDescription>
      </CardHeader>
      <CardContent className="pl-0">
        <ResponsiveContainer width="100%" height={450}>
          <ComposedChart data={data} margin={{ top: 20, right: 30, left: 10, bottom: 0 }}>
            <defs>
              <linearGradient id="colorForecast" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.4} /> {/* Indigo-500 */}
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0.05} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="3 3" className="stroke-muted/40" vertical={false} />

            <XAxis
              dataKey="date"
              stroke="#888888"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => format(parseISO(value), 'MMM d')}
              minTickGap={30}
            />

            <YAxis
              stroke="#888888"
              fontSize={12}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value) => `${value}`}
            />

            <Tooltip content={<CustomTooltip />} />

            <Legend
              verticalAlign="top"
              height={36}
              iconType="circle"
            />

            {/* Today Reference Line */}
            {lastHistoryDate && (
              <ReferenceLine x={lastHistoryDate} stroke="#fbbf24" strokeDasharray="3 3" label="Today" />
            )}

            {/* Confidence Band (Area) */}
            <Area
              type="monotone"
              dataKey="range"
              name="Confidence Interval (P10-P90)"
              stroke="none"
              fill="url(#colorForecast)"
            />

            {/* Forecast Line (P50) */}
            <Line
              type="monotone"
              dataKey="p50"
              name="Forecast (Median)"
              stroke="#6366f1" // Indigo
              strokeWidth={3}
              dot={{ r: 0 }}
              activeDot={{ r: 6 }}
              strokeDasharray="4 4"
            />

            {/* History Line (Actual) */}
            <Line
              type="monotone"
              dataKey="actual"
              name="Actual Sales"
              stroke="#10b981" // Emerald
              strokeWidth={2}
              dot={{ r: 2, fill: "#10b981" }}
              connectNulls={false}
            />

          </ComposedChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
