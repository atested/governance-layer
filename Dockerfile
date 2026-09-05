FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash coreutils && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --system atested && \
    adduser --system --ingroup atested --home /home/atested atested

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r mcp/requirements.txt

RUN mkdir -p /data/LOGS /data/TOOL_EVENTS && \
    chown -R atested:atested /data && \
    chmod 700 /data /data/LOGS /data/TOOL_EVENTS

ENV GOV_RUNTIME_DIR=/data
ENV ATESTED_RUNTIME_CONTEXT=production
ENV ATESTED_GOVERNANCE_CAPACITY=32
ENV GOVMCP_HOST=0.0.0.0
ENV GOVMCP_PORT=8080
ENV GOVMCP_STREAMABLE_HTTP_PATH=/mcp
ENV GOVMCP_REMOTE_AUTH_MODE=bearer
ENV GOVMCP_LOG_LEVEL=INFO

EXPOSE 8080

USER atested

CMD ["python3", "mcp/remote_deploy.py"]
