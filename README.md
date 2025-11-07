# Project Overview

This project sets up a local development environment with Docker
Compose, including: - PostgreSQL database with initialization scripts -
Ollama AI model server - Custom FastAPI-based MCP server that generates
SQL via Ollama and executes it safely

------------------------------------------------------------------------

## 📦 Services

### **1. PostgreSQL (db)**

-   Runs official `postgres:16` image
-   Exposes port **5432**
-   Initializes database using SQL scripts from `db-init/`
-   Includes a healthcheck to ensure readiness before dependent services
    start

### **2. Ollama (ollama)**

-   Runs `ollama/ollama:latest`
-   Exposes port **11434**
-   Stores downloaded models in a Docker volume

### **3. MCP Server (FastAPI)**

-   Built from `mcp/Dockerfile`
-   Depends on the database service being healthy
-   Exposes port **3001**
-   On startup automatically:
    -   Waits for Ollama
    -   Ensures model `qwen2.5-coder` is pulled

------------------------------------------------------------------------

## 🚀 Setup Instructions

Run the setup script:

``` bash
./setup.sh
```

This will: 1. Build 2.
Start services in the background 3. Wait briefly and show service status

------------------------------------------------------------------------

## 🔗 Service URLs

-   **MCP API Root:** http://localhost:3001
-   **Health Check:** http://localhost:3001/health
-   **Ollama API:** http://localhost:11434
-   **PostgreSQL:** localhost:5432

------------------------------------------------------------------------

## 🧪 Example Test Request

``` bash
curl -X POST http://localhost:3001/ask   -H "Content-Type: application/json"   -d '{"question": "Show me all users"}'
```

------------------------------------------------------------------------

## 📁 Important Files

### **docker-compose.yaml**

Defines all services, volumes, networking, and dependencies.

### **setup.sh**

Automates rebuild + startup + health info.

### **db-init/init.sql**

Creates a `users` table and inserts sample users (Alice, Bob, Charlie).

### **mcp/Dockerfile**

Minimal Python image with installed dependencies.

### **mcp/server.py**

FastAPI server that: - Waits for Ollama and ensures the required model
is downloaded - Exposes an `/ask` endpoint that: - Converts user
questions to SQL - Ensures only `SELECT` queries are allowed - Executes
SQL on PostgreSQL and returns JSON results

------------------------------------------------------------------------

## ✅ Features

-   Safe SQL execution (SELECT-only)
-   Automated model pulling
-   Automatic database initialization
-   Health endpoint verifying DB + Ollama

------------------------------------------------------------------------

## 🛠️ Future Enhancements

-   Add logging middleware
-   Support additional tables or schemas
-   Allow streaming responses from Ollama

------------------------------------------------------------------------

