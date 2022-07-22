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

.NOTPARALLEL:

DESTDIR := ""
PREFIX := /usr/local
INSTALLED_QUIVER_HOME := ${PREFIX}/lib/quiver
DOCKER_TAG := docker.io/ssorj/quiver

export QUIVER_HOME := ${CURDIR}/build/quiver
export PATH := ${CURDIR}/build/bin:${PATH}
export PYTHONPATH := ${QUIVER_HOME}/python:${CURDIR}/python:${PYTHONPATH}
export NODE_PATH := /usr/lib/node_modules:${NODE_PATH}

VERSION := $(shell cat VERSION.txt)

DOTNET_ENABLED := \
	$(shell which dotnet 1> /dev/null 2>&1 && echo yes || echo no)
JAVA_ENABLED := \
	$(shell which mvn 1> /dev/null 2>&1 && echo yes || echo no)
JAVASCRIPT_ENABLED := \
	$(shell which node 1> /dev/null 2>&1 && echo yes || echo no)
QPID_PROTON_C_ENABLED := \
	$(shell PYTHONPATH=python scripts/check-cpp-header "proton/proactor.h" 1> /dev/null 2>&1 && echo yes || echo no)
QPID_PROTON_CPP_ENABLED := \
	$(shell PYTHONPATH=python scripts/check-cpp-header "proton/message.hpp" 1> /dev/null 2>&1 && echo yes || echo no)
QPID_PROTON_PYTHON_ENABLED := \
	$(shell PYTHONPATH=python scripts/check-python3-import "proton" 1> /dev/null 2>&1 && echo yes || echo no)

ifneq (${QPID_PROTON_PYTHON_ENABLED},yes)
        $(warning Qpid Proton Python is required to build Quiver)
endif

$(info DOTNET_ENABLED=${DOTNET_ENABLED})
$(info JAVA_ENABLED=${JAVA_ENABLED})
$(info JAVASCRIPT_ENABLED=${JAVASCRIPT_ENABLED})
$(info QPID_PROTON_C_ENABLED=${QPID_PROTON_C_ENABLED})
$(info QPID_PROTON_CPP_ENABLED=${QPID_PROTON_CPP_ENABLED})
$(info QPID_PROTON_PYTHON_ENABLED=${QPID_PROTON_PYTHON_ENABLED})

BIN_SOURCES := $(shell find bin -type f -name \*.in)
BIN_TARGETS := ${BIN_SOURCES:%.in=build/%}

PYTHON_SOURCES := $(shell find python -type f -name \*.py -o -name \*.py.in)
PYTHON_TARGETS := ${PYTHON_SOURCES:%=build/quiver/%} ${PYTHON_SOURCES:%.in=build/quiver/%}

TESTDATA_SOURCES := $(shell find python -type f -name \*.pem)
TESTDATA_TARGETS := ${TESTDATA_SOURCES:%=build/quiver/%} ${TESTDATA_SOURCES:%.in=build/quiver/%}

TARGETS := ${BIN_TARGETS} ${PYTHON_TARGETS} ${TESTDATA_TARGETS} \
	build/quiver/impls/quiver-arrow-qpid-proton-python \
	build/quiver/impls/quiver-server-activemq-artemis \
	build/quiver/impls/quiver-server-builtin \
	build/quiver/impls/quiver-server-qpid-dispatch \
	build/quiver/impls/brokerlib.py

ifeq (${JAVA_ENABLED},yes)
TARGETS += \
	build/quiver/impls/quiver-arrow-activemq-artemis-jms \
	build/quiver/impls/quiver-arrow-activemq-jms \
	build/quiver/impls/quiver-arrow-qpid-jms \
	build/quiver/impls/quiver-arrow-qpid-protonj2 \
	build/quiver/impls/quiver-arrow-vertx-proton
endif

ifeq (${DOTNET_ENABLED},yes)
TARGETS += build/quiver/impls/quiver-arrow-qpid-proton-dotnet
endif

ifeq (${JAVASCRIPT_ENABLED},yes)
TARGETS += build/quiver/impls/quiver-arrow-rhea
endif

ifeq (${QPID_PROTON_C_ENABLED},yes)
TARGETS += build/quiver/impls/quiver-arrow-qpid-proton-c
endif

ifeq (${QPID_PROTON_CPP_ENABLED},yes)
TARGETS += build/quiver/impls/quiver-arrow-qpid-proton-cpp
endif

CCFLAGS := -g -O2 -std=c++11 -lstdc++ -lpthread
CFLAGS  := -g -O2 -std=c99

.PHONY: default
default: build

.PHONY: help
help:
	@echo "build          Build the code"
	@echo "install        Install the code"
	@echo "clean          Clean up the source tree"
	@echo "test           Run the tests"

.PHONY: clean
clean:
	rm -rf build
	rm -rf install
	rm -rf python/__pycache__
	find dotnet -name bin -type d -exec rm -rf {} +
	find java -name target -type d -exec rm -rf {} +

.PHONY: build
build: ${TARGETS} build/prefix.txt
	cp python/plano.py build/quiver/python/plano.py
	scripts/smoke-test

.PHONY: install
install: build
	scripts/install-files build/bin ${DESTDIR}$$(cat build/prefix.txt)/bin
	scripts/install-files build/quiver ${DESTDIR}$$(cat build/prefix.txt)/lib/quiver

.PHONY: test
test: build
	quiver-self-test

.PHONY: big-test
big-test: test os-tests

.PHONY: os-tests
os-tests: test-fedora test-ubuntu test-centos

.PHONY: test-fedora
test-fedora: docker-build docker-test

