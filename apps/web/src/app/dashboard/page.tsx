'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@/contexts/auth-context';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Upload,
  TrendingUp,
  ChartBar,
  Settings,
  ArrowRight,
  FileText
} from 'lucide-react';

interface Upload {
  id: string;
  status: string;
  rows_processed?: number;
  rows_failed?: number;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchUploads = async () => {
      const { data } = await api.data.uploads();
      if (data) {
        setUploads(data.uploads);
      }
      setIsLoading(false);
    };

    fetchUploads();
  }, []);

  const totalRows = uploads.reduce((acc, u) => acc + (u.rows_processed || 0), 0);
  const successfulUploads = uploads.filter(u => u.status === 'COMPLETED').length;
  const hasData = uploads.length > 0 && successfulUploads > 0;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Welcome */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Welcome back</h1>
        <p className="text-muted-foreground mt-1">
          {hasData
            ? "Your restaurant insights are ready to view."
            : "Let's get started by uploading your sales data."}
        </p>
      </div>

      {/* No data state - prominent CTA */}
      {!hasData && !isLoading && (
        <Card className="border-2 border-dashed bg-muted/30">
          <CardContent className="flex flex-col items-center justify-center py-12 px-6 text-center">
            <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
              <Upload className="w-8 h-8 text-primary" />
            </div>
            <h3 className="text-xl font-semibold text-foreground mb-2">Get Started with Flux</h3>
            <p className="text-sm text-muted-foreground max-w-md mb-6">
              Upload your POS transaction data to unlock demand forecasting, inventory insights, and profitability analysis.
              You'll need at least 30 days of sales history to begin.
            </p>
            <div className="flex gap-3">
              <Button asChild size="lg">
                <a href="/dashboard/data">
                  <Upload className="mr-2 h-4 w-4" />
                  Upload Sales Data
                </a>
              </Button>
              <Button asChild variant="outline" size="lg">
                <a href="/dashboard/settings">
                  <Settings className="mr-2 h-4 w-4" />
                  Configure Settings
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Quick Actions - Only show when data exists */}
      {hasData && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => window.location.href = '/dashboard/forecast'}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center">
                    <TrendingUp className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground" />
                </div>
                <CardTitle className="text-base">View Forecasts</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  7-day demand predictions with confidence intervals
                </p>
              </CardContent>
            </Card>

            <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => window.location.href = '/dashboard/recipes'}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 bg-emerald-100 dark:bg-emerald-900/30 rounded-lg flex items-center justify-center">
                    <ChartBar className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground" />
                </div>
                <CardTitle className="text-base">Menu Analytics</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Profitability and performance by menu item
                </p>
              </CardContent>
            </Card>

            <Card className="hover:shadow-md transition-shadow cursor-pointer" onClick={() => window.location.href = '/dashboard/data'}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900/30 rounded-lg flex items-center justify-center">
                    <Upload className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                  </div>
                  <ArrowRight className="w-4 h-4 text-muted-foreground" />
                </div>
                <CardTitle className="text-base">Upload More Data</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Keep your insights fresh with the latest sales
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Quick stats */}
      {hasData && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Data Overview</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <p className="text-sm text-muted-foreground">Total Uploads</p>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{uploads.length}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <p className="text-sm text-muted-foreground">Successful</p>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{successfulUploads}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <p className="text-sm text-muted-foreground">Transactions</p>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{totalRows.toLocaleString()}</p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <p className="text-sm text-muted-foreground">Status</p>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 bg-emerald-500 rounded-full"></div>
                  <p className="text-2xl font-bold">Active</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Recent activity */}
      {hasData && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">Recent Uploads</h2>
            <Button asChild variant="ghost" size="sm">
              <a href="/dashboard/data">
                View all <ArrowRight className="ml-1 h-4 w-4" />
              </a>
            </Button>
          </div>
          {isLoading ? (
            <Card>
              <CardContent className="p-8 text-center">
                <div className="animate-spin rounded-full h-6 w-6 border-2 border-muted border-t-foreground mx-auto"></div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="divide-y divide-border">
                  {uploads.slice(0, 5).map((upload) => (
                    <div key={upload.id} className="px-5 py-4 flex items-center justify-between hover:bg-muted/50 transition">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                          <FileText className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div>
                          <p className="text-sm font-medium">Data upload</p>
                          <p className="text-xs text-muted-foreground">{upload.rows_processed || 0} transactions processed</p>
                        </div>
                      </div>
                      <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${
                        upload.status === 'COMPLETED'
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400'
                          : upload.status === 'FAILED'
                            ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                            : 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
                      }`}>
                        {upload.status.toLowerCase()}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
