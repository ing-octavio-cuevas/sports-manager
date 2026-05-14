#!/bin/bash
# Ejecutar en la EC2 (Amazon Linux 2): sudo bash setup-nginx-ssl.sh
# Prerequisito: el dominio api.tornealo-sports-api.com ya debe apuntar a esta IP

DOMAIN="tornealo-sports-api.com"
BACKEND_PORT=8000

echo "=== 1. Instalando Nginx y Certbot ==="
amazon-linux-extras install nginx1 -y 2>/dev/null || yum install -y nginx
yum install -y certbot python3-certbot-nginx

echo "=== 2. Configurando Nginx como reverse proxy ==="
cat > /etc/nginx/conf.d/$DOMAIN.conf <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$BACKEND_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # CORS headers
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS" always;
        add_header Access-Control-Allow-Headers "Authorization, Content-Type" always;

        if (\$request_method = OPTIONS) {
            return 204;
        }
    }

    client_max_body_size 10M;
}
EOF

systemctl enable nginx
systemctl start nginx
nginx -t && systemctl reload nginx

echo "=== 3. Obteniendo certificado SSL con Let's Encrypt ==="
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN --redirect

echo "=== 4. Configurando renovación automática ==="
echo "0 0,12 * * * root certbot renew --quiet" > /etc/cron.d/certbot-renew

echo ""
echo "=== Listo! ==="
echo "Tu API ahora está disponible en: https://$DOMAIN"
echo "El certificado se renueva automáticamente cada 12 horas."
