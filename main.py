import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import db, create_document, get_documents
from schemas import Insurer, Plan, QuoteRequest, Quote

app = FastAPI(title="Life Insurance Comparison API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Life Insurance Comparison API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# ---------------------- Seeding Helpers ----------------------
class SeedStatus(BaseModel):
    insurers: int
    plans: int


@app.post("/seed", response_model=SeedStatus)
def seed_data():
    """Seed demo insurers and plans if not present."""
    insurers_count = db.insurer.count_documents({}) if db else 0
    plans_count = db.plan.count_documents({}) if db else 0
    if insurers_count > 0 and plans_count > 0:
        return SeedStatus(insurers=insurers_count, plans=plans_count)

    acme_id = db.insurer.insert_one(Insurer(name="Acme Life", logo_url=None, rating=4.6, tagline="Protect what matters").model_dump()).inserted_id
    shield_id = db.insurer.insert_one(Insurer(name="ShieldGuard", logo_url=None, rating=4.4, tagline="Coverage you can count on").model_dump()).inserted_id
    family_id = db.insurer.insert_one(Insurer(name="FamilyFirst", logo_url=None, rating=4.7, tagline="For the ones you love").model_dump()).inserted_id

    plans: List[Plan] = [
        Plan(
            insurer_id=str(acme_id),
            name="Term Secure",
            coverage_amount=250000,
            term_years=20,
            smoker_multiplier=1.7,
            male_factor=1.05,
            age_band=[25, 35, 45, 55],
            base_rates=[12.0, 18.0, 29.0, 48.0],
            features=["Accelerated benefits", "Level premiums", "Convertible"]
        ),
        Plan(
            insurer_id=str(shield_id),
            name="Guardian Term",
            coverage_amount=500000,
            term_years=30,
            smoker_multiplier=1.8,
            male_factor=1.03,
            age_band=[25, 35, 45, 55],
            base_rates=[15.0, 22.0, 36.0, 60.0],
            features=["Online application", "Living benefits", "Critical illness rider"]
        ),
        Plan(
            insurer_id=str(family_id),
            name="Family Promise",
            coverage_amount=300000,
            term_years=20,
            smoker_multiplier=1.6,
            male_factor=1.02,
            age_band=[25, 35, 45, 55],
            base_rates=[13.0, 19.5, 31.0, 50.0],
            features=["Child rider", "Waiver of premium", "No exam up to $250k"]
        ),
    ]

    for p in plans:
        db.plan.insert_one(p.model_dump())

    return SeedStatus(
        insurers=db.insurer.count_documents({}),
        plans=db.plan.count_documents({})
    )


# ---------------------- Quoting Logic ----------------------

def premium_from_plan(plan: Plan, req: QuoteRequest) -> float:
    """Compute approximate monthly premium for a given plan and request.
    Uses base rate per $100k by age band, adjusted for gender and smoker.
    """
    bands = plan.age_band
    rates = plan.base_rates
    idx = 0
    for i, b in enumerate(bands):
        if req.age >= b:
            idx = i
    idx = min(idx, len(rates) - 1)

    per_100k = rates[idx]
    per_100k *= plan.male_factor if req.gender == "male" else 1.0
    per_100k *= plan.smoker_multiplier if req.smoker else 1.0

    units = max(1, round(req.coverage_amount / 100000))
    monthly = per_100k * units
    term_adj = 1.0 + max(0, (req.term_years - plan.term_years)) * 0.01
    monthly *= term_adj
    return round(float(monthly), 2)


@app.post("/quote", response_model=List[Quote])
def get_quote(request: QuoteRequest):
    """Return ranked quotes from available plans."""
    # Ensure data exists
    if db.insurer.count_documents({}) == 0 or db.plan.count_documents({}) == 0:
        seed_data()

    # Build plan models safely (strip _id and unknown keys)
    plans_raw = list(db.plan.find({}))
    keys = [
        "insurer_id",
        "name",
        "coverage_amount",
        "term_years",
        "smoker_multiplier",
        "male_factor",
        "age_band",
        "base_rates",
        "features",
    ]
    plans: List[Plan] = []
    for p in plans_raw:
        clean = {k: p[k] for k in keys if k in p}
        plans.append(Plan(**clean))

    insurers_by_id = {str(i["_id"]): i for i in db.insurer.find({})}

    request_id = create_document("quoterequest", request)

    quotes: List[Quote] = []
    for p in plans:
        premium = premium_from_plan(p, request)
        insurer = insurers_by_id.get(p.insurer_id)
        if not insurer:
            continue
        q = Quote(
            request_id=request_id,
            insurer_name=insurer.get("name", "Insurer"),
            plan_name=p.name,
            monthly_premium=premium,
            coverage_amount=request.coverage_amount,
            term_years=request.term_years,
            features=p.features,
        )
        quotes.append(q)

    quotes.sort(key=lambda x: x.monthly_premium)
    for q in quotes:
        create_document("quote", q)

    return quotes


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
