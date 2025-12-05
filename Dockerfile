FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application files
COPY server.py .
COPY tenant-info/ ./tenant-info/

# Create charts directory
RUN mkdir -p charts

# Expose port
EXPOSE 8000

# Run the server with SSE transport
CMD ["python", "server.py", "--transport", "sse", "--port", "8000"]


