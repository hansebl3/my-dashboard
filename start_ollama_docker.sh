#!/bin/bash

CONTAINER_NAME="ollama-docker-isolated"
PORT="11435"

echo "Checking if container $CONTAINER_NAME exists..."
if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "Container exists. Starting if stopped..."
    docker start $CONTAINER_NAME
else
    echo "Creating new Ollama container on port $PORT..."
    # Use a volume for persisted models
    docker run -d \
      --restart unless-stopped \
      -p $PORT:11434 \
      -v ollama_docker_isolate:/root/.ollama \
      --name $CONTAINER_NAME \
      ollama/ollama
fi

echo "Waiting for Ollama to initialize..."
sleep 5

echo "Checking status..."
curl -s http://localhost:$PORT/api/tags || echo "Failed to reach Ollama on port $PORT"

echo "Done. Local Docker Ollama is running on port $PORT."
