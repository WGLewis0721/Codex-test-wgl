"""FastAPI server for Customer Profile Builder."""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from shared.schemas import HealthResponse
from agent.profile import build_profile, profile_to_markdown
from agent.storage import init_db, save_profile, list_versions, get_profile_version

app = FastAPI(title="Customer Profile API", version="1.0.0")
init_db()


class ProfileFormData(BaseModel):
    customer_id: str = Field(..., min_length=1, max_length=100)
    company: str = Field(..., min_length=1, max_length=200)
    industry: str = Field(default="technology")
    team_size: str = Field(default="1-50")
    current_stack: str = Field(default="", max_length=500)
    pain_points: str = Field(default="", max_length=1000)
    goals: str = Field(default="", max_length=1000)
    compliance: str = Field(default="None", max_length=200)
    budget: str = Field(default="unknown", max_length=100)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", details={"agent": "customer-profile"})


@app.post("/profile")
def create_profile(form_data: ProfileFormData) -> dict:
    profile = build_profile(form_data.model_dump())
    version = save_profile(form_data.customer_id, profile)
    markdown = profile_to_markdown(profile, version)
    return {"profile": profile, "version": version, "markdown": markdown}


@app.get("/profiles/{customer_id}")
def get_profiles(customer_id: str) -> dict:
    versions = list_versions(customer_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"No profiles for customer: {customer_id}")
    return {"customer_id": customer_id, "versions": versions}


@app.get("/profiles/{customer_id}/{version}")
def get_profile(customer_id: str, version: int) -> dict:
    profile = get_profile_version(customer_id, version)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile version not found")
    return profile
