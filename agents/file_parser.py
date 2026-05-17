from langchain.agents import Tool, initialize_agent, AgentType
from langchain.llms import OpenAI
import pandas as pd
from pathlib import Path
import PyPDF2
from openpyxl import load_workbook

class FileParserAgent:
    def __init__(self):
        self.llm = OpenAI(temperature=0)
        self.tools = [
            Tool(
                name="parse_csv",
                func=self.parse_csv,
                description="解析CSV文件并返回数据框"
            ),
            Tool(
                name="parse_excel",
                func=self.parse_excel,
                description="解析Excel文件并返回数据框"
            ),
            Tool(
                name="parse_pdf",
                func=self.parse_pdf,
                description="解析PDF文件并提取文本内容"
            ),
            Tool(
                name="analyze_structure",
                func=self.analyze_structure,
                description="分析数据结构和字段信息"
            )
        ]
        self.agent = initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )
    
    def parse_csv(self, file_path: str) -> str:
        try:
            df = pd.read_csv(file_path)
            return f"CSV解析成功。数据形状: {df.shape}。列: {list(df.columns)}"
        except Exception as e:
            return f"CSV解析失败: {str(e)}"
    
    def parse_excel(self, file_path: str) -> str:
        try:
            df = pd.read_excel(file_path)
            return f"Excel解析成功。数据形状: {df.shape}。列: {list(df.columns)}"
        except Exception as e:
            return f"Excel解析失败: {str(e)}"
    
    def parse_pdf(self, file_path: str) -> str:
        try:
            text = ""
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text()
            return f"PDF解析成功。提取文本长度: {len(text)}字符"
        except Exception as e:
            return f"PDF解析失败: {str(e)}"
    
    def analyze_structure(self, file_path: str) -> str:
        try:
            df = pd.read_csv(file_path) if file_path.endswith('.csv') else pd.read_excel(file_path)
            info = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": df.dtypes.astype(str).to_dict(),
                "missing": df.isnull().sum().to_dict()
            }
            return str(info)
        except Exception as e:
            return f"结构分析失败: {str(e)}"
    
    def run(self, file_path: str, task: str) -> dict:
        result = self.agent.run(f"请{task}文件: {file_path}")
        return {"status": "success", "result": result}