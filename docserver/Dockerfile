# Use an Alpine base image
FROM python:3.12.3-alpine

# Set environment variables for Python and MkDocs
# PYTHONBUFFERED - see the stdout/stderr of the script
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install necessary packages: Caddy and mkdocs
RUN apk add --no-cache \
    caddy \
    && pip install --upgrade pip \
    && pip install mkdocstrings-python mkdocs-material

# Create a working directory
WORKDIR /opt/pipelines

# Copy Caddyfile for Caddy server configuration
COPY Caddyfile /etc/caddy/Caddyfile

# Expose necessary ports
# Do not forget to map ports correctly `docker run -p 8080:8080 <image_name>`
EXPOSE 8080

# Command to run Caddy and MkDocs at the same time
CMD ["sh", "-c", "mkdocs build -d /docs && caddy run -c /etc/caddy/Caddyfile"]
