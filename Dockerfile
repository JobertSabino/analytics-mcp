FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastmcp==3.4.3 \
    analytics-mcp==0.6.0

COPY server.py .

EXPOSE 8000

CMD ["python", "server.py"]
