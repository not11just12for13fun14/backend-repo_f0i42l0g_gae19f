"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Domain Schemas for this app ---

class Company(BaseModel):
    name: str = Field(..., description="Company legal name")
    website: Optional[str] = Field(None, description="Company website URL")
    country: Optional[str] = Field(None, description="Country of registration")
    sector: Optional[str] = Field(None, description="Primary industry/sector")
    size: Optional[str] = Field(None, description="Company size (e.g., SME, startup, large)")
    contact_email: Optional[str] = Field(None, description="Primary contact email")
    description: Optional[str] = Field(None, description="Short description of the company and project idea")

class Opportunity(BaseModel):
    title: str
    url: str
    programme: Optional[str] = None
    call_id: Optional[str] = None
    deadline: Optional[str] = None
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None

class InterviewAnswer(BaseModel):
    question_id: str
    answer: str

class Interview(BaseModel):
    company_name: str
    company: Optional[Company] = None
    questions: List[Dict[str, Any]]
    answers: List[InterviewAnswer] = []
    matched_opportunities: List[Opportunity] = []
    fit_score: Optional[float] = None
    evaluation: Optional[str] = None
    created_at: Optional[datetime] = None

class ProposalDraft(BaseModel):
    company_name: str
    opportunity_title: str
    opportunity_url: str
    outline: Dict[str, str]
    research_notes: Optional[str] = None
    created_at: Optional[datetime] = None

# Example schemas kept for reference
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True

# The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
