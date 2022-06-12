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

FROM registry.fedoraproject.org/fedora-minimal AS build

RUN microdnf -y install gcc-c++ java-17-openjdk-devel make maven nodejs npm python3-numpy unzip zstd \
    cyrus-sasl-devel cyrus-sasl-md5 cyrus-sasl-plain python3-qpid-proton \
    qpid-proton-c-devel qpid-proton-cpp-devel \
    && microdnf -y clean all

RUN npm -g install rhea

COPY . /root/quiver

RUN cd /root/quiver && make install PREFIX=/usr/local

FROM registry.fedoraproject.org/fedora-minimal

RUN microdnf -y install java-17-openjdk-headless nodejs python3-numpy unzip zstd cyrus-sasl cyrus-sasl-md5 \
    cyrus-sasl-plain python3-qpid-proton qpid-dispatch-router qpid-proton-c qpid-proton-cpp \
    && microdnf -y clean all

COPY --from=build /usr/local /usr/local

ENV NODE_PATH=/usr/local/lib/node_modules
WORKDIR /root
CMD ["/bin/bash"]
