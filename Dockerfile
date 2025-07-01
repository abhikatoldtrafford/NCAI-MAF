# To run only the API code. Further executions can be managed in the bootstrap.sh file. 
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYT1ECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    apt-transport-https \
    ca-certificates \
    gcc \
    libffi-dev \
    python3-poetry \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app


# Copy the poetry.lock and pyproject.toml first to leverage Docker cache
COPY pyproject.toml /app/

COPY . /app

RUN poetry install
RUN poetry lock

EXPOSE 80
EXPOSE 443
EXPOSE 8000

# Set the entry point for the container

CMD ["poetry", "run", "python", "/app/api/enhanced_main.py"]
