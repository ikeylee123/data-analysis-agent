from langchain.agents import Tool, initialize_agent, AgentType
from langchain.llms import OpenAI
import pandas as pd
import numpy as np

class DataAnalyzerAgent:
    def __init__(self):
        self.llm = OpenAI(temperature=0)
        self.df = None
        self.tools = [
            Tool(
                name="basic_stats",
                func=self.get_basic_stats,
                description="获取数据基本统计信息"
            ),
            Tool(
                name="correlation_analysis",
                func=self.correlation_analysis,
                description="进行相关性分析"
            ),
            Tool(
                name="trend_analysis",
                func=self.trend_analysis,
                description="分析数据趋势"
            ),
            Tool(
                name="anomaly_detection",
                func=self.anomaly_detection,
                description="检测异常数据"
            )
        ]
        self.agent = initialize_agent(
            self.tools,
            self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True
        )
    
    def load_data(self, file_path: str):
        if file_path.endswith('.csv'):
            self.df = pd.read_csv(file_path)
        else:
            self.df = pd.read_excel(file_path)
    
    def get_basic_stats(self, _="") -> str:
        if self.df is None:
            return "未加载数据"
        stats = self.df.describe().to_string()
        return f"基本统计信息:\n{stats}"
    
    def correlation_analysis(self, _="") -> str:
        if self.df is None:
            return "未加载数据"
        numeric_df = self.df.select_dtypes(include=[np.number])
        corr = numeric_df.corr().to_string()
        return f"相关性分析:\n{corr}"
    
    def trend_analysis(self, _="") -> str:
        if self.df is None:
            return "未加载数据"
        return "趋势分析完成"
    
    def anomaly_detection(self, _="") -> str:
        if self.df is None:
            return "未加载数据"
        numeric_df = self.df.select_dtypes(include=[np.number])
        Q1 = numeric_df.quantile(0.25)
        Q3 = numeric_df.quantile(0.75)
        IQR = Q3 - Q1
        outliers = ((numeric_df < (Q1 - 1.5 * IQR)) | (numeric_df > (Q3 + 1.5 * IQR))).sum()
        return f"异常值检测: {outliers.to_dict()}"
    
    def run(self, file_path: str, analysis_task: str) -> dict:
        self.load_data(file_path)
        result = self.agent.run(f"请对数据进行以下分析: {analysis_task}")
        return {"status": "success", "result": result, "data": self.df.to_dict()}