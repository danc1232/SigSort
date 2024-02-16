FROM bash:5.2-alpine3.19
RUN apk add --no-cache bash postgresql-client sed
COPY init-db.sh /init-db.sh
COPY schema.sql /schema.sql
RUN chmod +x /init-db.sh
ENTRYPOINT ["/bin/bash", "/init-db.sh"]