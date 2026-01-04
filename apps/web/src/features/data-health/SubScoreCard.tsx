import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Database, Clock, Activity, Target } from "lucide-react";

interface SubScoreCardProps {
  title: string;
  score: number;
  type: 'completeness' | 'consistency' | 'timeliness' | 'accuracy';
}

const ICONS = {
  completeness: Database,
  consistency: Activity,
  timeliness: Clock,
  accuracy: Target
};

const DESCRIPTIONS = {
  completeness: "Historical depth and item categorization",
  consistency: "Regularity of data uploads",
  timeliness: "Recency of transactions",
  accuracy: "Stockout and promotion tracking"
};

export function SubScoreCard({ title, score, type }: SubScoreCardProps) {
  const Icon = ICONS[type];

  // Color logic
  let colorClass = "bg-red-500";
  if (score >= 80) colorClass = "bg-emerald-500";
  else if (score >= 60) colorClass = "bg-amber-500";

  return (
    <Card className="overflow-hidden hover:shadow-md transition-shadow">
      <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between mb-2">
          <span className="text-2xl font-bold text-foreground">{Math.round(score)}%</span>
        </div>
        <Progress value={score} max={100} className="h-2" indicatorClassName={colorClass} />
        <p className="mt-3 text-xs text-muted-foreground">
          {DESCRIPTIONS[type]}
        </p>
      </CardContent>
    </Card>
  );
}
