import json
import logging
import hashlib
import time
from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session

from config import settings
from db.database import get_db
from models import WechatWorkMessage, Material, Rule
from models.rule_source import rule_sources
from sqlalchemy import insert as sa_insert

router = APIRouter(prefix="/api/wechat-work", tags=["WechatWork"])
logger = logging.getLogger(__name__)


@router.post("/webhook")
async def wechat_work_webhook(request: Request, db: Session = Depends(get_db)):
    """接收企业微信机器人消息"""
    body = await request.body()

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    msg_type = data.get("MsgType")
    msg_id = data.get("MsgId")

    logger.info("收到企微消息: msg_type=%s, msg_id=%s", msg_type, msg_id)

    # 检查是否已处理过
    existing = db.query(WechatWorkMessage).filter(WechatWorkMessage.msg_id == msg_id).first()
    if existing:
        return {"status": "already_processed", "msg_id": msg_id}

    # 处理图片消息
    if msg_type == "image":
        return await _handle_image_message(data, db)

    # 其他消息类型暂不处理
    msg = WechatWorkMessage(
        msg_id=msg_id,
        msg_type=msg_type,
        content=data.get("Content", ""),
        sender_id=data.get("FromUserId", ""),
        sender_name=data.get("FromUserName", ""),
        chat_id=data.get("ChatId", ""),
        status="ignored"
    )
    db.add(msg)
    db.commit()

    return {"status": "ignored", "msg_type": msg_type}


async def _handle_image_message(data: dict, db: Session) -> dict:
    """处理图片消息"""
    msg_id = data.get("MsgId")
    image_url = data.get("Image", {}).get("URL", "")
    sender_id = data.get("FromUserId", "")
    sender_name = data.get("FromUserName", "未知用户")
    chat_id = data.get("ChatId", "")

    if not image_url:
        raise HTTPException(status_code=400, detail="图片 URL 缺失")

    # 记录消息
    msg = WechatWorkMessage(
        msg_id=msg_id,
        msg_type="image",
        media_url=image_url,
        sender_id=sender_id,
        sender_name=sender_name,
        chat_id=chat_id,
        status="received"
    )
    db.add(msg)
    db.commit()

    # 异步处理图片
    result = await _process_wechat_image(msg, image_url, sender_name, db)

    return result


async def _process_wechat_image(msg: WechatWorkMessage, image_url: str, sender_name: str, db: Session) -> dict:
    """处理企微图片：下载 → 提取规则 → 生成 Wiki"""
    import httpx
    import os
    from datetime import datetime

    msg.status = "processing"
    db.commit()

    start_time = time.time()

    try:
        # 1. 下载图片
        image_dir = os.path.join(settings.upload_dir, "wechat_work")
        os.makedirs(image_dir, exist_ok=True)

        image_path = os.path.join(image_dir, f"{msg.msg_id}.jpg")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                raise RuntimeError(f"下载图片失败: HTTP {resp.status_code}")
            with open(image_path, "wb") as f:
                f.write(resp.content)

        # 2. 创建 Material 记录
        material = Material(
            title=f"企微图片-{sender_name}-{datetime.now().strftime('%Y%m%d_%H%M')}",
            filename=f"{msg.msg_id}.jpg",
            file_hash=hashlib.md5(resp.content).hexdigest(),
            material_type="image",
            doc_type="prd",
            source_channel="wechat_work",
            raw_image_path=image_path,
            status="processing"
        )
        db.add(material)
        db.commit()
        db.refresh(material)

        # 3. 使用 Qwen-VL 提取规则
        from extractors.vision_extractor import extract_from_image
        rules_data = await extract_from_image(image_path, material.title, "qwen")

        # 4. 保存规则
        created_rules = []
        for rd in rules_data:
            rule = Rule(
                material_id=material.id,
                domain=rd.get("domain"),
                category=rd.get("category"),
                rule_text=rd["rule_text"],
                source_section=rd.get("source_section", "企微图片"),
                status="draft",
                confidence=rd.get("confidence", 0.6)
            )
            db.add(rule)
            db.flush()
            created_rules.append(rule)

        # 5. 向量化
        if created_rules:
            from extractors.embedder import get_embeddings_batch, _build_rule_text
            embeddings = await get_embeddings_batch([_build_rule_text(r) for r in created_rules])
            for rule, emb in zip(created_rules, embeddings):
                rule.embedding = emb

        # 6. 更新状态
        elapsed = round(time.time() - start_time, 2)
        material.status = "extracted"
        material.rules_count = len(created_rules)
        material.process_elapsed = elapsed
        material.vision_provider = "qwen"

        msg.status = "processed"
        msg.material_id = material.id
        msg.processed_at = datetime.now()

        db.commit()

        logger.info("企微图片处理完成: %d 条规则, %.2fs", len(created_rules), elapsed)

        return {
            "status": "processed",
            "msg_id": msg.msg_id,
            "material_id": material.id,
            "rules_count": len(created_rules),
            "elapsed": elapsed,
            "sender": sender_name
        }

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        msg.status = "failed"
        db.commit()

        logger.error("企微图片处理失败: %s", e)

        return {
            "status": "failed",
            "msg_id": msg.msg_id,
            "error": str(e)[:200]
        }


@router.get("/messages")
def list_wechat_messages(status: str = "", limit: int = 50, db: Session = Depends(get_db)):
    """查询企微消息列表"""
    query = db.query(WechatWorkMessage)
    if status:
        query = query.filter(WechatWorkMessage.status == status)
    return query.order_by(WechatWorkMessage.created_at.desc()).limit(limit).all()