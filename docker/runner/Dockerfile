FROM quay.io/ansible/awx-ee:latest

USER root
RUN dnf install -y patch && dnf clean all
RUN /bin/sh -c "curl -L https://github.com/yaml/pyyaml/commit/3257001bb871711c9f63a6707d423ea389369a55.patch | patch -i - /usr/local/lib64/python3.9/site-packages/yaml/constructor.py"
RUN pip3 install pyone netaddr dnspython
RUN /bin/sh -c "curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash"
USER 1000
