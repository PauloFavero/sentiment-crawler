FROM python:3.11-slim

WORKDIR /app

# Install poetry and system dependencies
RUN pip install poetry && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create a virtual environment
RUN poetry config virtualenvs.create false

# Create src directory
RUN mkdir -p /app/src

# Copy source code to the correct location
COPY ./src/ /app/src/

# Install dependencies
RUN poetry install --no-interaction --no-ansi || pip install temporalio praw asyncpraw openai tweepy

# Install Google Sheets dependencies explicitly
RUN pip install gspread oauth2client

# Make run script executable
RUN chmod +x /app/src/run_worker.sh

# Set the command to run the worker
CMD ["/app/src/run_worker.sh"] 