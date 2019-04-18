FROM fedora:29

LABEL Name="quiver" \
    Vendor="ssorj/Justin Ross" \
    Version="1.0.1" \
    License="Apache License, Version 2.0"

# Core dependancies
RUN dnf install -y gcc-c++ make java-1.8.0-openjdk-devel maven nodejs numpy python xz && \
     dnf clean all

# Qpid dependancies
RUN dnf install -y qpid-proton-c-devel qpid-cpp-client-devel qpid-proton-cpp-devel python-qpid-messaging python-qpid-proton && \
     dnf clean all

# Quiver
RUN dnf install -y dnf-plugins-core && \
     dnf copr enable -y jross/ssorj && \
     dnf install -y quiver && \
     dnf clean all

# Create a directory for anyone who wants to use vertx
RUN mkdir -p /tmp/vertx-cache

ADD fix-permissions /usr/bin/fix-permissions

# Fix folder permissions
RUN chmod +x /usr/bin/fix-permissions && \
     /usr/bin/fix-permissions /usr/lib/quiver && \
     /usr/bin/fix-permissions /tmp/vertx-cache

CMD ["quiver", "--help"]