.PHONY: test-ubuntu
test-ubuntu:
	sudo docker build -f scripts/test-ubuntu.dockerfile -t quiver-test-ubuntu .
	sudo docker run quiver-test-ubuntu

.PHONY: test-centos
test-centos:
	sudo docker build -f scripts/test-centos.dockerfile -t quiver-test-centos .
	sudo docker run quiver-test-centos

.PHONY: check-dependencies
check-dependencies:
	scripts/check-dependencies

.PHONY: docker-build
docker-build:
	sudo docker build -t ${DOCKER_TAG} .

.PHONY: docker-test
docker-test: docker-build
	sudo docker run -t ${DOCKER_TAG} quiver-self-test

.PHONY: docker-run
docker-run: docker-build
	sudo docker run -it ${DOCKER_TAG}

.PHONY: docker-push
docker-push:
	sudo docker push ${DOCKER_TAG}

build/prefix.txt:
	echo ${PREFIX} > build/prefix.txt

build/bin/%: bin/%.in
	scripts/configure-file -a default_home=${INSTALLED_QUIVER_HOME} $< $@

build/quiver/impls/%: impls/%.in
	scripts/configure-file -a default_home=${INSTALLED_QUIVER_HOME} $< $@

build/quiver/impls/quiver-arrow-qpid-proton-c: impls/quiver-arrow-qpid-proton-c.c
	@mkdir -p ${@D}
	${CC} $< -o $@ ${CFLAGS} -lqpid-proton -lqpid-proton-proactor

build/quiver/impls/quiver-arrow-qpid-proton-cpp: impls/quiver-arrow-qpid-proton-cpp.cpp
	@mkdir -p ${@D}
	${CXX} $< -o $@ ${CCFLAGS} -lqpid-proton -lqpid-proton-cpp

# XXX Use a template for the java rules

build/quiver/impls/quiver-arrow-vertx-proton: impls/quiver-arrow-vertx-proton.in build/quiver/java/quiver-vertx-proton.jar

build/quiver/java/quiver-vertx-proton.jar: java/quiver-vertx-proton/pom.xml $(shell find java/quiver-vertx-proton/src -type f)
	@mkdir -p build/quiver/java
	cd java/quiver-vertx-proton && mvn -B clean package
	cp java/quiver-vertx-proton/target/quiver-vertx-proton-1.0.0-SNAPSHOT-jar-with-dependencies.jar $@

build/quiver/impls/quiver-arrow-qpid-protonj2: impls/quiver-arrow-qpid-protonj2.in build/quiver/java/quiver-protonj2.jar

build/quiver/impls/brokerlib.py: impls/brokerlib.py
	@mkdir -p ${@D}
	cp $< $@

build/quiver/java/quiver-qpid-protonj2.jar: java/quiver-protonj2/pom.xml $(shell find java/quiver-protonj2/src -type f)
	@mkdir -p build/quiver/java
	cd java/quiver-protonj2 && mvn -B clean package
	cp java/quiver-protonj2/target/quiver-protonj2-1.0.0-SNAPSHOT-jar-with-dependencies.jar $@

build/quiver/impls/quiver-arrow-qpid-proton-dotnet: impls/quiver-arrow-qpid-proton-dotnet.in build/quiver/dotnet/quiver-qpid-proton-dotnet

build/quiver/dotnet/quiver-qpid-proton-dotnet: dotnet/quiver-proton-dotnet/quiver-proton-dotnet.csproj $(shell find dotnet/quiver-proton-dotnet -type f)
	@mkdir -p build/quiver/dotnet/quiver-qpid-proton-dotnet
	cd dotnet/quiver-proton-dotnet && dotnet restore && dotnet build --configuration Release
	cp -R dotnet/quiver-proton-dotnet/bin/Release/net6.0/* $@

build/quiver/impls/quiver-arrow-activemq-jms: impls/quiver-arrow-activemq-jms.in build/quiver/java/quiver-activemq-jms.jar

build/quiver/impls/quiver-arrow-activemq-artemis-jms: impls/quiver-arrow-activemq-artemis-jms.in \
    build/quiver/java/quiver-activemq-artemis-jms.jar

build/quiver/impls/quiver-arrow-qpid-jms: impls/quiver-arrow-qpid-jms.in build/quiver/java/quiver-qpid-jms.jar

build/quiver/java/%.jar: java/pom.xml java/quiver-jms-driver/pom.xml $(shell find java/quiver-jms-driver/src -type f)
	@mkdir -p build/quiver/java
	cd java/quiver-jms-driver && mvn -B install
	cd java && mvn -B clean package
	cp java/$*/target/$*-1.0.0-SNAPSHOT-jar-with-dependencies.jar $@

build/quiver/javascript/%: javascript/%
	@mkdir -p ${@D}
	cp $< $@

build/quiver/python/quiver/common.py: python/quiver/common.py.in
	@mkdir -p ${@D}
	scripts/configure-file -a version=${VERSION} -a default_home=${INSTALLED_QUIVER_HOME} $< $@

build/quiver/python/quiver/%: python/quiver/% python/pencil.py python/plano.py build/quiver/python/quiver/common.py
	@mkdir -p ${@D}
	cp $< $@

build/quiver/python/%: python/%
	@mkdir -p ${@D}
	cp $< $@

build/quiver/python/quiver/test_tls_certs/%: python/quiver/test_tls_certs/%
	mkdir -p $(@D)
	cp $< $@

.PHONY: update-rhea
update-rhea:
	rm -rf javascript
	@mkdir -p javascript
	npm install rhea --prefix javascript

.PHONY: update-%
update-%:
	curl -sfo python/$*.py "https://raw.githubusercontent.com/ssorj/$*/master/python/$*.py"
