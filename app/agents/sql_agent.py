import os
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from app.database.mysql_client import MySQLClient
from app.vector.qdrant_client import QdrantManager
from dotenv import load_dotenv

load_dotenv()

class SQLAgent:
    def __init__(self):
        model_name = os.getenv("GENERATION_MODEL", "gemma-4-31b-it")
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0,
            max_retries=3
        )
        self.db = MySQLClient()
        self.vector_db = QdrantManager()

    def _clean_sql(self, text):
        match = re.search(r"\[SQL\](.*?)\[/SQL\]", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip().replace("```sql", "").replace("```", "").strip()
        
        text = text.replace("```sql", "").replace("```", "").strip()
        matches = re.findall(r"(SELECT|WITH|INSERT|UPDATE|DELETE).*?;", text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[-1].strip()
        return text

    def run(self, user_query):
        # 1. Retrieval
        tables = self.vector_db.search("table_metadata", user_query)
        table_context = "\n".join([f"- {t['table_name']}: {t['summary']}" for t in tables])
        
        examples = self.vector_db.search("golden_queries", user_query)
        example_context = "\n".join([f"Q: {e['question']}\nSQL: {e['sql']}" for e in examples])
        
        prompt = f"""
You are a MySQL expert for a Wealth Banking system.
DATABASE SCHEMA:
{table_context}

FEW-SHOT EXAMPLES:
{example_context}

USER QUESTION: {user_query}

RULES:
- Respond ONLY with the raw SQL code wrapped in [SQL] tags.
- Example: [SQL] SELECT * FROM users; [/SQL]
- DO NOT explain the query. 
- Use proper joins. Be concise.

SQL:"""

        import time
        max_attempts = 3
        content = None
        
        for attempt in range(max_attempts):
            try:
                response = self.llm.invoke(prompt)
                content = response.content
                # Handle cases where content might be a list of dicts/parts
                if isinstance(content, list):
                    content = "".join([part.get("text", "") if isinstance(part, dict) else str(part) for part in content])
                
                sql = self._clean_sql(content.strip())
                break # Success
            except Exception as e:
                # Catch 500 Internal errors specifically or any LLM failure
                if attempt == max_attempts - 1:
                    return {"results": None, "sql": None, "error": f"LLM Error after {max_attempts} retries: {e}"}
                print(f"LLM API Error (Attempt {attempt+1}): {e}. Retrying in 2s...")
                time.sleep(2)
        
        # 2. Execution & Reflection
        results, error = self.db.execute_query(sql)
        
        if error:
            retry_prompt = f"The following SQL failed: {sql}\nError: {error}\nFix it for: {user_query}\nSQL:"
            try:
                response = self.llm.invoke(retry_prompt)
                sql = self._clean_sql(response.content.strip())
                results, error = self.db.execute_query(sql)
            except Exception as e:
                 return {"results": None, "sql": sql, "error": f"Reflection Error: {e}"}
            
        return {"results": results, "sql": sql, "error": error}
