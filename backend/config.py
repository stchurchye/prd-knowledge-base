from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = ""
    # Qwen / 百炼 (阿里云通义千问) - 主要 LLM
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-max"  # 可选: qwen-plus, qwen-turbo

    # Anthropic (可选，已弃用)
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""  # Custom API endpoint

    # Embedding: Voyage AI (可选，优先使用本地模型)
    voyage_api_key: str = ""
    upload_dir: str = "./uploads"
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_allow_methods: list[str] = ["GET", "POST", "PUT", "DELETE"]
    cors_allow_headers: list[str] = ["Content-Type", "Authorization"]

    # Feishu / Lark
    feishu_app_id: str = ""
    feishu_app_secret: str = ""

    # Qwen-VL (通义千问视觉 - 图片识别)
    qwen_vl_model: str = "qwen-vl-max"

    class Config:
        env_file = ".env"


settings = Settings()
