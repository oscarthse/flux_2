'use client';

import { useState, useEffect, useRef } from 'react';
import { DataHealthScore, api, CSVPreviewResponse } from "@/lib/api";
import { useAuth } from '@/contexts/auth-context';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload, RefreshCcw, FileText, CheckCircle2, XCircle, AlertCircle, Loader2, X } from 'lucide-react';
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

  // Upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CSVPreviewResponse | null>(null);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Trigger file picker
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  // Handle file selection
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setSelectedFile(file);
    setUploadError(null);
    setIsPreviewLoading(true);

    // Get preview
    const { data, error } = await api.data.previewCSV(file);
    
    if (data) {
      setPreview(data);
    } else {
      setUploadError(error || 'Failed to preview file');
    }
    
    setIsPreviewLoading(false);
  };

  // Handle actual upload
  const handleConfirmUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadError(null);

    const { data, error } = await api.data.uploadCSV(selectedFile);

    if (data) {
      // Success - refresh uploads list and close modal
      setSelectedFile(null);
      setPreview(null);
      fetchUploads();
      fetchHealthData();
    } else {
      setUploadError(error || 'Failed to upload file');
    }

    setIsUploading(false);
  };

  // Cancel upload
  const handleCancelUpload = () => {
    setSelectedFile(null);
    setPreview(null);
    setUploadError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

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
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileSelect}
        accept=".csv"
        className="hidden"
      />

      {/* Upload Preview Modal */}
      {(selectedFile || isPreviewLoading) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-2xl max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="text-lg font-semibold">Upload CSV Preview</h3>
              <Button variant="ghost" size="sm" onClick={handleCancelUpload}>
                <X className="w-4 h-4" />
              </Button>
            </div>
            
            <CardContent className="p-4 overflow-y-auto max-h-[60vh]">
              {isPreviewLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                  <span className="ml-2 text-muted-foreground">Analyzing file...</span>
                </div>
              ) : preview ? (
                <div className="space-y-4">
                  {/* File info */}
                  <div className="bg-muted/50 rounded-lg p-3">
                    <p className="text-sm"><strong>File:</strong> {selectedFile?.name}</p>
                    <p className="text-sm"><strong>Detected format:</strong> {preview.vendor}</p>
                    <p className="text-sm"><strong>Total rows:</strong> {preview.total_rows}</p>
                    <p className="text-sm"><strong>Success rate:</strong> {(preview.success_rate * 100).toFixed(1)}%</p>
                  </div>

                  {/* Errors */}
                  {preview.errors.length > 0 && (
                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
                      <p className="text-sm font-medium text-red-800 dark:text-red-400 mb-2">Errors found:</p>
                      <ul className="text-sm text-red-700 dark:text-red-300 space-y-1">
                        {preview.errors.slice(0, 5).map((err, i) => (
                          <li key={i}>Row {err.row_number || '?'}: {err.message}</li>
                        ))}
                        {preview.errors.length > 5 && (
                          <li>...and {preview.errors.length - 5} more</li>
                        )}
                      </ul>
                    </div>
                  )}

                  {/* Preview table */}
                  {preview.parsed_rows.length > 0 && (
                    <div>
                      <p className="text-sm font-medium mb-2">Preview (first {preview.parsed_rows.length} rows):</p>
                      <div className="border rounded-lg overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-muted">
                            <tr>
                              <th className="px-3 py-2 text-left">Date</th>
                              <th className="px-3 py-2 text-left">Item</th>
                              <th className="px-3 py-2 text-right">Qty</th>
                              <th className="px-3 py-2 text-right">Price</th>
                              <th className="px-3 py-2 text-right">Total</th>
                            </tr>
                          </thead>
                          <tbody>
                            {preview.parsed_rows.map((row, i) => (
                              <tr key={i} className="border-t">
                                <td className="px-3 py-2">{row.date}</td>
                                <td className="px-3 py-2">{row.item_name}</td>
                                <td className="px-3 py-2 text-right">{row.quantity}</td>
                                <td className="px-3 py-2 text-right">${Number(row.unit_price || 0).toFixed(2)}</td>
                                <td className="px-3 py-2 text-right">${Number(row.total || 0).toFixed(2)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              ) : uploadError ? (
                <div className="text-center py-8">
                  <XCircle className="w-12 h-12 text-red-500 mx-auto mb-3" />
                  <p className="text-red-600">{uploadError}</p>
                </div>
              ) : null}
            </CardContent>

            {/* Actions */}
            {preview && (
              <div className="flex justify-end gap-2 p-4 border-t">
                <Button variant="outline" onClick={handleCancelUpload}>
                  Cancel
                </Button>
                <Button onClick={handleConfirmUpload} disabled={isUploading || !preview.schema_detected}>
                  {isUploading ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Uploading...
                    </>
                  ) : (
                    <>
                      <Upload className="w-4 h-4 mr-2" />
                      Confirm Upload
                    </>
                  )}
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

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
          <Button onClick={handleUploadClick}>
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
              <Button onClick={handleUploadClick}>
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
