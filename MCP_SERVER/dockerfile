FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Expose the default Hugging Face Spaces port
EXPOSE 7860

# Run the FastMCP server
CMD ["python", "app.py"]
