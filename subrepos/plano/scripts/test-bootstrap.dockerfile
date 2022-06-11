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

FROM fedora

RUN dnf -qy update && dnf -q clean all

RUN dnf -y install python git

COPY test-project /root/test-project
COPY bin/plano /root/test-project/plano

WORKDIR /root/test-project
RUN git init

RUN mkdir /root/test-project/modules

WORKDIR /root/test-project/modules
RUN git submodule add https://github.com/ssorj/plano.git

WORKDIR /root/test-project/python
RUN ln -s ../modules/plano/python/plano.py
RUN ln -s ../modules/plano/python/bullseye.py

WORKDIR /root/test-project
RUN ./plano || :

RUN git submodule update --init

CMD ["./plano"]
