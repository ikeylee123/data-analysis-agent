import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from typing import Dict, List

class ChartGenerator:
    @staticmethod
    def create_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str):
        fig = px.bar(df, x=x_col, y=y_col, title=title)
        return fig
    
    @staticmethod
    def create_line_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str):
        fig = px.line(df, x=x_col, y=y_col, title=title, markers=True)
        return fig
    
    @staticmethod
    def create_scatter_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str):
        fig = px.scatter(df, x=x_col, y=y_col, title=title)
        return fig
    
    @staticmethod
    def create_pie_chart(df: pd.DataFrame, values_col: str, names_col: str, title: str):
        fig = px.pie(df, values=values_col, names=names_col, title=title)
        return fig
    
    @staticmethod
    def create_dashboard(analysis_data: Dict):
        pass