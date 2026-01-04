'use client';

import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';

interface OverallScoreProps {
  score: number;
}

export function OverallScore({ score }: OverallScoreProps) {
  const roundedScore = Math.round(score);

  // Color determination
  let color = "#ef4444"; // red-500
  if (score >= 80) color = "#10b981"; // emerald-500
  else if (score >= 60) color = "#f59e0b"; // amber-500

  // Chart data
  const data = [
    { value: score },
    { value: 100 - score },
  ];

  return (
    <div className="relative flex flex-col items-center justify-center p-6">
      <div className="h-64 w-64 relative">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={80}
              outerRadius={100}
              startAngle={180}
              endAngle={0}
              paddingAngle={0}
              dataKey="value"
              stroke="none"
              cornerRadius={10}
            >
              <Cell key="score" fill={color} />
              <Cell key="remaining" fill="#e7e5e4" /> {/* stone-200 */}
            </Pie>
          </PieChart>
        </ResponsiveContainer>

        {/* Score Text Overlay */}
        <div className="absolute inset-x-0 bottom-1/2 translate-y-8 flex flex-col items-center justify-center">
          <span className="text-6xl font-bold tracking-tighter text-foreground">
            {roundedScore}%
          </span>
          <span className="text-sm font-medium text-muted-foreground uppercase tracking-wider mt-2">
            Health Score
          </span>
        </div>
      </div>

      <div className="text-center md:max-w-xs mt-[-40px]">
        <p className="text-sm text-muted-foreground">
          {score >= 80 ? "Your data is in great shape. Forecasts will be highly accurate." :
            score >= 60 ? "Data is acceptable but needs improvement for optimal results." :
              "Critical data issues detected. Forecasting accuracy is severely impacted."}
        </p>
      </div>
    </div>
  );
}
