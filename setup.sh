#!/bin/bash

echo "Stopping old containers..."
docker-compose down

echo "Building containers..."
docker-compose build

echo "Starting containers..."
docker-compose up -d

echo "✅ Setup complete!"
echo "FastAPI available at http://localhost:3001/ask"
echo "Ollama API available at http://localhost:11434"
echo "При первом запросе Ollama сама загрузит модель qwen2.5-coder"
