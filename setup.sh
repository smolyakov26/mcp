#!/bin/bash

echo "🛑 Stopping old containers..."
docker-compose down -v

echo "🏗️ Building containers..."
docker-compose build --no-cache

echo "🚀 Starting containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

echo ""
echo "📊 Checking service status..."
docker-compose ps

echo ""
echo "📝 Follow the logs with:"
echo "   docker-compose logs -f mcp-server"
echo ""
echo "✅ Setup complete!"
echo ""
echo "🔗 Services:"
echo "   • FastAPI:    http://localhost:3001"
echo "   • Health:     http://localhost:3001/health"
echo "   • Ollama API: http://localhost:11434"
echo "   • PostgreSQL: localhost:5432"
echo ""
echo "🧪 Test with:"
echo '   curl -X POST http://localhost:3001/ask -H "Content-Type: application/json" -d '"'"'{"question": "Show me all users"}'"'"''
echo ""
echo "⚠️ Note: First request may take 2-3 minutes while Ollama downloads the qwen2.5-coder model (~3GB)"