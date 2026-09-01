FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp/.cache \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN adduser --disabled-password --gecos "" appuser

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --no-compile --root-user-action=ignore -r requirements.txt

COPY --chown=appuser:appuser app.py utils.py ./
COPY --chown=appuser:appuser pages/ ./pages/
COPY --chown=appuser:appuser www/ ./www/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=5).read(1)"

CMD ["python", "-m", "shiny", "run", "--host", "0.0.0.0", "--port", "8000", "app.py"]
