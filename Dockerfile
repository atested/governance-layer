FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash coreutils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r mcp/requirements.txt

RUN mkdir -p /data/LOGS /data/TOOL_EVENTS && \
    chmod 700 /data /data/LOGS /data/TOOL_EVENTS

ENV GOV_RUNTIME_DIR=/data
ENV GOV_SIGNING_DEV_MODE=1
ENV GOVMCP_HOST=0.0.0.0
ENV GOVMCP_PORT=8080
ENV GOVMCP_STREAMABLE_HTTP_PATH=/mcp
ENV GOVMCP_REMOTE_AUTH_MODE=bearer
ENV GOVMCP_LOG_LEVEL=INFO

EXPOSE 8080

CMD ["python3", "mcp/remote_deploy.py"]
