"""
SQLAlchemy models for Flux.
"""
# Core entities
from src.models.user import User
from src.models.restaurant import Restaurant
from src.models.data_upload import DataUpload
from src.models.transaction import Transaction, TransactionItem

# Menu
from src.models.menu import MenuCategory, MenuItem

# Ingredients & Recipes
from src.models.ingredient import IngredientCategory, Ingredient, Recipe
from src.models.recipe import (
    StandardRecipe,
    StandardRecipeIngredient,
    MenuItemRecipe,
    IngredientCostHistory,
)

# Inventory
from src.models.inventory import Inventory, InventoryMovement

# Employees & Scheduling
from src.models.employee import (
    EmployeeRole,
    Employee,
    Skill,
    EmployeeSkill,
    ShiftTemplate,
    EmployeeAvailability,
    ScheduledShift,
)

# Forecasting
from src.models.forecast import DemandForecast, StaffingForecast

# Promotions
from src.models.promotion import Promotion, PriceElasticity

# External data
from src.models.external import WeatherData, LocalEvent

# Settings & Audit
from src.models.settings import RestaurantSettings, AlgorithmRun

# Operating Hours
from src.models.operating_hours import OperatingHours, ServicePeriod

# Data Health
from src.models.data_health import DataHealthScore

# Inventory Snapshots
from src.models.inventory import InventorySnapshot

# Token Blacklist
from src.models.token_blacklist import TokenBlacklist


__all__ = [
    # Core
    "User",
    "Restaurant",
    "DataUpload",
    "Transaction",
    "TransactionItem",
    # Menu
    "MenuCategory",
    "MenuItem",
    # Ingredients & Standard Recipes
    "IngredientCategory",
    "Ingredient",
    "Recipe",
    "StandardRecipe",
    "StandardRecipeIngredient",
    "MenuItemRecipe",
    "IngredientCostHistory",
    # Inventory
    "Inventory",
    "InventoryMovement",
    # Employees
    "EmployeeRole",
    "Employee",
    "Skill",
    "EmployeeSkill",
    "ShiftTemplate",
    "EmployeeAvailability",
    "ScheduledShift",
    # Forecasting
    "DemandForecast",
    "StaffingForecast",
    # Promotions
    "Promotion",
    "PriceElasticity",
    # External
    "WeatherData",
    "LocalEvent",
    # Settings
    "RestaurantSettings",
    "AlgorithmRun",
    # Operating Hours
    "OperatingHours",
    "ServicePeriod",
    # Data Health
    "DataHealthScore",
    # Inventory Snapshots
    "InventorySnapshot",
    # Token Blacklist
    "TokenBlacklist",
]
