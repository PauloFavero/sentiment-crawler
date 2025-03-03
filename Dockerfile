FROM python:3.11-slim

WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create a virtual environment
RUN poetry config virtualenvs.create false

# Create src directory
RUN mkdir -p /app/src

# Copy source code to the correct location
COPY ./src/ /app/src/

# Install dependencies
RUN poetry install --no-interaction --no-ansi

# Set the command to run the worker
CMD ["python", "app/worker.py"] 