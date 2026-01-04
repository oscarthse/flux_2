'use client';

import { useState, useEffect } from 'react';
import { api, MenuItemWithEstimate, EstimatedIngredient } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  ChefHat,
  Loader2,
  Plus,
  Trash2,
  Save,
  Sparkles,
  AlertCircle,
  DollarSign
} from 'lucide-react';

interface EditableIngredient extends EstimatedIngredient {
  isEditing?: boolean;
}

export function RecipeConfirmation() {
  const [recipes, setRecipes] = useState<MenuItemWithEstimate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingItems, setEditingItems] = useState<Record<string, EditableIngredient[]>>({});

  useEffect(() => {
    loadRecipes();
  }, []);

  const loadRecipes = async () => {
    setIsLoading(true);
    setError(null);
    const result = await api.recipes.getEstimates();

    if (result.data) {
      setRecipes(result.data.items);
      // Initialize editing state
      const initialEdits: Record<string, EditableIngredient[]> = {};
      result.data.items.forEach(item => {
        initialEdits[item.menu_item_id] = [...item.ingredients];
      });
      setEditingItems(initialEdits);
    } else {
      setError(result.error || 'Failed to load recipe estimates');
    }
    setIsLoading(false);
  };

  const updateIngredient = (menuItemId: string, index: number, field: keyof EditableIngredient, value: any) => {
    setEditingItems(prev => ({
      ...prev,
      [menuItemId]: prev[menuItemId].map((ing, i) =>
        i === index ? { ...ing, [field]: value } : ing
      )
    }));
  };

  const addIngredient = (menuItemId: string) => {
    setEditingItems(prev => ({
      ...prev,
      [menuItemId]: [
        ...prev[menuItemId],
        {
          name: '',
          quantity: 0,
          unit: 'g',
          estimated_cost: 0,
          isEditing: true
        }
      ]
    }));
  };

  const removeIngredient = (menuItemId: string, index: number) => {
    setEditingItems(prev => ({
      ...prev,
      [menuItemId]: prev[menuItemId].filter((_, i) => i !== index)
    }));
  };

  const saveRecipe = async (menuItemId: string) => {
    const ingredients = editingItems[menuItemId];
    const { data, error } = await api.recipes.saveRecipe(menuItemId, ingredients);

    if (data) {
      alert(`Recipe saved successfully! Total cost: $${calculateTotal(ingredients).toFixed(2)}`);
      // Remove the confirmed recipe from the list by reloading
      await loadRecipes();
    } else {
      alert(`Failed to save recipe: ${error || 'Unknown error'}`);
    }
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

  const calculateTotal = (ingredients: EditableIngredient[]) => {
    return ingredients.reduce((sum, ing) => sum + Number(ing.estimated_cost), 0);
  };

  const calculateMargin = (price: number | null, cost: number) => {
    if (!price) return 0;
    return ((price - cost) / price) * 100;
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-destructive">
        <CardContent className="flex items-center gap-3 py-8 text-center">
          <AlertCircle className="w-5 h-5 text-destructive" />
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (recipes.length === 0) {
    return (
      <Card className="border-dashed border-2">
        <CardContent className="text-center py-12">
          <ChefHat className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">No Menu Items Found</h3>
          <p className="text-sm text-muted-foreground">
            Add menu items to your restaurant to see recipe estimates
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {recipes.map((recipe) => {
        const ingredients = editingItems[recipe.menu_item_id] || recipe.ingredients;
        const totalCost = calculateTotal(ingredients);
        const margin = calculateMargin(recipe.menu_item_price, totalCost);

        return (
          <Card key={recipe.menu_item_id} className="overflow-hidden">
            <CardHeader className="bg-muted/30 border-b">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <CardTitle className="text-xl">{recipe.menu_item_name}</CardTitle>
                    <Badge className={getConfidenceBadge(recipe.confidence)}>
                      <Sparkles className="w-3 h-3 mr-1" />
                      {recipe.confidence} confidence
                    </Badge>
                  </div>
                  {recipe.estimation_notes && (
                    <p className="text-sm text-muted-foreground">{recipe.estimation_notes}</p>
                  )}
                </div>
                <div className="text-right">
                  {recipe.menu_item_price && (
                    <div className="text-sm text-muted-foreground mb-1">
                      Menu Price: ${recipe.menu_item_price}
                    </div>
                  )}
                  <div className="text-lg font-bold">
                    Total Cost: ${totalCost.toFixed(2)}
                  </div>
                  {recipe.menu_item_price && (
                    <div className={`text-sm font-medium ${margin < 25 ? 'text-red-600' : margin > 35 ? 'text-green-600' : 'text-yellow-600'}`}>
                      {margin.toFixed(1)}% margin
                    </div>
                  )}
                </div>
              </div>
            </CardHeader>

            <CardContent className="p-6">
              {/* Ingredients Table */}
              <div className="space-y-3 mb-4">
                <div className="grid grid-cols-12 gap-2 text-xs font-medium text-muted-foreground uppercase mb-2">
                  <div className="col-span-4">Ingredient</div>
                  <div className="col-span-2">Quantity</div>
                  <div className="col-span-2">Unit</div>
                  <div className="col-span-2">Cost</div>
                  <div className="col-span-2"></div>
                </div>

                {ingredients.map((ingredient, index) => (
                  <div key={index} className="grid grid-cols-12 gap-2 items-center">
                    <div className="col-span-4">
                      <Input
                        value={ingredient.name}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateIngredient(recipe.menu_item_id, index, 'name', e.target.value)}
                        placeholder="Ingredient name"
                        className="h-9"
                      />
                    </div>
                    <div className="col-span-2">
                      <Input
                        type="number"
                        value={ingredient.quantity}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateIngredient(recipe.menu_item_id, index, 'quantity', parseFloat(e.target.value) || 0)}
                        placeholder="0"
                        className="h-9"
                        step="0.1"
                      />
                    </div>
                    <div className="col-span-2">
                      <Input
                        value={ingredient.unit}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateIngredient(recipe.menu_item_id, index, 'unit', e.target.value)}
                        placeholder="g"
                        className="h-9"
                      />
                    </div>
                    <div className="col-span-2">
                      <div className="relative">
                        <DollarSign className="absolute left-2 top-2 h-5 w-5 text-muted-foreground" />
                        <Input
                          type="number"
                          value={ingredient.estimated_cost}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateIngredient(recipe.menu_item_id, index, 'estimated_cost', parseFloat(e.target.value) || 0)}
                          placeholder="0.00"
                          className="h-9 pl-8"
                          step="0.01"
                        />
                      </div>
                    </div>
                    <div className="col-span-2 flex justify-end">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeIngredient(recipe.menu_item_id, index)}
                        className="h-9 text-destructive hover:text-destructive hover:bg-destructive/10"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Add Ingredient Button */}
              <Button
                variant="outline"
                size="sm"
                onClick={() => addIngredient(recipe.menu_item_id)}
                className="w-full mb-4"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Ingredient
              </Button>

              {/* Save Button */}
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    // Reset to original
                    setEditingItems(prev => ({
                      ...prev,
                      [recipe.menu_item_id]: [...recipe.ingredients]
                    }));
                  }}
                >
                  Reset
                </Button>
                <Button onClick={() => saveRecipe(recipe.menu_item_id)}>
                  <Save className="w-4 h-4 mr-2" />
                  Save Recipe
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
