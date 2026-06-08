#!/bin/bash

echo "Waiting for MySQL to be ready..."
sleep 10

echo "Initializing admin user..."
python init_sql/init_admin.py

echo "Starting FastAPI server..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload