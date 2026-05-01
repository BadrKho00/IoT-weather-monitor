# Start from a standard Python 3.11 image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements first (so Docker caches this layer)
COPY requirements.txt .

# Install all dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your middleware code
COPY . .

# Tell Cloud Run which port Flask listens on
EXPOSE 8080

# Start the app using gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "60"]