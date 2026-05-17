import os
import pandas as pd
from pathlib import Path
from config import Config

class FileHandler:
    @staticmethod
    def validate_file(file_path: str) -> bool:
        if not os.path.exists(file_path):
            return False
        ext = Path(file_path).suffix.lower()
        if ext not in Config.ALLOWED_EXTENSIONS:
            return False
        file_size = os.path.getsize(file_path) / (1024 * 1024)
        if file_size > Config.MAX_FILE_SIZE:
            return False
        return True
    
    @staticmethod
    def save_uploaded_file(uploaded_file, upload_dir: str = Config.UPLOAD_DIR) -> str:
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, uploaded_file.name)
        with open(file_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        return file_path
    
    @staticmethod
    def read_file(file_path: str) -> pd.DataFrame:
        ext = Path(file_path).suffix.lower()
        if ext == '.csv':
            return pd.read_csv(file_path)
        elif ext in {'.xlsx', '.xls'}:
            return pd.read_excel(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {ext}")