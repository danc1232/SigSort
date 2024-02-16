FROM grafana/grafana-oss
COPY source.template /source.template
COPY entrypoint.sh /entrypoint.sh
RUN mkdir -p /etc/grafana/provisioning/datasources
RUN chmod 777 /etc/grafana/provisioning/datasources
ENTRYPOINT ["/entrypoint.sh"]
