from fastapi import APIRouter, Depends
from sqlalchemy import func as sa_func, desc
from sqlalchemy.orm import Session

from db.database import get_db
from models import Rule, Challenge, AuditLog

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("/overview")
def health_overview(db: Session = Depends(get_db)):
    total_rules = db.query(Rule).count()
    active_rules = db.query(Rule).filter(Rule.status == "active").count()
    challenged_rules = db.query(Rule).filter(Rule.status == "challenged").count()
    deprecated_rules = db.query(Rule).filter(Rule.status == "deprecated").count()
    open_challenges = db.query(Challenge).filter(Challenge.status == "open").count()
    total_hits = db.query(sa_func.sum(Rule.hit_count)).scalar() or 0
    cold_rules = db.query(Rule).filter(Rule.hit_count == 0, Rule.status == "active").count()

    return {
        "total_rules": total_rules,
        "active_rules": active_rules,
        "challenged_rules": challenged_rules,
        "deprecated_rules": deprecated_rules,
        "open_challenges": open_challenges,
        "total_hits": total_hits,
        "cold_rules": cold_rules,
    }


@router.get("/top-hits")
def top_hits(limit: int = 10, db: Session = Depends(get_db)):
    rules = (
        db.query(Rule.id, Rule.rule_text, Rule.category, Rule.hit_count, Rule.last_hit_at)
        .filter(Rule.hit_count > 0)
        .order_by(desc(Rule.hit_count))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "rule_text": r.rule_text[:100],
            "category": r.category,
            "hit_count": r.hit_count,
            "last_hit_at": r.last_hit_at,
        }
        for r in rules
    ]


@router.get("/cold-rules")
def cold_rules(limit: int = 20, db: Session = Depends(get_db)):
    rules = (
        db.query(Rule.id, Rule.rule_text, Rule.category, Rule.domain, Rule.created_at)
        .filter(Rule.hit_count == 0, Rule.status == "active")
        .order_by(Rule.created_at)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "rule_text": r.rule_text[:100],
            "category": r.category,
            "domain": r.domain,
            "created_at": r.created_at,
        }
        for r in rules
    ]


@router.get("/recent-activity")
def recent_activity(limit: int = 20, db: Session = Depends(get_db)):
    logs = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": l.id,
            "rule_id": l.rule_id,
            "actor": l.actor,
            "action": l.action,
            "diff": l.diff,
            "created_at": l.created_at,
        }
        for l in logs
    ]


@router.get("/challenge-stats")
def challenge_stats(db: Session = Depends(get_db)):
    total = db.query(Challenge).count()
    open_count = db.query(Challenge).filter(Challenge.status == "open").count()
    resolved = db.query(Challenge).filter(Challenge.status == "resolved").count()
    rejected = db.query(Challenge).filter(Challenge.status == "rejected").count()
    return {
        "total": total,
        "open": open_count,
        "resolved": resolved,
        "rejected": rejected,
    }
