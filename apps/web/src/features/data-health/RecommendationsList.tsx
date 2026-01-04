import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Recommendation } from "./types";
import { Badge } from "@/components/ui/badge";
import { ChevronRight, Upload, AlertTriangle, FileText, CheckCircle2 } from "lucide-react";

interface RecommendationsListProps {
  items: Recommendation[];
}

export function RecommendationsList({ items }: RecommendationsListProps) {
  if (items.length === 0) {
    return (
      <Card className="bg-card border-border">
        <CardContent className="flex flex-col items-center justify-center p-8 text-center">
          <CheckCircle2 className="h-12 w-12 text-primary mb-4" />
          <h3 className="text-lg font-medium text-foreground">All Clear</h3>
          <p className="text-sm text-muted-foreground mt-2">
            Your data health is excellent. No immediate actions required.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-foreground">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
          Recommended Actions
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-4">
        {items.map((rec, index) => (
          <div
            key={index}
            className="flex items-start gap-4 p-4 rounded-lg border border-border bg-card hover:bg-muted/50 transition-colors cursor-pointer group"
          >
            <div className="mt-1 bg-muted p-2 rounded-full">
              {rec.action === 'upload_csv' ? <Upload className="h-4 w-4 text-foreground" /> : <FileText className="h-4 w-4 text-foreground" />}
            </div>

            <div className="flex-1 space-y-1">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-foreground">{rec.title}</h4>
                <Badge
                  variant={rec.priority === 'high' ? 'destructive' : 'secondary'}
                >
                  {rec.priority}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground leading-relaxed">
                {rec.description}
              </p>
            </div>

            <div className="self-center">
              <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-foreground transition-colors" />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
