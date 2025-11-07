from fastapi import FastAPI, Request
import requests
import psycopg2
import uvicorn

app = FastAPI()
OLLAMA_URL = "http://ollama:11434/v1"  # базовый URL v1 Ollama

@app.get("/")
def root():
    return {"message": "MCP Python server running!"}

@app.post("/ask")
async def ask_question(request: Request):
    data = await request.json()
    question = data.get("question")
    if not question:
        return {"error": "Missing 'question' field"}

    prompt = f"""
You are a PostgreSQL expert.
Write a valid SQL query to answer this question: "{question}".
Assume there is a table called users(id, name, created_at).
Return only the SQL query, no explanations or extra text.
"""

    # 1️⃣ Запрос к Ollama
    try:
        res = requests.post(
            f"{OLLAMA_URL}/completions",
            json={
                "model": "qwen2.5-coder",
                "prompt": prompt,
                "max_tokens": 512
            },
            timeout=180
        )
        res.raise_for_status()
        sql = res.json()["completion"].strip()

        # удаляем markdown
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        elif sql.startswith("```"):
            sql = sql.replace("```", "").strip()

    except Exception as e:
        return {"error": f"Ollama request failed: {str(e)}"}

    # 2️⃣ Только SELECT
    if not sql.lower().startswith("select"):
        return {"error": "Only SELECT queries are allowed", "sql": sql}

    # 3️⃣ Выполнение SQL в PostgreSQL
    try:
        conn = psycopg2.connect(host="db", user="user", password="pass", dbname="appdb")
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
        data = [dict(zip(columns, row)) for row in rows]
        return {"question": question, "sql": sql, "data": data}

    except Exception as e:
        return {"error": f"Database query failed: {str(e)}", "sql": sql}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=3001)
