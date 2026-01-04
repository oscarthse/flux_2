'use client';

import { useState, useEffect } from 'react';
import { DataHealthScore, api } from "@/lib/api";
import { useAuth } from '@/contexts/auth-context';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload, RefreshCcw, FileText, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { OverallScore } from "@/features/data-health/OverallScore";
import { SubScoreCard } from "@/features/data-health/SubScoreCard";
import { RecommendationsList } from "@/features/data-health/RecommendationsList";

interface UploadRecord {
  id: string;
  status: string;
  rows_processed?: number;
  rows_failed?: number;
  created_at?: string;
}

export default function DataPage() {
  const [healthData, setHealthData] = useState<DataHealthScore | null>(null);
  const [uploads, setUploads] = useState<UploadRecord[]>([]);
  const [isLoadingHealth, setIsLoadingHealth] = useState(true);
  const [isLoadingUploads, setIsLoadingUploads] = useState(true);
  const { user } = useAuth();

  const fetchHealthData = async () => {
    setIsLoadingHealth(true);
    try {
      const { data, error } = await api.data.health();
      if (data) {
        setHealthData(data);
      } else if (error) {
        console.error("Failed to fetch data health:", error);
      }
    } catch (error) {
      console.error("Failed to fetch data health", error);
    } finally {
      setIsLoadingHealth(false);
    }
  };

  const fetchUploads = async () => {
    setIsLoadingUploads(true);
    try {
      const { data } = await api.data.uploads();
      if (data) {
        setUploads(data.uploads);
      }
    } catch (error) {
      console.error("Failed to fetch uploads", error);
    } finally {
      setIsLoadingUploads(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchHealthData();
      fetchUploads();
    }
  }, [user]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return <CheckCircle2 className="w-4 h-4 text-emerald-600" />;
      case 'FAILED':
        return <XCircle className="w-4 h-4 text-red-600" />;
      default:
        return <AlertCircle className="w-4 h-4 text-amber-600" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400';
      case 'FAILED':
        return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
      default:
        return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400';
    }
  };

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Data</h1>
          <p className="text-muted-foreground mt-1">
            Monitor your data quality and manage uploads
          </p>
        </div>
        <Button onClick={() => { fetchHealthData(); fetchUploads(); }} variant="outline">
          <RefreshCcw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Data Health Section */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Data Health</h2>

        {isLoadingHealth ? (
          <div className="flex items-center justify-center min-h-[300px]">
            <div className="animate-spin rounded-full h-12 w-12 border-2 border-muted border-t-foreground"></div>
          </div>
        ) : healthData ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Overall Score */}
            <div className="lg:col-span-1">
              <Card>
                <CardContent className="pt-6">
                  <OverallScore score={Number(healthData.overall_score)} />
                </CardContent>
              </Card>

              <Card className="mt-4 bg-muted/30">
                <CardContent className="pt-6">
                  <h3 className="font-semibold mb-2">Why this matters</h3>
                  <p className="text-sm text-muted-foreground leading-relaxed">
                    Higher data health scores directly correlate with more accurate demand forecasts.
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Component Scores */}
            <div className="lg:col-span-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <SubScoreCard
                  title="Completeness"
                  score={Number(healthData.completeness_score)}
                  type="completeness"
                />
                <SubScoreCard
                  title="Consistency"
                  score={Number(healthData.consistency_score)}
                  type="consistency"
                />
                <SubScoreCard
                  title="Timeliness"
                  score={Number(healthData.timeliness_score)}
                  type="timeliness"
                />
                <SubScoreCard
                  title="Accuracy"
                  score={Number(healthData.accuracy_score)}
                  type="accuracy"
                />
              </div>

              {/* Recommendations */}
              {healthData.recommendations && healthData.recommendations.length > 0 && (
                <div className="mt-6">
                  <RecommendationsList items={healthData.recommendations} />
                </div>
              )}
            </div>
          </div>
        ) : (
          <Card>
            <CardContent className="text-center py-12">
              <h3 className="text-lg font-semibold">No Health Score Available</h3>
              <p className="text-muted-foreground mt-2">Upload data to generate your first score.</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Upload History Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Upload History</h2>
          <Button>
            <Upload className="w-4 h-4 mr-2" />
            Upload New Data
          </Button>
        </div>

        {isLoadingUploads ? (
          <Card>
            <CardContent className="p-8 text-center">
              <div className="animate-spin rounded-full h-6 w-6 border-2 border-muted border-t-foreground mx-auto"></div>
            </CardContent>
          </Card>
        ) : uploads.length > 0 ? (
          <Card>
            <CardContent className="p-0">
              <div className="divide-y divide-border">
                {uploads.map((upload) => (
                  <div key={upload.id} className="px-6 py-4 flex items-center justify-between hover:bg-muted/50 transition">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                        <FileText className="w-5 h-5 text-muted-foreground" />
                      </div>
                      <div>
                        <p className="text-sm font-medium">Data upload</p>
                        <p className="text-xs text-muted-foreground">
                          {upload.rows_processed || 0} transactions processed
                          {upload.rows_failed ? ` • ${upload.rows_failed} failed` : ''}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {getStatusIcon(upload.status)}
                      <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${getStatusColor(upload.status)}`}>
                        {upload.status.toLowerCase()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-2 border-dashed">
            <CardContent className="text-center py-12">
              <div className="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
                <Upload className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold mb-2">No uploads yet</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Upload your POS transaction data to get started with forecasting
              </p>
              <Button>
                <Upload className="w-4 h-4 mr-2" />
                Upload Your First File
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
