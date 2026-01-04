'use client';

import { useState, useRef } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload, Camera, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';

interface ExtractedItem {
  name: string;
  category: string | null;
  description: string | null;
  price: number | null;
  confidence: number;
}

interface MenuPhotoUploadProps {
  onItemsExtracted?: (items: ExtractedItem[]) => void;
}

export function MenuPhotoUpload({ onItemsExtracted }: MenuPhotoUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [extractedItems, setExtractedItems] = useState<ExtractedItem[]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      setError('Please upload an image file (JPEG, PNG, etc.)');
      return;
    }

    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB');
      return;
    }

    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => {
      setPreviewUrl(e.target?.result as string);
    };
    reader.readAsDataURL(file);

    // Upload and extract
    setUploading(true);
    setError(null);
    setExtractedItems([]);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('/api/recipes/menu/upload-photo', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to extract menu items');
      }

      const result = await response.json();

      if (result.total_items === 0) {
        setError(result.message || 'No menu items could be extracted. Please try a clearer photo.');
        return;
      }

      setExtractedItems(result.items);
      if (onItemsExtracted) {
        onItemsExtracted(result.items);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to upload menu photo');
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    setPreviewUrl(null);
    setExtractedItems([]);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Card */}
      <Card className="p-6">
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <div className="p-2 bg-muted rounded-lg">
              <Camera className="w-5 h-5 text-foreground" />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-foreground mb-2">Upload Menu Photo</h2>
              <p className="text-sm text-muted-foreground mb-4">
                Take a photo of your menu or upload an existing image. Our AI will extract all menu items,
                categories, and prices automatically.
              </p>
            </div>
          </div>

          {/* File Input */}
          <div className="flex gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileSelect}
              className="hidden"
              id="menu-photo-input"
            />
            <label htmlFor="menu-photo-input" className="flex-1">
              <div className="border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-foreground/20 transition-colors">
                {uploading ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className="w-8 h-8 text-muted-foreground animate-spin" />
                    <p className="text-sm text-muted-foreground">Extracting menu items...</p>
                  </div>
                ) : (
                  <>
                    <Upload className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                    <p className="text-sm font-medium text-foreground">Click to upload menu photo</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      JPEG, PNG up to 10MB
                    </p>
                  </>
                )}
              </div>
            </label>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </Card>

      {/* Preview & Results */}
      {(previewUrl || extractedItems.length > 0) && (
        <Card className="p-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-foreground">Extraction Results</h3>
              <Button variant="outline" size="sm" onClick={handleReset}>
                Upload Another
              </Button>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Preview */}
              {previewUrl && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">Uploaded Image</p>
                  <img
                    src={previewUrl}
                    alt="Menu preview"
                    className="rounded-lg border border-border w-full h-auto"
                  />
                </div>
              )}

              {/* Extracted Items */}
              {extractedItems.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-muted-foreground mb-2">
                    Extracted Items ({extractedItems.length})
                  </p>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {extractedItems.map((item, index) => (
                      <div
                        key={index}
                        className="p-3 bg-muted rounded-lg"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              <CheckCircle2 className="w-4 h-4 text-green-600 flex-shrink-0" />
                              <span className="font-medium text-foreground">{item.name}</span>
                            </div>
                            {item.category && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {item.category}
                              </p>
                            )}
                            {item.description && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {item.description}
                              </p>
                            )}
                          </div>
                          {item.price && (
                            <span className="text-sm font-semibold text-foreground">
                              ${item.price.toFixed(2)}
                            </span>
                          )}
                        </div>
                        {/* Confidence indicator */}
                        <div className="mt-2">
                          <div className="flex items-center gap-2">
                            <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
                              <div
                                className={`h-full ${
                                  item.confidence >= 0.9
                                    ? 'bg-green-600'
                                    : item.confidence >= 0.7
                                    ? 'bg-yellow-600'
                                    : 'bg-orange-600'
                                }`}
                                style={{ width: `${item.confidence * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {Math.round(item.confidence * 100)}%
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Next Steps */}
            {extractedItems.length > 0 && (
              <div className="bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                <p className="text-sm text-blue-800 dark:text-blue-300">
                  <strong>Next:</strong> These items have been added to your menu. Click "Confirm New Recipes"
                  to review and edit the AI-generated ingredient estimates for each item.
                </p>
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
