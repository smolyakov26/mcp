from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
import uvicorn
import time
import os
import logging
from typing import List, Dict, Any, Optional
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP SQL Query API",
    description="Natural language to SQL query service using Ollama",
    version="1.0.0"
)

# Configuration from environment variables
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "db"),
    "user": os.getenv("DB_USER", "user"),
    "password": os.getenv("DB_PASSWORD", "pass"),
    "dbname": os.getenv("DB_NAME", "appdb")
}

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5-coder:1.5b")
MAX_RETRIES = 3
TIMEOUT = 180

# Pydantic models
class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, description="Natural language question")

class QueryResponse(BaseModel):
    question: str
    sql: str
    data: List[Dict[str, Any]]
    row_count: int

class HealthResponse(BaseModel):
    status: str
    ollama: str
    database: str
    model: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
    sql: Optional[str] = None

# Database connection pool
def get_db_connection():
    """Create a database connection with retry logic"""
    for attempt in range(MAX_RETRIES):
        try:
            conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
            return conn
        except psycopg2.OperationalError as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"Database connection attempt {attempt + 1} failed, retrying...")
                time.sleep(2)
            else:
                raise HTTPException(status_code=503, detail=f"Database unavailable: {str(e)}")

def wait_for_ollama():
    """Wait for Ollama to be ready and ensure model is available"""
    logger.info("Waiting for Ollama to start...")
    
    for i in range(60):
        try:
            res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if res.status_code == 200:
                logger.info("✅ Ollama is ready!")
                
                # Check if model exists
                models = res.json().get("models", [])
                model_exists = any(MODEL_NAME in m.get("name", "") for m in models)
                
                if not model_exists:
                    logger.info(f"📥 Pulling {MODEL_NAME} model... (this may take a few minutes)")
                    try:
                        pull_res = requests.post(
                            f"{OLLAMA_URL}/api/pull",
                            json={"name": MODEL_NAME},
                            stream=True,
                            timeout=600
                        )
                        
                        # Stream the pull response
                        for line in pull_res.iter_lines():
                            if line:
                                logger.info(line.decode('utf-8'))
                        
                        if pull_res.status_code == 200:
                            logger.info(f"✅ Model {MODEL_NAME} ready!")
                        else:
                            logger.error(f"⚠️ Failed to pull model: {pull_res.text}")
                    except Exception as e:
                        logger.error(f"Error pulling model: {str(e)}")
                else:
                    logger.info(f"✅ Model {MODEL_NAME} already available")
                return True
                
        except Exception as e:
            logger.info(f"Waiting for Ollama... ({i+1}/60) - {str(e)}")
            time.sleep(2)
    
    logger.error("❌ Ollama failed to start")
    return False

def clean_sql(sql: str) -> str:
    """Clean and validate SQL query"""
    # Remove markdown code blocks
    sql = re.sub(r'```sql\n?', '', sql)
    sql = re.sub(r'```\n?', '', sql)
    
    # Remove common prefixes
    sql = re.sub(r'^(sql|SQL):\s*', '', sql)
    
    # Strip whitespace
    sql = sql.strip()
    
    # Remove semicolons at the end
    sql = sql.rstrip(';')
    
    return sql

def validate_sql(sql: str) -> tuple[bool, Optional[str]]:
    """Validate SQL query for safety"""
    sql_lower = sql.lower()
    
    # Must be a SELECT query
    if not sql_lower.startswith('select'):
        return False, "Only SELECT queries are allowed"
    
    # Check for dangerous keywords
    dangerous_keywords = [
        'drop', 'delete', 'truncate', 'alter', 'create',
        'insert', 'update', 'grant', 'revoke', 'exec',
        'execute', 'procedure', 'function'
    ]
    
    for keyword in dangerous_keywords:
        if re.search(rf'\b{keyword}\b', sql_lower):
            return False, f"Query contains forbidden keyword: {keyword}"
    
    return True, None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting MCP Server...")
    if not wait_for_ollama():
        logger.error("Failed to initialize Ollama")
    logger.info("MCP Server ready!")

@app.get("/", tags=["General"])
def root():
    """Root endpoint"""
    return {
        "message": "MCP SQL Query API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "ask": "/ask (POST)"
        }
    }

@app.get("/health", response_model=HealthResponse, tags=["General"])
def health():
    """Health check endpoint"""
    ollama_status = "error"
    db_status = "error"
    model_info = None
    
    # Check Ollama
    try:
        ollama_res = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
        if ollama_res.status_code == 200:
            ollama_status = "ok"
            models = ollama_res.json().get("models", [])
            model_exists = any(MODEL_NAME in m.get("name", "") for m in models)
            model_info = MODEL_NAME if model_exists else "not_loaded"
    except Exception as e:
        logger.error(f"Ollama health check failed: {str(e)}")
    
    # Check Database
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        db_status = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
    
    status = "healthy" if (ollama_status == "ok" and db_status == "ok") else "unhealthy"
    
    return {
        "status": status,
        "ollama": ollama_status,
        "database": db_status,
        "model": model_info
    }

@app.post("/ask", response_model=QueryResponse, responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}}, tags=["Query"])
async def ask_question(request: QuestionRequest):
    """
    Convert natural language question to SQL and execute it
    
    - **question**: Natural language question about the database
    """
    question = request.question.strip()
    
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    # Create prompt for Ollama
    prompt = f"""You are a PostgreSQL expert. Write a valid SQL query to answer this question.

Question: "{question}"

Database schema:
- Table: users
  - id (SERIAL PRIMARY KEY)
  - name (VARCHAR(100))
  - created_at (TIMESTAMP)

Rules:
1. Return ONLY the SQL query, no explanations
2. Use standard PostgreSQL syntax
3. Do not include semicolons
4. Do not use markdown formatting
5. Query must start with SELECT

SQL Query:"""

    # Generate SQL with Ollama
    try:
        logger.info(f"Generating SQL for question: {question}")
        res = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9
                }
            },
            timeout=TIMEOUT
        )
        res.raise_for_status()
        response_data = res.json()
        
        if "response" not in response_data:
            raise HTTPException(
                status_code=503,
                detail=f"Unexpected Ollama response format: {response_data}"
            )
        
        raw_sql = response_data["response"]
        sql = clean_sql(raw_sql)
        
        logger.info(f"Generated SQL: {sql}")
        
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=503,
            detail="Ollama request timed out. The model may still be loading."
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama service error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating SQL: {str(e)}"
        )
    
    # Validate SQL
    is_valid, error_msg = validate_sql(sql)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=error_msg,
            headers={"X-Generated-SQL": sql}
        )
    
    # Execute SQL
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            
            # Convert RealDictRow to regular dict
            data = [dict(row) for row in rows]
            
        conn.close()
        
        logger.info(f"Query successful, returned {len(data)} rows")
        
        return {
            "question": question,
            "sql": sql,
            "data": data,
            "row_count": len(data)
        }
        
    except psycopg2.Error as e:
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"SQL execution failed: {str(e)}",
            headers={"X-Generated-SQL": sql}
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Query execution error: {str(e)}",
            headers={"X-Generated-SQL": sql}
        )

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=3001,
        log_level="info"
    )