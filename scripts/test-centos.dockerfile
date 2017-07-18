FROM centos
MAINTAINER Justin Ross <jross@apache.org>

RUN yum -y update && yum clean all

RUN yum -y install java-1.8.0-openjdk nodejs numpy python python-qpid-messaging python-qpid-proton \
    qpid-cpp-client qpid-proton-c qpid-proton-cpp xz gcc-c++ java-1.8.0-openjdk-devel maven make \
    qpid-cpp-client-devel qpid-proton-c-devel qpid-proton-cpp-devel \
    && yum clean all 

ADD . /root/qtools
WORKDIR /root/qtools

RUN make install PREFIX=/usr

CMD ["quiver-test"]
