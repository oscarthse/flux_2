'use client';

import { OverallScore } from "./OverallScore";
import { SubScoreCard } from "./SubScoreCard";
import { RecommendationsList } from "./RecommendationsList";
import { DataHealthScore } from "./types";
import { RefreshCcw, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DataHealthDashboardProps {
  data: DataHealthScore | null;
  isLoading: boolean;
  onRefresh: () => void;
}

export function DataHealthDashboard({ data, isLoading, onRefresh }: DataHealthDashboardProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-12 w-12 border-2 border-muted border-t-foreground"></div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold text-foreground">No Health Score Available</h2>
        <p className="text-muted-foreground mt-2">Upload data to generate your first score.</p>
        <button
          onClick={onRefresh}
          className="mt-4 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition"
        >
          Refresh
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-700">

      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Data Health</h1>
          <p className="text-muted-foreground mt-1">
            Real-time analysis of your data quality and readiness for forecasting.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-muted-foreground bg-muted px-3 py-1 rounded-full">
          <Clock className="w-3 h-3" />
          Last calculated: {new Date(data.calculated_at).toLocaleString()}
          <button onClick={onRefresh} className="ml-2 hover:text-foreground transition-colors" title="Refresh">
            <RefreshCcw className="w-3 h-3" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Left Column: Overall Score & Context */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-card border border-border rounded-xl shadow-sm overflow-hidden">
            <OverallScore score={Number(data.overall_score)} />
          </div>

          <div className="bg-muted/50 border border-border rounded-xl p-6">
            <h3 className="font-semibold text-foreground mb-2">Why this matters</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Higher data health scores directly correlate with more accurate demand forecasts.
              Improving your score from 60% to 90% can reduce forecast error by up to 25%.
            </p>
          </div>
        </div>

        {/* Right Column: Breakdown & Actions */}
        <div className="lg:col-span-2 space-y-8">

          {/* Sub Scores Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <SubScoreCard
              title="Completeness"
              score={Number(data.completeness_score)}
              type="completeness"
            />
            <SubScoreCard
              title="Consistency"
              score={Number(data.consistency_score)}
              type="consistency"
            />
            <SubScoreCard
              title="Timeliness"
              score={Number(data.timeliness_score)}
              type="timeliness"
            />
            <SubScoreCard
              title="Accuracy"
              score={Number(data.accuracy_score)}
              type="accuracy"
            />
          </div>

          {/* Recommendations */}
          <div>
            <RecommendationsList items={data.recommendations} />
          </div>
        </div>
      </div>
    </div>
  );
}
