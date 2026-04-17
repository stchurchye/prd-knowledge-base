from sqlalchemy import Column, Integer, String, Text, DateTime, func
from sqlalchemy import ForeignKey

from db.database import Base


class WechatWorkMessage(Base):
    """企业微信机器人消息"""
    __tablename__ = "wechat_work_messages"

    id = Column(Integer, primary_key=True)
    msg_id = Column(String(100), unique=True, index=True)

    # 消息内容
    msg_type = Column(String(30))  # image, text, file
    content = Column(Text)
    media_url = Column(String(500))

    # 发送者信息
    sender_id = Column(String(100))
    sender_name = Column(String(100))
    chat_id = Column(String(100))

    # 处理状态
    status = Column(String(20), default="received")  # received, processing, processed, failed
    material_id = Column(Integer, ForeignKey("materials.id"))

    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime)