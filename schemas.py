"""
Database Schemas for Life Insurance Comparison App

Each Pydantic model represents a collection in MongoDB. The collection name
is the lowercase of the class name.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class Insurer(BaseModel):
    """Insurer/company profile"""
    name: str = Field(..., description="Insurer display name")
    logo_url: Optional[str] = Field(None, description="Public logo URL")
    rating: Optional[float] = Field(4.5, ge=0, le=5, description="Consumer rating 0-5")
    tagline: Optional[str] = Field(None, description="Short marketing tagline")


class Plan(BaseModel):
    """Individual plan offered by an insurer"""
    insurer_id: str = Field(..., description="Reference to insurer _id as string")
    name: str = Field(..., description="Plan name")
    coverage_amount: int = Field(..., ge=10000, description="Base coverage amount in USD")
    term_years: int = Field(..., ge=5, le=40, description="Term length in years")
    smoker_multiplier: float = Field(1.5, ge=1.0, le=3.0, description="Multiplier for smokers")
    male_factor: float = Field(1.0, ge=0.8, le=1.5, description="Factor applied for males")
    age_band: List[int] = Field([25, 35, 45, 55], description="Boundary ages for rate bands")
    base_rates: List[float] = Field(..., description="Monthly base rate per $100k for each age band")
    features: List[str] = Field(default_factory=list, description="Bulleted features")


class QuoteRequest(BaseModel):
    """User-submitted request used for quoting and stored for analytics"""
    first_name: Optional[str] = None
    age: int = Field(..., ge=18, le=70)
    gender: Literal["male", "female", "other"] = "male"
    smoker: bool = Field(False)
    coverage_amount: int = Field(..., ge=50000, le=2000000)
    term_years: int = Field(..., ge=5, le=40)


class Quote(BaseModel):
    """Persisted quote result snapshot"""
    request_id: str
    insurer_name: str
    plan_name: str
    monthly_premium: float
    coverage_amount: int
    term_years: int
    features: List[str] = []
