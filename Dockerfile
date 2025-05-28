FROM python:3.12-alpine

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your script into the image
COPY filterarr.py .

# By default, run your script
ENTRYPOINT ["python", "filterarr.py"]