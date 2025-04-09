FROM python:3.11-slim

WORKDIR /app

# Installa le dipendenze di sistema necessarie (tra cui gdal per geopandas)
RUN apt-get update && apt-get install -y \
    libgdal-dev \
    gdal-bin \
    libgeos-dev \
    libproj-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copia i file dei requisiti e installa le dipendenze Python
COPY deploy_requirements.txt .
RUN pip install --no-cache-dir -r deploy_requirements.txt

# Copia il resto dell'applicazione
COPY . .

# Crea directory per i dati persistenti
RUN mkdir -p /app/instance
VOLUME ["/app/instance"]

# Variabili d'ambiente
ENV FLASK_APP=main.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Porta esposta
EXPOSE 5000

# Avvia l'applicazione con Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "main:app"]