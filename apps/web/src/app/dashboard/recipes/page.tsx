'use client';

import { useState } from 'react';
import { RecipeConfirmation, ProfitabilityDashboard, ConfirmedRecipes, MenuPhotoUpload } from '@/features/recipes';
import { ChefHat, DollarSign, CheckCircle2, Camera } from 'lucide-react';

type Tab = 'upload' | 'confirm' | 'confirmed' | 'profitability';

export default function RecipesPage() {
  const [activeTab, setActiveTab] = useState<Tab>('upload');

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-secondary rounded-lg">
          <ChefHat className="w-6 h-6 text-foreground" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Recipes</h1>
          <p className="text-muted-foreground">View confirmed recipes and analyze profitability with waste factors</p>
        </div>
      </div>

      {/* Why This Matters */}
      <div className="bg-card border border-border rounded-xl p-6">
        <h3 className="font-semibold text-foreground mb-2">Unlocking true profitability with waste factors</h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Flux calculates your real cost of goods sold (COGS) including waste factors from trimming,
          spoilage, and prep errors. This reveals hidden costs that impact your margins by 3-6% on average.
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-2 border-b border-border pb-2">
        <button
          onClick={() => setActiveTab('upload')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'upload'
            ? 'bg-secondary text-secondary-foreground'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            }`}
        >
          <Camera className="w-4 h-4 inline mr-2" />
          Upload Menu
        </button>
        <button
          onClick={() => setActiveTab('confirm')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'confirm'
            ? 'bg-secondary text-secondary-foreground'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            }`}
        >
          <ChefHat className="w-4 h-4 inline mr-2" />
          Confirm Recipes
        </button>
        <button
          onClick={() => setActiveTab('confirmed')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'confirmed'
            ? 'bg-secondary text-secondary-foreground'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            }`}
        >
          <CheckCircle2 className="w-4 h-4 inline mr-2" />
          Recipes
        </button>
        <button
          onClick={() => setActiveTab('profitability')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === 'profitability'
            ? 'bg-secondary text-secondary-foreground'
            : 'text-muted-foreground hover:text-foreground hover:bg-muted'
            }`}
        >
          <DollarSign className="w-4 h-4 inline mr-2" />
          Profitability
        </button>
      </div>

      {/* Content */}
      {activeTab === 'upload' && <MenuPhotoUpload onItemsExtracted={() => setActiveTab('confirm')} />}
      {activeTab === 'confirm' && <RecipeConfirmation />}
      {activeTab === 'confirmed' && <ConfirmedRecipes />}
      {activeTab === 'profitability' && <ProfitabilityDashboard />}
    </div>
  );
}
