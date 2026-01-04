'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { CheckCircle2 } from 'lucide-react';
import { api, type MenuItemWithEstimate } from '@/lib/api';

export function ConfirmedRecipes() {
  const [recipes, setRecipes] = useState<MenuItemWithEstimate[]>([]);
  const [loading, setLoading] = useState(true);
  const [wasteFactorsEnabled, setWasteFactorsEnabled] = useState(true);

  useEffect(() => {
    loadConfirmedRecipes();
    loadFeatureSettings();
  }, []);

  const loadConfirmedRecipes = async () => {
    setLoading(true);
    const result = await api.recipes.getConfirmed();
    if (result.data) {
      setRecipes(result.data.items);
    }
    setLoading(false);
  };

  const loadFeatureSettings = async () => {
    const result = await api.settings.getFeatures();
    if (result.data) {
      setWasteFactorsEnabled(result.data.waste_factors_enabled);
    }
  };

  const calculateTotal = (ingredients: Array<{ base_cost?: number; waste_factor?: number; estimated_cost: number }>) => {
    if (!wasteFactorsEnabled) {
      // When waste factors disabled, use base cost only
      return ingredients.reduce((sum, ing) => sum + Number(ing.base_cost || ing.estimated_cost), 0);
    }
    // When enabled, use estimated_cost which includes waste
    return ingredients.reduce((sum, ing) => sum + Number(ing.estimated_cost), 0);
  };

  const calculateBaseTotal = (ingredients: Array<{ base_cost?: number; estimated_cost: number }>) => {
    return ingredients.reduce((sum, ing) => sum + Number(ing.base_cost || ing.estimated_cost), 0);
  };

  const calculateWasteTotal = (ingredients: Array<{ base_cost?: number; waste_factor?: number; estimated_cost: number }>) => {
    if (!wasteFactorsEnabled) return 0;
    return ingredients.reduce((sum, ing) => {
      const base = Number(ing.base_cost || ing.estimated_cost);
      const waste = Number(ing.waste_factor || 0);
      return sum + (base * waste);
    }, 0);
  };

  const calculateMargin = (price: number | null, cost: number) => {
    if (!price || price === 0) return null;
    return ((price - cost) / price) * 100;
  };

  const getConfidenceBadge = (confidence: string) => {
    const colors = {
      high: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      low: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
      user_edited: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
    };
    return colors[confidence as keyof typeof colors] || colors.medium;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-muted-foreground">Loading confirmed recipes...</div>
      </div>
    );
  }

  if (recipes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <CheckCircle2 className="w-12 h-12 text-muted-foreground mb-4" />
        <h3 className="text-lg font-semibold text-foreground mb-2">No Confirmed Recipes</h3>
        <p className="text-sm text-muted-foreground max-w-md">
          Once you confirm recipes from the "Confirm Recipes" tab, they will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Confirmed Recipes</h2>
          <p className="text-sm text-muted-foreground">
            {recipes.length} {recipes.length === 1 ? 'recipe' : 'recipes'} confirmed
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {recipes.map((recipe) => {
          const totalCost = calculateTotal(recipe.ingredients);
          const baseTotal = calculateBaseTotal(recipe.ingredients);
          const wasteTotal = calculateWasteTotal(recipe.ingredients);
          const margin = calculateMargin(recipe.menu_item_price, totalCost);
          const marginWithoutWaste = calculateMargin(recipe.menu_item_price, baseTotal);

          return (
            <Card key={recipe.menu_item_id} className="p-6">
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-foreground">
                        {recipe.menu_item_name}
                      </h3>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getConfidenceBadge(recipe.confidence)}`}>
                        {recipe.confidence === 'user_edited' ? 'User Edited' : recipe.confidence.toUpperCase()}
                      </span>
                      <CheckCircle2 className="w-5 h-5 text-green-600" />
                    </div>
                    {recipe.estimation_notes && (
                      <p className="text-sm text-muted-foreground">{recipe.estimation_notes}</p>
                    )}
                  </div>

                  {/* Price & Cost Summary */}
                  <div className="text-right space-y-1">
                    {recipe.menu_item_price && (
                      <div className="text-sm text-muted-foreground">
                        Price: <span className="font-semibold text-foreground">${Number(recipe.menu_item_price).toFixed(2)}</span>
                      </div>
                    )}
                    <div className="text-sm text-muted-foreground">
                      Base Cost: <span className="font-medium text-foreground">${baseTotal.toFixed(2)}</span>
                    </div>
                    {wasteTotal > 0 && (
                      <div className="text-sm text-muted-foreground">
                        Waste Cost: <span className="font-medium text-amber-600">+${wasteTotal.toFixed(2)}</span>
                      </div>
                    )}
                    <div className="text-sm text-muted-foreground border-t border-border pt-1">
                      True COGS: <span className="font-semibold text-foreground">${totalCost.toFixed(2)}</span>
                    </div>
                    {margin !== null && (
                      <div className="text-sm">
                        <span className={`font-semibold ${margin >= 70 ? 'text-green-600' : margin >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
                          {margin.toFixed(1)}% margin
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Waste Impact Alert */}
                {wasteTotal > 0.5 && marginWithoutWaste !== null && margin !== null && (
                  <div className="bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 rounded-lg p-3">
                    <div className="flex items-start gap-2">
                      <div className="text-amber-600 dark:text-amber-400 mt-0.5">⚠️</div>
                      <div className="flex-1">
                        <div className="text-sm font-medium text-amber-900 dark:text-amber-100">
                          Hidden Cost Impact
                        </div>
                        <div className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                          Without waste factors: {marginWithoutWaste.toFixed(1)}% margin •
                          With waste: {margin.toFixed(1)}% margin •
                          <span className="font-semibold"> Impact: -{(marginWithoutWaste - margin).toFixed(1)}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Ingredients Table */}
                <div className="border border-border rounded-lg overflow-hidden">
                  <div className={`bg-muted px-4 py-2 grid gap-2 text-xs font-medium text-muted-foreground ${wasteFactorsEnabled ? 'grid-cols-12' : 'grid-cols-10'}`}>
                    <div className="col-span-3">Ingredient</div>
                    <div className="col-span-2">Quantity</div>
                    <div className="col-span-1">Unit</div>
                    <div className="col-span-2">Base Cost</div>
                    {wasteFactorsEnabled && <div className="col-span-2">Waste %</div>}
                    <div className="col-span-2">Total Cost</div>
                  </div>

                  <div className="divide-y divide-border">
                    {recipe.ingredients.map((ingredient, index) => {
                      const baseCost = Number(ingredient.base_cost || ingredient.estimated_cost);
                      const wasteFactor = Number(ingredient.waste_factor || 0);
                      const wastePercent = wasteFactor * 100;
                      const totalIngredientCost = Number(ingredient.estimated_cost);

                      return (
                        <div key={index} className={`px-4 py-3 grid gap-2 items-center ${wasteFactorsEnabled ? 'grid-cols-12' : 'grid-cols-10'}`}>
                          <div className="col-span-3 text-sm text-foreground">
                            {ingredient.name}
                          </div>
                          <div className="col-span-2 text-sm text-muted-foreground">
                            {ingredient.quantity}
                          </div>
                          <div className="col-span-1 text-sm text-muted-foreground">
                            {ingredient.unit}
                          </div>
                          <div className="col-span-2 text-sm text-muted-foreground">
                            ${baseCost.toFixed(2)}
                          </div>
                          {wasteFactorsEnabled && (
                            <div className="col-span-2">
                              {wasteFactor > 0 ? (
                                <span className={`text-sm font-medium ${
                                  wastePercent >= 20 ? 'text-red-600' :
                                  wastePercent >= 10 ? 'text-amber-600' :
                                  'text-green-600'
                                }`}>
                                  {wastePercent.toFixed(0)}%
                                </span>
                              ) : (
                                <span className="text-sm text-muted-foreground">0%</span>
                              )}
                            </div>
                          )}
                          <div className="col-span-2 text-sm font-medium text-foreground">
                            ${totalIngredientCost.toFixed(2)}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Total Row */}
                  <div className={`bg-muted px-4 py-3 grid gap-2 border-t-2 border-border ${wasteFactorsEnabled ? 'grid-cols-12' : 'grid-cols-10'}`}>
                    <div className="col-span-4 text-sm font-semibold text-foreground">
                      Total Cost
                    </div>
                    <div className="col-span-4"></div>
                    {wasteFactorsEnabled && (
                      <div className="col-span-2 text-sm">
                        {wasteTotal > 0 && (
                          <span className="text-xs text-muted-foreground">
                            Avg: {((wasteTotal / baseTotal) * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                    )}
                    <div className="col-span-2 text-sm font-bold text-foreground">
                      ${totalCost.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
