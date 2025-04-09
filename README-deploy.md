# Istruzioni per il Deployment su VPS Contabo

Questo documento fornisce istruzioni dettagliate per il deployment dell'applicazione su un server VPS Contabo utilizzando Docker e docker-compose.

## Prerequisiti

- Un VPS Contabo con sistema operativo Linux (Ubuntu consigliato)
- Docker e docker-compose installati sul server
- Un dominio o indirizzo IP assegnato al server
- Accesso SSH al server

## Installazione di Docker e docker-compose

```bash
# Aggiorna i pacchetti
sudo apt update
sudo apt upgrade -y

# Installa prerequisiti
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Aggiungi la chiave GPG ufficiale di Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

# Aggiungi il repository Docker
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

# Aggiorna i repository
sudo apt update

# Installa Docker
sudo apt install -y docker-ce

# Aggiungi l'utente al gruppo docker
sudo usermod -aG docker ${USER}

# Installa docker-compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.6/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verifica l'installazione
docker --version
docker-compose --version
```

## Preparazione del deployment

1. Copia i file dell'applicazione sul server:

```bash
# Dal tuo computer locale
scp -r /percorso/locale/dell/applicazione user@ip-server:/home/user/territori-app
```

2. Crea un file .env partendo dall'esempio:

```bash
# Sul server
cd /home/user/territori-app
cp .env.example .env
nano .env
```

3. Modifica il file .env con i valori appropriati:
   - Genera un FLASK_SECRET_KEY sicuro (puoi usare `openssl rand -hex 24`)
   - Imposta le credenziali del database
   - Inserisci la tua chiave Google Maps API

## Deployment dell'applicazione

```bash
# Entra nella directory del progetto
cd /home/user/territori-app

# Costruisci e avvia i container
docker-compose up -d --build

# Verifica che i container siano in esecuzione
docker-compose ps
```

## Configurazione del webserver Nginx (opzionale, ma consigliato)

Per esporre l'applicazione su Internet in modo sicuro, è consigliabile configurare Nginx come reverse proxy:

```bash
# Installa Nginx
sudo apt install -y nginx

# Installa Certbot per certificato SSL (HTTPS)
sudo apt install -y certbot python3-certbot-nginx
```

Crea un file di configurazione Nginx:

```bash
sudo nano /etc/nginx/sites-available/territori-app
```

Inserisci la seguente configurazione (sostituisci example.com con il tuo dominio):

```nginx
server {
    listen 80;
    server_name example.com www.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Attiva la configurazione:

```bash
sudo ln -s /etc/nginx/sites-available/territori-app /etc/nginx/sites-enabled/
sudo nginx -t  # Test della configurazione
sudo systemctl restart nginx
```

Ottieni un certificato SSL:

```bash
sudo certbot --nginx -d example.com -d www.example.com
```

## Gestione dell'applicazione

- Visualizza i log: `docker-compose logs -f`
- Riavvia l'applicazione: `docker-compose restart`
- Ferma l'applicazione: `docker-compose down`
- Aggiorna l'applicazione:
  ```bash
  git pull  # Se usi git
  docker-compose down
  docker-compose up -d --build
  ```

## Backup del database

Per eseguire un backup del database:

```bash
docker-compose exec db pg_dump -U postgres -d territori_db > backup-$(date +%Y%m%d).sql
```

## Ripristino del database

Per ripristinare un backup del database:

```bash
cat backup-file.sql | docker-compose exec -T db psql -U postgres -d territori_db
```