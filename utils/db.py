import sqlite3
from config import Config

class Database:
    def __init__(self, db_path: str = Config.DATABASE_URL):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path)
            return self.conn
        except Exception as e:
            print(f"数据库连接失败: {str(e)}")
            return None
    
    def close(self):
        if self.conn:
            self.conn.close()
    
    def execute_query(self, query: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            self.conn.commit()
            return cursor.fetchall()
        except Exception as e:
            print(f"查询执行失败: {str(e)}")
            return None