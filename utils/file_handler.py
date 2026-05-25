import os
from pathlib import Path

import pandas as pd

from config import Config


class FileHandler:
    CSV_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin1")

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
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return file_path

    @staticmethod
    def read_file(file_path: str) -> pd.DataFrame:
        ext = Path(file_path).suffix.lower()
        if ext == ".csv":
            for encoding in FileHandler.CSV_ENCODINGS:
                try:
                    return pd.read_csv(file_path, encoding=encoding)
                except UnicodeDecodeError:
                    continue
            return pd.read_csv(file_path, encoding="latin1", encoding_errors="replace")
        if ext in {".xlsx", ".xls"}:
            return pd.read_excel(file_path)
        raise ValueError(f"不支持的文件格式: {ext}")
