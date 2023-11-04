FROM prom/snmp-exporter:latest

ADD --chmod=755 https://github.com/mikefarah/yq/releases/download/v4.35.2/yq_linux_amd64 /usr/bin/yq
ADD snmp-patch.yml /tmp/
RUN yq -i '. *= (load("/tmp/snmp-patch.yml") | .)' /etc/snmp_exporter/snmp.yml
