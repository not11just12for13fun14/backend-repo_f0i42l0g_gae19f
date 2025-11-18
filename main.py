import os
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests

from database import db, create_document, get_documents
from schemas import Company, Opportunity, Interview, InterviewAnswer, ProposalDraft

app = FastAPI(title="AI-Powered EU Funding Vetting API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "EU Funding Vetting API is running"}


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
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# ---- Simple web-scrape helper (non-LLM) ----
EU_PORTAL_SEARCH = "https://cordis.europa.eu/search?q=/contentType/code%3D'project'"


def fetch_sample_opportunities() -> List[Opportunity]:
    """
    Placeholder: returns a few curated example opportunities.
    In production, replace with a robust crawler or official API integration.
    """
    samples = [
        Opportunity(
            title="Horizon Europe: Digital, Industry and Space",
            url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities",
            programme="Horizon Europe",
            summary="Support for research and innovation in digital technologies, advanced manufacturing, and space.",
            keywords=["AI", "manufacturing", "space", "digital"]
        ),
        Opportunity(
            title="EIC Accelerator",
            url="https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en",
            programme="EIC",
            summary="Funding for high-risk, high-impact innovations by startups and SMEs.",
            keywords=["startup", "SME", "deep tech", "innovation"]
        ),
        Opportunity(
            title="LIFE Programme - Environment and Climate Action",
            url="https://cinea.ec.europa.eu/life_en",
            programme="LIFE",
            summary="Projects supporting environment, biodiversity and climate action.",
            keywords=["climate", "environment", "biodiversity"]
        ),
    ]
    return samples


# ---- Interview generation logic (non-LLM heuristic for now) ----
BASE_QUESTIONS = [
    {"id": "q1", "text": "Describe your project in 2-3 sentences."},
    {"id": "q2", "text": "What impact does your project aim to achieve (economic, social, environmental)?"},
    {"id": "q3", "text": "Which TRL (Technology Readiness Level) best describes your solution today?"},
    {"id": "q4", "text": "What is your target market and primary customers?"},
    {"id": "q5", "text": "Do you have a consortium or partners? If yes, who?"},
    {"id": "q6", "text": "What is your company size (startup/SME/large) and country of registration?"},
    {"id": "q7", "text": "What is the estimated budget and timeline?"},
    {"id": "q8", "text": "What prior funding or grants have you received, if any?"},
    {"id": "q9", "text": "List 3-5 keywords that best describe your project."},
    {"id": "q10", "text": "What are the main risks and how will you mitigate them?"},
]


def compute_fit_score(company: Optional[Company], answers: List[InterviewAnswer], opp: Opportunity) -> float:
    score = 0.0
    total = 5.0
    # Heuristics: SME/startup preferred for EIC; climate keywords for LIFE; AI/manufacturing for Horizon
    ans_map = {a.question_id: a.answer.lower() for a in answers}

    # Sector/keywords
    if opp.keywords and any(k.lower() in (ans_map.get("q9", "")) for k in opp.keywords):
        score += 1.5
    # Size/programme alignment
    if company and company.size:
        size = company.size.lower()
        if "eic" in (opp.programme or "").lower() and any(s in size for s in ["sme", "startup"]):
            score += 1.0
    # Impact presence
    if ans_map.get("q2"):
        score += 0.8
    # TRL presence
    if ans_map.get("q3"):
        score += 0.7
    # Budget/timeline presence
    if ans_map.get("q7"):
        score += 1.0

    pct = max(0.0, min(100.0, (score / total) * 100))
    return round(pct, 1)


# ---- API models ----
class StartInterviewRequest(BaseModel):
    company: Optional[Company] = None


class StartInterviewResponse(BaseModel):
    interview_id: str
    questions: List[Dict[str, Any]]
    opportunities: List[Opportunity]


class SubmitAnswersRequest(BaseModel):
    interview_id: str
    answers: List[InterviewAnswer]


class EvaluateResponse(BaseModel):
    fit_score: float
    evaluation: str
    matched: List[Opportunity]


class GenerateProposalRequest(BaseModel):
    interview_id: str
    chosen_opportunity_index: int


# ---- Routes ----
@app.get("/api/opportunities", response_model=List[Opportunity])
def list_opportunities():
    return fetch_sample_opportunities()


@app.post("/api/interview/start", response_model=StartInterviewResponse)
def start_interview(payload: StartInterviewRequest):
    questions = BASE_QUESTIONS
    opportunities = fetch_sample_opportunities()

    interview = Interview(
        company_name=payload.company.name if payload.company else "Unknown",
        company=payload.company,
        questions=questions,
        answers=[],
        matched_opportunities=[],
    )
    interview_id = create_document("interview", interview)

    return StartInterviewResponse(
        interview_id=interview_id,
        questions=questions,
        opportunities=opportunities,
    )


@app.post("/api/interview/submit", response_model=EvaluateResponse)
def submit_answers(payload: SubmitAnswersRequest):
    # Fetch the interview from DB
    docs = get_documents("interview", {"_id": {"$exists": True}})
    if not docs:
        raise HTTPException(status_code=404, detail="Interview not found")

    # Since we don't have ID retrieval helper, re-query latest doc for simplicity
    interview_doc = docs[-1]

    # Compute scores for each sample opportunity
    opportunities = fetch_sample_opportunities()
    company = None
    if interview_doc.get("company"):
        c = interview_doc["company"]
        company = Company(**c)

    answers = [InterviewAnswer(**a) for a in payload.answers]

    scored = []
    for opp in opportunities:
        scored.append((opp, compute_fit_score(company, answers, opp)))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_score = scored[0][1] if scored else 0.0

    evaluation_text = (
        "Strong fit based on keywords and organisation profile." if top_score >= 70 else
        "Moderate fit: promising but gaps identified (consider refining scope)." if top_score >= 40 else
        "Low fit: likely misalignment with programme priorities."
    )

    return EvaluateResponse(
        fit_score=top_score,
        evaluation=evaluation_text,
        matched=[s[0] for s in scored[:3]],
    )


@app.post("/api/proposal/generate", response_model=ProposalDraft)
def generate_proposal(payload: GenerateProposalRequest):
    opportunities = fetch_sample_opportunities()
    if payload.chosen_opportunity_index < 0 or payload.chosen_opportunity_index >= len(opportunities):
        raise HTTPException(status_code=400, detail="Invalid opportunity selection")

    chosen = opportunities[payload.chosen_opportunity_index]

    outline = {
        "Executive Summary": "Concise description of the company, problem, solution, and expected impact.",
        "Objectives": "Specific, measurable objectives aligned with programme priorities.",
        "Innovation": "What is novel vs state-of-the-art; IP position; TRL justification.",
        "Impact": "Economic, social, environmental impacts; EU added value; dissemination.",
        "Implementation": "Work packages, timeline, budget, risk management, consortium roles.",
    }

    draft = ProposalDraft(
        company_name="Interviewed Company",
        opportunity_title=chosen.title,
        opportunity_url=chosen.url,
        outline=outline,
        research_notes=(
            "Initial draft generated. For production, integrate an LLM and live policy search to ground the content "
            "in current calls, work programmes, and evaluator criteria."
        ),
    )
    create_document("proposaldraft", draft)
    return draft


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
