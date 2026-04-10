#!/usr/bin/env sh

set -eu

if [ -f secrets/rabbitmq_ca_cert.pem ] && [ -f secrets/rabbitmq_server_key.pem ] && [ -f secrets/rabbitmq_server_cert.pem ]; then
  exit 0
fi

openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
  -subj "/CN=fiofio-rabbitmq-dev-ca" \
  -keyout secrets/rabbitmq_ca_key.pem \
  -out secrets/rabbitmq_ca_cert.pem

cat <<'EOF' > secrets/rabbitmq_server_ext.cnf
subjectAltName=DNS:rabbitmq
extendedKeyUsage=serverAuth
EOF

openssl req -nodes -newkey rsa:2048 \
  -subj "/CN=rabbitmq" \
  -keyout secrets/rabbitmq_server_key.pem \
  -out secrets/rabbitmq_server.csr

openssl x509 -req -in secrets/rabbitmq_server.csr \
  -CA secrets/rabbitmq_ca_cert.pem \
  -CAkey secrets/rabbitmq_ca_key.pem \
  -CAcreateserial \
  -days 3650 \
  -extfile secrets/rabbitmq_server_ext.cnf \
  -out secrets/rabbitmq_server_cert.pem

rm -f secrets/rabbitmq_server.csr secrets/rabbitmq_ca_cert.srl secrets/rabbitmq_server_ext.cnf
