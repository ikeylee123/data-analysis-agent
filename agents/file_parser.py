import os

from dotenv import load_dotenv
from langchain.agents import AgentType, Tool, initialize_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from pypdf import PdfReader

from utils.file_handler import FileHandler

load_dotenv()


class FileParserAgent:
    def __init__(self):
        api_key = (
            os.getenv("GOOGLE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or ""
        ).strip()
        self.llm = ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            temperature=0,
            google_api_key=api_key,
        )
        self.tools = [
            Tool(
                name="parse_csv",
                func=self.parse_csv,
                description="解析 CSV 文件并返回数据框摘要",
            ),
            Tool(
                name="parse_excel",
                func=self.parse_excel,
                description="解析 Excel 文件并返回数据框摘要",
            ),
            Tool(
                name="parse_pdf",
                func=self.parse_pdf,
                description="解析 PDF 文件并提取文本内容",
            ),
            Tool(
                name="analyze_structure",
                func=self.analyze_structure,
                description="分析数据结构和字段信息",
            ),
        ]
        self.agent = initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
        )

    def parse_csv(self, file_path: str) -> str:
        try:
            df = FileHandler.read_file(file_path)
            return f"CSV 解析成功。数据形状: {df.shape}。列: {list(df.columns)}"
        except Exception as e:
            return f"CSV 解析失败: {str(e)}"

    def parse_excel(self, file_path: str) -> str:
        try:
            df = FileHandler.read_file(file_path)
            return f"Excel 解析成功。数据形状: {df.shape}。列: {list(df.columns)}"
        except Exception as e:
            return f"Excel 解析失败: {str(e)}"

    def parse_pdf(self, file_path: str) -> str:
        try:
            text = ""
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
            return f"PDF 解析成功。提取文本长度: {len(text)} 字符"
        except Exception as e:
            return f"PDF 解析失败: {str(e)}"

    def analyze_structure(self, file_path: str) -> str:
        try:
            df = FileHandler.read_file(file_path)
            info = {
                "shape": df.shape,
                "columns": list(df.columns),
                "dtypes": df.dtypes.astype(str).to_dict(),
                "missing": df.isnull().sum().to_dict(),
            }
            return str(info)
        except Exception as e:
            return f"结构分析失败: {str(e)}"

    def run(self, file_path: str, task: str) -> dict:
        result = self.agent.run(f"请{task}文件: {file_path}")
        return {"status": "success", "result": result}
