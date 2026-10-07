# 1. Start from an official image that already has Python 3.11 installed.
#    "slim" = a smaller version without extras we don't need.
FROM python:3.11-slim

# 2. Inside the container, work in a folder called /app.
WORKDIR /app

# 3. Copy only the list of packages first, then install them.
#    Docker caches this step, so packages are only reinstalled when requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of the project code in.
COPY . .

# 5. Note that the app listens on port 8000 (documentation for people and tools).
EXPOSE 8000

# 6. The command that runs when the container starts.
#    --host 0.0.0.0 lets connections in from outside the container.
#    Hosting sites like Render pick the port and pass it in as $PORT; otherwise we use 8000.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
