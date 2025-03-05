FROM python:3.10-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Set the PYTHONPATH environment variable
ENV PYTHONPATH=/app

# Don't install requirements here - we'll do it in Modal
# RUN pip install --no-cache-dir -r requirements.txt
# RUN pip freeze

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
