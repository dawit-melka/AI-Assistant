# Use the official Python 3.10 slim image as the base image
FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV FLASK_PORT=5000

# Set the working directory
WORKDIR /AI-Assistant

# Install Poetry
RUN pip install poetry

# Copy the application code
COPY . /AI-Assistant

# Install dependencies
RUN poetry config virtualenvs.create false && poetry install --no-root

# Run the application
CMD ["gunicorn", "-w", "4", "--bind", "0.0.0.0:$FLASK_PORT", "run:app"]
