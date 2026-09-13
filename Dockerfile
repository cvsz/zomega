FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Apply vendor security updates so the runtime image does not retain
# fixable HIGH/CRITICAL Debian vulnerabilities from the moving slim tag.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN useradd --system --uid 10001 --create-home zomega
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chown -R zomega:zomega /app
USER zomega
EXPOSE 8000
CMD ["python", "-m", "zomega", "serve"]
