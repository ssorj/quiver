FROM ubuntu
MAINTAINER Justin Ross <jross@apache.org>

RUN apt-get update \
    && apt-get -y install software-properties-common \
    && add-apt-repository -y ppa:qpid/released \
    && apt-get update \
    && apt-get -y install build-essential make openjdk-8-jdk maven nodejs python-numpy python xz-utils

RUN apt-get -y install libqpidmessaging2-dev libqpidtypes1-dev libqpidcommon2-dev \
        libqpid-proton8-dev python-qpid python-qpid-messaging python-qpid-proton

RUN cd /usr/bin && ln -s nodejs node

ADD . /root/quiver
WORKDIR /root/quiver

RUN make install PREFIX=/usr

CMD ["quiver-test"]
