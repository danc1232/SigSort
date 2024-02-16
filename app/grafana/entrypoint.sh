#!/bin/bash

echo "performing environment variable injection"

FILE_PATH=/etc/grafana/provisioning

# Replace vars in datasource config
sed "s/PASSWORD_VAR/${POSTGRES_PW}/g; s/DATABASE_VAR/${POSTGRES_DB}/g" /source.template > $FILE_PATH/datasources/01-postgres-datasource.yaml

echo "completed variable injection, starting from normal entrypoint now"

exec /run.sh "$@"