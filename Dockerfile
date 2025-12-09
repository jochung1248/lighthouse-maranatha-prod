FROM python:3.9-slim-buster

# Set working directory
WORKDIR /app

# Copy only dependency list first for Docker layer caching
COPY requirements.txt .

# Install runtime dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (avoid copying secrets - add .dockerignore for credentials/token)
COPY . .

# Keep logs unbuffered
ENV PYTHONUNBUFFERED=1

# Optional: expose a port if your agent listens on one
# EXPOSE 8080

# Run the agent module (executes ppt_agent/agent.py as a module)
CMD ["python", "-m", "ppt_agent.agent"]