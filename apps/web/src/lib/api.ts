/**
 * API client for communicating with the Flux backend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ApiResponse<T> {
  data?: T;
  error?: string;
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      // Handle different error formats
      let errorMessage: string;
      if (typeof errorData.detail === 'string') {
        errorMessage = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        // Validation errors from FastAPI
        errorMessage = errorData.detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ');
      } else if (errorData.detail && typeof errorData.detail === 'object') {
        errorMessage = JSON.stringify(errorData.detail);
      } else {
        errorMessage = `HTTP ${response.status}`;
      }
      return { error: errorMessage };
    }

    const data = await response.json();
    return { data };
  } catch (error) {
    return { error: 'Network error' };
  }
}

// Auth endpoints
export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
}

export const api = {
  auth: {
    login: (data: LoginRequest) =>
      request<TokenResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    register: (data: RegisterRequest) =>
      request<TokenResponse>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),

    me: () => request<User>('/api/auth/me'),
  },

  data: {
    uploads: () => request<{ uploads: any[] }>('/api/data/uploads'),
    health: () => request<DataHealthScore>('/api/data/health'),
  },

  settings: {
    getOperatingHours: () => request<WeeklySchedule>('/api/operating-hours'),
    updateOperatingHours: (data: WeeklyScheduleUpdate) =>
      request<WeeklySchedule>('/api/operating-hours', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    getServicePeriods: () => request<ServicePeriodList>('/api/service-periods'),
    createServicePeriod: (data: ServicePeriodCreate) =>
      request<ServicePeriod>('/api/service-periods', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    deleteServicePeriod: (id: string) =>
      request<void>(`/api/service-periods/${id}`, {
        method: 'DELETE',
      }),
    getFeatures: () => request<FeatureSettings>('/api/settings/features'),
    updateFeatures: (settings: FeatureSettings) =>
      request<FeatureSettings>('/api/settings/features', {
        method: 'PUT',
        body: JSON.stringify(settings),
      }),
  },

  promotions: {
    list: (params?: { status?: string; is_exploration?: boolean }) => {
      const searchParams = new URLSearchParams();
      if (params?.status) searchParams.set('status', params.status);
      if (params?.is_exploration !== undefined) searchParams.set('is_exploration', String(params.is_exploration));
      const query = searchParams.toString();
      return request<PromotionsList>(`/api/promotions${query ? `?${query}` : ''}`);
    },
    get: (id: string) => request<Promotion>(`/api/promotions/${id}`),
    update: (id: string, data: PromotionUpdate) =>
      request<Promotion>(`/api/promotions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
    exploreCandidates: () => request<ExploreCandidatesList>('/api/promotions/explore-candidates'),
    estimateElasticity: (menuItemId: string, lookbackDays: number = 180) =>
      request<ElasticityEstimate>(`/api/promotions/elasticity/estimate/${menuItemId}?lookback_days=${lookbackDays}`, {
        method: 'POST',
      }),
    getElasticity: (menuItemId: string) =>
      request<ElasticityEstimate>(`/api/promotions/elasticity/${menuItemId}`),
    inferPromotions: (lookbackDays: number = 90, confidenceThreshold: number = 0.6) =>
      request<PromotionInferenceResult>('/api/promotions/infer-promotions', {
        method: 'POST',
        body: JSON.stringify({ lookback_days: lookbackDays, confidence_threshold: confidenceThreshold }),
      }),
  },

  inventory: {
    listStockouts: (params?: { start_date?: string; end_date?: string }) => {
      const searchParams = new URLSearchParams();
      if (params?.start_date) searchParams.set('start_date', params.start_date);
      if (params?.end_date) searchParams.set('end_date', params.end_date);
      const query = searchParams.toString();
      return request<StockoutListResponse>(`/api/inventory/stockouts${query ? `?${query}` : ''}`);
    },
    detectStockouts: (days: number = 30, save: boolean = false) =>
      request<DetectStockoutsResponse>('/api/inventory/detect-stockouts', {
        method: 'POST',
        body: JSON.stringify({ days_to_analyze: days, save_results: save }),
      }),
    markStockout: (menu_item_id: string, date: string) =>
      request<InventorySnapshot>('/api/inventory/mark-stockout', {
        method: 'POST',
        body: JSON.stringify({ menu_item_id, date }),
      }),
  },

  menu: {
    list: () => request<MenuItemListResponse>('/api/menu-items'),
  },

  recipes: {
    getUnconfirmed: () => request<UnconfirmedItemsResponse>('/api/recipes/menu-items/unconfirmed'),
    getEstimates: () => request<EstimatedRecipesResponse>('/api/recipes/menu-items/estimates'),
    getConfirmed: () => request<EstimatedRecipesResponse>('/api/recipes/menu-items/confirmed'),
    saveRecipe: (menuItemId: string, ingredients: EstimatedIngredient[]) =>
      request<{ status: string; message: string }>(`/api/recipes/menu-items/${menuItemId}/save-recipe`, {
        method: 'POST',
        body: JSON.stringify({ ingredients }),
      }),
    confirmRecipe: (menuItemId: string, recipeId: string) =>
      request<{ status: string }>(`/api/recipes/menu-items/${menuItemId}/confirm-recipe`, {
        method: 'POST',
        body: JSON.stringify({ recipe_id: recipeId }),
      }),
    autoConfirmAll: () => request<{ confirmed_count: number }>('/api/recipes/menu-items/auto-confirm', {
      method: 'POST',
    }),
    getProfitability: () => request<MenuProfitabilityResponse>('/api/recipes/profitability'),
    getItemProfitability: (menuItemId: string) =>
      request<ProfitabilityItemResponse>(`/api/recipes/menu-items/${menuItemId}/profitability`),
  },

  forecast: {
    generate: (itemName: string, daysAhead: number = 7) =>
      request<ForecastPoint[]>('/api/forecast/generate', {
        method: 'POST',
        body: JSON.stringify({ menu_item_name: itemName, days_ahead: daysAhead })
      }),
    get: (itemName: string, daysHistory: number = 30) =>
      request<ForecastResponse>(`/api/forecast/?menu_item_name=${encodeURIComponent(itemName)}&days_history=${daysHistory}`)
  },
};

// Settings types
export interface FeatureSettings {
  waste_factors_enabled: boolean;
}

export interface Recommendation {
  type: 'completeness' | 'consistency' | 'timeliness' | 'accuracy';
  priority: 'high' | 'medium' | 'low';
  title: string;
  description: string;
  action: string;
}

export interface DataHealthScore {
  overall_score: number;
  completeness_score: number;
  consistency_score: number;
  timeliness_score: number;
  accuracy_score: number;
  recommendations: Recommendation[];
  calculated_at: string;
}

// Operating Hours types
export interface DaySchedule {
  day_of_week: number;
  day_name: string;
  open_time: string | null;
  close_time: string | null;
  is_closed: boolean;
}

export interface WeeklySchedule {
  schedule: DaySchedule[];
  source: 'inferred' | 'manual' | 'mixed';
}

export interface WeeklyScheduleUpdate {
  schedule: DaySchedule[];
}

// Service Periods types
export interface ServicePeriod {
  id: string;
  date: string;
  open_time: string | null;
  close_time: string | null;
  is_closed: boolean;
  reason: string | null;
}

export interface ServicePeriodList {
  periods: ServicePeriod[];
  total: number;
}

export interface ServicePeriodCreate {
  date: string;
  open_time?: string | null;
  close_time?: string | null;
  is_closed: boolean;
  reason?: string | null;
}

// Promotion types
export interface Promotion {
  id: string;
  restaurant_id: string;
  menu_item_id: string | null;
  name: string | null;
  discount_type: 'percentage' | 'fixed_amount';
  discount_value: number;
  start_date: string;
  end_date: string;
  status: 'draft' | 'active' | 'completed' | 'cancelled';
  trigger_reason: string | null;
  is_exploration: boolean;
  expected_lift: number | null;
  actual_lift: number | null;
  created_at: string;
}

export interface PromotionsList {
  promotions: Promotion[];
  total: number;
  exploration_count: number;
}

export interface PromotionUpdate {
  name?: string;
  status?: 'draft' | 'active' | 'completed' | 'cancelled';
  actual_lift?: number;
}

export interface ExploreCandidate {
  menu_item_id: string;
  name: string;
  current_price: number;
  sample_size: number;
  confidence: number | null;
  suggested_discount: number;
}

export interface ExploreCandidatesList {
  candidates: ExploreCandidate[];
  total: number;
}

export interface ElasticityEstimate {
  menu_item_id: string;
  menu_item_name: string;
  elasticity: number;
  std_error: number;
  ci_lower: number;
  ci_upper: number;
  sample_size: number;
  confidence: number;
  method: string;
  r_squared?: number;
  f_stat?: number;
  is_weak_instrument?: boolean;
}

export interface PromotionInferenceResult {
  promotions_inferred: number;
  message: string;
}

// Menu Item types
export interface MenuItem {
  id: string;
  name: string;
  price: number;
  category_path: string | null;
  first_seen: string | null;
  last_seen: string | null;
  auto_created: boolean;
  confidence_score: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MenuItemListResponse {
  items: MenuItem[];
  total: number;
  auto_created_count: number;
  needs_review_count: number;
}

// Inventory/Stockout types
export interface InventorySnapshot {
  id: string;
  menu_item_id: string;
  date: string;
  available_qty: number | null;
  stockout_flag: string;
  source: string;
}

export interface StockoutListResponse {
  stockouts: InventorySnapshot[];
}

export interface DetectedStockout {
  menu_item_id: string | null;
  item_name: string;
  detected_date: string;
  confidence: number;
  reason: string;
}

export interface DetectStockoutsResponse {
  detected_stockouts: DetectedStockout[];
  total_detected: number;
  saved_count: number;
}

// Recipe Matching types
export interface RecipeMatch {
  recipe_id: string;
  recipe_name: string;
  cuisine_type: string | null;
  category: string | null;
  prep_time_minutes: number | null;
  confidence_score: number;
  match_method: string;
}

export interface MatchResult {
  menu_item_id: string;
  menu_item_name: string;
  matches: RecipeMatch[];
  auto_confirmed: boolean;
  needs_review: boolean;
}

export interface UnconfirmedItemsResponse {
  items: MatchResult[];
  total: number;
  high_confidence_count: number;
  needs_review_count: number;
}

// Recipe Estimation types
export interface EstimatedIngredient {
  name: string;
  quantity: number;
  unit: string;
  base_cost: number;
  waste_factor: number;
  estimated_cost: number;
  category?: string;
  perishability?: string;
  notes?: string;
}

export interface MenuItemWithEstimate {
  menu_item_id: string;
  menu_item_name: string;
  menu_item_price: number | null;
  ingredients: EstimatedIngredient[];
  total_estimated_cost: number;
  confidence: string;
  estimation_notes?: string;
}

export interface EstimatedRecipesResponse {
  items: MenuItemWithEstimate[];
  total: number;
}

// Profitability types
export interface IngredientCost {
  ingredient_id: string;
  ingredient_name: string;
  quantity: number;
  unit: string;
  unit_cost: number;
  waste_factor: number;
  base_cost: number;
  waste_adjusted_cost: number;
}

export interface ProfitabilityItemResponse {
  menu_item_id: string;
  menu_item_name: string;
  menu_item_price: number;
  total_cogs: number;
  contribution_margin: number;
  margin_percentage: number;
  recipe_source: string;
  ingredient_breakdown: IngredientCost[];
  bcg_quadrant?: string;
}

export interface MenuProfitabilityResponse {
  items: ProfitabilityItemResponse[];
  average_margin: number;
  low_margin_count: number;
}

// Forecast types
export interface ForecastPoint {
  date: string;
  mean: number;
  p10: number;
  p50: number;
  p90: number;
}

export interface HistoryPoint {
  date: string;
  quantity: number;
  stockout: boolean;
}

export interface ForecastResponse {
  history: HistoryPoint[];
  forecast: ForecastPoint[];
}
