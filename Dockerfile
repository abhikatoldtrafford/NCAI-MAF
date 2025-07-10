# To run only the API code. Further executions can be managed in the bootstrap.sh file. 
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    apt-transport-https \
    ca-certificates \
    git \
    gcc \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /app


# Install uv
RUN pip install --upgrade pip && pip install uv

# Copy project files
COPY pyproject.toml /app/
COPY . /app

ARG GITHUB_TOKEN
ENV GITHUB_TOKEN=$GITHUB_TOKEN

# Set up .netrc for GitHub authentication
RUN set -e && \
    if [ -n "$GITHUB_TOKEN" ]; then \
      echo 'import os;from pathlib import Path;import stat;token=os.getenv("GITHUB_TOKEN");p=Path.home()/".netrc";print(p);p.write_text(f"""machine github.com\nlogin {token}\npassword x-oauth-basic\n""");p.chmod(stat.S_IRUSR | stat.S_IWUSR)' > /app/write_netrc.py && \
      python /app/write_netrc.py && \
      rm /app/write_netrc.py && \
      chmod 600 ~/.netrc; \
    else \
      echo "No GitHub token provided, skipping .netrc setup"; \
    fi

# Use uv to install dependencies and the package
RUN uv pip install --system -e .[dev]

EXPOSE 80
EXPOSE 443
EXPOSE 8000

# Clean up .netrc for security
RUN echo ' ' > ~/.netrc

# Set the entry point for the container
CMD ["python", "/app/api/enhanced_main.py"]
