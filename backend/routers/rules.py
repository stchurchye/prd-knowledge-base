from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from db.database import get_db
from models import Rule, Challenge, AuditLog, PRD, rule_sources


def _rule_to_out(rule: Rule, db: Session) -> dict:
    """Convert Rule ORM to dict with source_docs populated."""
    data = RuleOut.model_validate(rule).model_dump()
    # 查询来源文档名称
    source_rows = (
        db.query(PRD.title)
        .join(rule_sources, rule_sources.c.prd_id == PRD.id)
        .filter(rule_sources.c.rule_id == rule.id)
        .all()
    )
    if source_rows:
        data["source_docs"] = [r.title for r in source_rows]
    elif rule.prd_id:
        # 兼容旧数据：从 prd_id 取
        prd = db.query(PRD.title).filter(PRD.id == rule.prd_id).first()
        data["source_docs"] = [prd.title] if prd else []
    return data

router = APIRouter(prefix="/api/rules", tags=["Rules"])


class RuleOut(BaseModel):
    id: int
    prd_id: Optional[int] = None
    domain: Optional[str] = None
    category: Optional[str] = None
    rule_text: str
    structured_logic: Optional[dict] = None
    params: Optional[dict] = None
    involves_roles: Optional[list[str]] = None
    compliance_notes: Optional[list[str]] = None
    source_section: Optional[str] = None
    source_docs: list[str] = []  # 来源文档名称列表
    risk_score: float = 0
    risk_flags: Optional[list[str]] = None
    status: str = "draft"
    hit_count: int = 0
    last_hit_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RuleUpdate(BaseModel):
    rule_text: Optional[str] = None
    category: Optional[str] = None
    domain: Optional[str] = None
    structured_logic: Optional[dict] = None
    params: Optional[dict] = None
    involves_roles: Optional[list[str]] = None
    compliance_notes: Optional[list[str]] = None
    status: Optional[str] = None


class ChallengeCreate(BaseModel):
    challenger: str
    content: str


class ChallengeResolve(BaseModel):
    resolution: str
    status: str = "resolved"


class ChallengeOut(BaseModel):
    id: int
    rule_id: int
    challenger: Optional[str] = None
    content: str
    resolution: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AuditLogOut(BaseModel):
    id: int
    rule_id: Optional[int] = None
    actor: Optional[str] = None
    action: Optional[str] = None
    diff: Optional[dict] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/pending-review")
def pending_review(db: Session = Depends(get_db)):
    """查询需要人工审核的规则：draft 状态的规则。"""
    rules = db.query(Rule).filter(Rule.status == "draft").order_by(Rule.created_at.desc()).all()
    return [_rule_to_out(r, db) for r in rules]


@router.post("/{rule_id}/approve")
def approve_rule(rule_id: int, actor: str = "anonymous", db: Session = Depends(get_db)):
    """审核通过，状态改为 active。"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.status = "active"
    db.add(AuditLog(rule_id=rule.id, actor=actor, action="approve", diff={"from": "draft", "to": "active"}))
    db.commit()
    return {"status": "active", "rule_id": rule.id}


@router.post("/{rule_id}/reject")
def reject_rule(rule_id: int, actor: str = "anonymous", db: Session = Depends(get_db)):
    """审核拒绝，状态改为 deprecated。"""
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.status = "deprecated"
    db.add(AuditLog(rule_id=rule.id, actor=actor, action="reject", diff={"from": "draft", "to": "deprecated"}))
    db.commit()
    return {"status": "deprecated", "rule_id": rule.id}


@router.get("/")
def list_rules(
    domain: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    prd_id: Optional[int] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Rule)
    if domain:
        query = query.filter(Rule.domain == domain)
    if category:
        query = query.filter(Rule.category == category)
    if status:
        query = query.filter(Rule.status == status)
    if prd_id:
        query = query.filter(Rule.prd_id == prd_id)
    if q:
        safe_q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter(Rule.rule_text.ilike(f"%{safe_q}%"))

    total = query.count()
    items = query.order_by(Rule.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": [_rule_to_out(r, db) for r in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.get("/stats")
def rule_stats(db: Session = Depends(get_db)):
    total = db.query(Rule).count()
    by_domain = (
        db.query(Rule.domain, sa_func.count(Rule.id))
        .group_by(Rule.domain)
        .all()
    )
    by_status = (
        db.query(Rule.status, sa_func.count(Rule.id))
        .group_by(Rule.status)
        .all()
    )
    by_category = (
        db.query(Rule.category, sa_func.count(Rule.id))
        .group_by(Rule.category)
        .all()
    )
    return {
        "total": total,
        "by_domain": {d: c for d, c in by_domain if d},
        "by_status": {s: c for s, c in by_status if s},
        "by_category": {cat: c for cat, c in by_category if cat},
    }


@router.get("/{rule_id}")
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _rule_to_out(rule, db)


@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, data: RuleUpdate, actor: str = Query("anonymous"), db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    diff = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        old = getattr(rule, field)
        if old != value:
            diff[field] = {"old": str(old), "new": str(value)}
            setattr(rule, field, value)

    if diff:
        log = AuditLog(rule_id=rule.id, actor=actor, action="update", diff=diff)
        db.add(log)
    db.commit()
    db.refresh(rule)
    return rule


# --- Challenges ---

@router.get("/{rule_id}/challenges", response_model=list[ChallengeOut])
def list_challenges(rule_id: int, db: Session = Depends(get_db)):
    return db.query(Challenge).filter(Challenge.rule_id == rule_id).order_by(Challenge.created_at.desc()).all()


@router.post("/{rule_id}/challenges", response_model=ChallengeOut)
def create_challenge(rule_id: int, data: ChallengeCreate, db: Session = Depends(get_db)):
    rule = db.query(Rule).filter(Rule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    challenge = Challenge(rule_id=rule_id, challenger=data.challenger, content=data.content)
    db.add(challenge)
    rule.status = "challenged"
    log = AuditLog(
        rule_id=rule_id,
        actor=data.challenger,
        action="challenge",
        diff={"content": data.content},
    )
    db.add(log)
    db.commit()
    db.refresh(challenge)
    return challenge


@router.put("/challenges/{challenge_id}/resolve", response_model=ChallengeOut)
def resolve_challenge(challenge_id: int, data: ChallengeResolve, actor: str = Query("anonymous"), db: Session = Depends(get_db)):
    challenge = db.query(Challenge).filter(Challenge.id == challenge_id).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    challenge.resolution = data.resolution
    challenge.status = data.status
    challenge.resolved_at = datetime.now(timezone.utc)

    rule = db.query(Rule).filter(Rule.id == challenge.rule_id).first()
    if rule:
        open_count = db.query(Challenge).filter(
            Challenge.rule_id == rule.id, Challenge.status == "open"
        ).count()
        if open_count <= 1:
            rule.status = "active"

    log = AuditLog(
        rule_id=challenge.rule_id,
        actor=actor,
        action="resolve_challenge",
        diff={"resolution": data.resolution, "status": data.status},
    )
    db.add(log)
    db.commit()
    db.refresh(challenge)
    return challenge


# --- Audit Logs ---

@router.get("/{rule_id}/logs", response_model=list[AuditLogOut])
def list_audit_logs(rule_id: int, db: Session = Depends(get_db)):
    return db.query(AuditLog).filter(AuditLog.rule_id == rule_id).order_by(AuditLog.created_at.desc()).all()
