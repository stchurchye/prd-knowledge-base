import hashlib
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models import User

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# 简单 token 存储（生产环境应用 Redis）
_tokens: dict[str, int] = {}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str = ""


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None
    role: str

    class Config:
        from_attributes = True


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or user.password_hash != _hash_password(req.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已禁用")

    token = secrets.token_hex(32)
    _tokens[token] = user.id

    user.last_login_at = datetime.now()
    db.commit()

    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": user.role,
        }
    }


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = User(
        username=req.username,
        password_hash=_hash_password(req.password),
        display_name=req.display_name or req.username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = secrets.token_hex(32)
    _tokens[token] = user.id

    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        }
    }


@router.get("/me")
def get_me(token: str = "", db: Session = Depends(get_db)):
    user_id = _tokens.get(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "role": user.role,
    }


@router.post("/logout")
def logout(token: str = ""):
    _tokens.pop(token, None)
    return {"status": "ok"}