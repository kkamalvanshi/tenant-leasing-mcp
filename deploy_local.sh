#!/bin/bash
# Quick local deployment with public URL using ngrok
# Requires: ngrok installed (brew install ngrok)

echo "🚀 Starting Tenant Leasing MCP Server..."
echo ""

cd /Users/kkamalva/financial_analysis/MCP/kurt-data

# Start the server in background
echo "Starting MCP server on port 8000..."
/Users/kkamalva/Library/Python/3.9/bin/uv run --python 3.10 python server.py --transport sse --port 8000 &
SERVER_PID=$!

sleep 2

echo ""
echo "✅ Server running on http://localhost:8000"
echo ""
echo "To expose publicly, run in another terminal:"
echo "  ngrok http 8000"
echo ""
echo "Press Ctrl+C to stop the server"

# Wait for interrupt
trap "kill $SERVER_PID 2>/dev/null; echo 'Server stopped.'" EXIT
wait $SERVER_PID


