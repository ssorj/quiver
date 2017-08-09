#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

FROM ubuntu
MAINTAINER Justin Ross <jross@apache.org>

RUN apt-get -qq update && apt-get -qq upgrade

RUN apt-get -qq install software-properties-common \
    && add-apt-repository -y ppa:qpid/released \
    && apt-get -qq update \
    && apt-get -qq install build-essential make openjdk-8-jdk maven nodejs python-numpy python unzip xz-utils

RUN apt-get -qq install libqpidmessaging2-dev libqpidtypes1-dev libqpidcommon2-dev \
        libqpid-proton8-dev python-qpid python-qpid-messaging python-qpid-proton

RUN cd /usr/bin && ln -s nodejs node

COPY . /root/quiver

ARG CACHE_BUST=1
RUN cd /root/quiver && make install PREFIX=/usr

CMD ["quiver-test"]
