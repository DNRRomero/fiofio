#!/bin/sh

set -eu

user="$(tr -d '\n' < /run/secrets/rabbitmq_user)"
pass="$(tr -d '\n' < /run/secrets/rabbitmq_password)"

install -d -m 700 /tmp/rabbitmq-secrets
cp /run/secrets/rabbitmq_ca_cert /tmp/rabbitmq-secrets/rabbitmq_ca_cert
cp /run/secrets/rabbitmq_server_cert /tmp/rabbitmq-secrets/rabbitmq_server_cert
cp /run/secrets/rabbitmq_server_key /tmp/rabbitmq-secrets/rabbitmq_server_key
chown -R rabbitmq:rabbitmq /tmp/rabbitmq-secrets
chmod 644 /tmp/rabbitmq-secrets/rabbitmq_ca_cert /tmp/rabbitmq-secrets/rabbitmq_server_cert
chmod 600 /tmp/rabbitmq-secrets/rabbitmq_server_key

cat <<EOF > /tmp/rabbitmq.conf
default_user = $user
default_pass = $pass
default_vhost = /alerts
EOF

cat /etc/rabbitmq/rabbitmq.conf.template >> /tmp/rabbitmq.conf

export RABBITMQ_CONFIG_FILE=/tmp/rabbitmq.conf
exec docker-entrypoint.sh rabbitmq-server
