FROM fedora:25

LABEL Name="quiver" \
    Vendor="ssorj/Justin Ross" \
    Version="1.0.0" \
    License="Apache License, Version 2.0"

# Core dependancies
RUN dnf install -y gcc-c++ make java-1.8.0-openjdk-devel maven nodejs numpy python xz && \
     dnf clean all

# QPid dependancies
RUN dnf install -y qpid-proton-c-devel qpid-cpp-client-devel qpid-proton-cpp-devel python-qpid-messaging python-qpid-proton && \
     dnf clean all

# quiver
RUN curl https://copr.fedorainfracloud.org/coprs/jross/ssorj/repo/epel-7/jross-ssorj-epel-7.repo -o /etc/yum.repos.d/jross-ssorj-epel-7.repo && \
     dnf install -y quiver && \
     dnf clean all

CMD ["quiver", "--help"]
