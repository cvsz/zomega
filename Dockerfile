# Official Docker Hub multi-platform index digest verified 2026-10-26.
# Refresh this digest only through a reviewed base-image update and exact-head image scan.
FROM python:3.12.15-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && mkdir -p /usr/share/zomega \
    && dpkg-query -W -f='${binary:Package}\t${Version}\n' | sort > /usr/share/zomega/os-packages.tsv \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --uid 10001 --create-home zomega
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chown -R zomega:zomega /app
USER zomega
EXPOSE 8000
CMD ["python", "-m", "zomega", "serve"]
