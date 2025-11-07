from fastapi import FastAPI, Request
import requests
import psycopg2
import uvicorn
import time

app = FastAPI()
OLLAMA_URL = "http://ollama:11434"
MODEL_NAME = "qwen2.5-coder"

def wait_for_ollama():
    """Wait for Ollama to be ready and pull model if needed"""
    print("Waiting for Ollama to start...")
    for i in range(60):
        try:
            res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if res.status_code == 200:
                print("✅ Ollama is ready!")
                
                # Check if model exists
                models = res.json().get("models", [])
                model_exists = any(MODEL_NAME in m.get("name", "") for m in models)
                
                if not model_exists:
                    print(f"📥 Pulling {MODEL_NAME} model... (this may take a few minutes)")
                    pull_res = requests.post(
                        f"{OLLAMA_URL}/api/pull",
                        json={"name": MODEL_NAME},
                        timeout=600
                    )
                    if pull_res.status_code == 200:
                        print(f"✅ Model {MODEL_NAME} ready!")
                    else:
                        print(f"⚠️ Failed to pull model: {pull_res.text}")
                else:
                    print(f"✅ Model {MODEL_NAME} already available")
                return True
        except Exception as e:
            print(f"Waiting for Ollama... ({i+1}/60)")
            time.sleep(2)
    
    print("❌ Ollama failed to start")
    return False

@app.on_event("startup")
async def startup_event():
    wait_for_ollama()

@app.get("/")
def root():
    return {"message": "MCP Python server running!"}

@app.get("/health")
def health():
    try:
        # Check Ollama
        ollama_res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        ollama_ok = ollama_res.status_code == 200
        
        # Check Database
        conn = psycopg2.connect(host="db", user="user", password="pass", dbname="appdb")
        conn.close()
        db_ok = True
    except:
        ollama_ok = False
        db_ok = False
    
    return {
        "status": "healthy" if (ollama_ok and db_ok) else "unhealthy",
        "ollama": "ok" if ollama_ok else "error",
        "database": "ok" if db_ok else "error"
    }

@app.post("/ask")
async def ask_question(request: Request):
    data = await request.json()
    question = data.get("question")
    if not question:
        return {"error": "Missing 'question' field"}

    prompt = f"""You are a PostgreSQL expert.
Write a valid SQL query to answer this question: "{question}".
Assume there is a table called users(id, name, created_at).
Return only the SQL query, no explanations or extra text."""

    # 1️⃣ Request to Ollama
    try:
        res = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=180
        )
        res.raise_for_status()
        response_data = res.json()
        
        if "response" not in response_data:
            return {"error": f"Unexpected Ollama response: {response_data}"}
            
        sql = response_data["response"].strip()

        # Remove markdown formatting
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        elif sql.startswith("```"):
            sql = sql.replace("```", "").strip()

    except requests.exceptions.RequestException as e:
        return {"error": f"Ollama request failed: {str(e)}. Make sure Ollama is running and the model is pulled."}
    except Exception as e:
        return {"error": f"Error processing Ollama response: {str(e)}"}

    # 2️⃣ Only SELECT queries allowed
    if not sql.lower().startswith("select"):
        return {"error": "Only SELECT queries are allowed", "sql": sql}

    # 3️⃣ Execute SQL in PostgreSQL
    try:
        conn = psycopg2.connect(
            host="db",
            user="user",
            password="pass",
            dbname="appdb"
        )
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