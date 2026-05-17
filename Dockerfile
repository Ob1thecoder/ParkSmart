FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/pyproject.toml .
RUN pip install --no-cache-dir .

# Copy application code
COPY backend/app/ app/
COPY backend/models/ models/
COPY backend/data_raw/tfnsw_fixtures/ data_raw/tfnsw_fixtures/

# Copy docs (contains KML file for parking signs)
COPY docs/ docs/

# Create directory for persistent data
RUN mkdir -p /data

# Default environment
ENV DB_PATH=/data/parksmart.db
ENV FIXTURES_DIR=data_raw/tfnsw_fixtures

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
