import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LLM配置
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # 文件配置
    UPLOAD_DIR = "data/uploads"
    REPORT_DIR = "data/reports"
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 50))  # MB
    ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.pdf'}
    
    # 数据库配置
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data.db")
    
    # 调试模式
    DEBUG = os.getenv("DEBUG", False)