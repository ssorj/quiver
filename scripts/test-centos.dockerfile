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

FROM centos
MAINTAINER Justin Ross <jross@apache.org>

RUN yum -q -y update && yum -q clean all

RUN yum -q -y install epel-release \
    && yum -q -y install java-1.8.0-openjdk nodejs python34-numpy python python34 \
        python-qpid-messaging qpid-cpp-client qpid-proton-c qpid-proton-cpp unzip xz gcc-c++ \
        java-1.8.0-openjdk-devel maven make qpid-cpp-client-devel qpid-proton-c-devel qpid-proton-cpp-devel \
        cyrus-sasl-devel cyrus-sasl-plain cyrus-sasl-md5 openssl \
    && yum -q clean all

COPY . /root/quiver

ARG CACHE_BUST=1
RUN cd /root/quiver && make install PREFIX=/usr

WORKDIR /root
CMD ["quiver-test"]
