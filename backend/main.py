import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import prd, rules, analysis, health, search, material, wechat_work

os.makedirs(settings.upload_dir, exist_ok=True)

app = FastAPI(title="PRD Knowledge Base", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,    
    allow_methods=["*"],
    allow_headers=["*"],
  )

app.include_router(prd.router)
app.include_router(rules.router)
app.include_router(analysis.router)
app.include_router(health.router)
app.include_router(search.router)
app.include_router(material.router)
app.include_router(wechat_work.router)


@app.get("/api/ping")
def ping():
    return {"status": "ok", "service": "prd-knowledge-base"}
