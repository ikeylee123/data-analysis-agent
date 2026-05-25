import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # LLM 配置
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # 文件配置
    UPLOAD_DIR = "data/uploads"
    REPORT_DIR = "data/reports"
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50))
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf"}

    # 数据库配置
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data.db")

    # 调试模式
    DEBUG = os.getenv("DEBUG", False)
