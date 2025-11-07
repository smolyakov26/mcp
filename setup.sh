#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🛑 Stopping old containers...${NC}"
docker-compose down -v

echo -e "${YELLOW}🏗️ Building containers...${NC}"
docker-compose build --no-cache

echo -e "${YELLOW}🚀 Starting containers...${NC}"
docker-compose up -d

echo ""
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"

# Wait for database
echo -n "Waiting for PostgreSQL..."
for i in {1..30}; do
    if docker-compose exec -T db pg_isready -U user -d appdb > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Wait for Ollama
echo -n "Waiting for Ollama..."
for i in {1..30}; do
    if curl -f http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Wait for MCP server
echo -n "Waiting for MCP server..."
for i in {1..30}; do
    if curl -f http://localhost:3001/health > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Wait for Streamlit UI
echo -n "Waiting for Streamlit UI..."
for i in {1..30}; do
    if curl -f http://localhost:8501 > /dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

echo ""
echo -e "${GREEN}📊 Service status:${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "${GREEN}🔗 Services:${NC}"
echo "   • MCP API Docs:   http://localhost:3001/docs"
echo "   • MCP Health:     http://localhost:3001/health"
echo "   • Ollama API:     http://localhost:11434"
echo "   • PostgreSQL:     localhost:5432"
echo "   • Streamlit UI:   http://localhost:8501"
echo ""
echo -e "${YELLOW}📝 View logs:${NC}"
echo "   docker-compose logs -f mcp-server"
echo "   docker-compose logs -f ui"
echo ""
echo -e "${YELLOW}🧪 Test query via MCP API:${NC}"
echo '   curl -X POST http://localhost:3001/ask \\' 
echo '     -H "Content-Type: application/json" \\' 
echo '     -d '"'"'{"question": "Show me all users"}'"'"''
echo ""
echo -e "${YELLOW}⚠️ Note:${NC} First query may take 1-2 minutes while model initializes"
