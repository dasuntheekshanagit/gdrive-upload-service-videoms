FROM python:3.11-slim

# Install rclone
RUN apt-get update && apt-get install -y curl unzip && \
    curl https://rclone.org/install.sh | bash && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create a placeholder for rclone config
RUN mkdir -p /root/.config/rclone && touch /root/.config/rclone/rclone.conf

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
