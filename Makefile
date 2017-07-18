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

export PATH := ${PWD}/install/bin:${PATH}
export PYTHONPATH := ${PWD}/install/lib/quiver/python:${PWD}/python:${PYTHONPATH}
export NODE_PATH := /usr/lib/node_modules:${NODE_PATH}

VERSION := $(shell cat VERSION.txt)

MAVEN_INSTALLED := \
	$(shell which mvn 1> /dev/null 2>&1 && echo yes)
NODEJS_INSTALLED := \
	$(shell which node 1> /dev/null 2>&1 && echo yes)
QPID_MESSAGING_CPP_INSTALLED := \
	$(shell PYTHONPATH=python scripts/check-cpp-header "qpid/messaging/Message.h" 1> /dev/null 2>&1 && echo yes)
QPID_MESSAGING_PYTHON_INSTALLED := \
	$(shell PYTHONPATH=python scripts/check-python-import "qpid_messaging" 1> /dev/null 2>&1 && echo yes)
QPID_PROTON_C_INSTALLED := \
	$(shell PYTHONPATH=python scripts/check-cpp-header "proton/proactor.h" 1> /dev/null 2>&1 && echo yes)
QPID_PROTON_CPP_INSTALLED := \
	$(shell PYTHONPATH=python scripts/check-cpp-header "proton/message.hpp" 1> /dev/null 2>&1 && echo yes)
QPID_PROTON_PYTHON_INSTALLED := \
	$(shell PYTHONPATH=python scripts/check-python-import "proton" 1> /dev/null 2>&1 && echo yes)

# XXX
#ifneq (${QPID_PROTON_PYTHON_INSTALLED},yes)
#        $(error Qpid Proton Python is required to build Quiver)
#endif

# XXX Workaround for an Ubuntu packaging problem
ifeq ($(shell lsb_release -is),Ubuntu)
	QPID_PROTON_CPP_INSTALLED := no
endif

DESTDIR := ""
PREFIX := /usr/local
QUIVER_HOME := ${PREFIX}/lib/quiver

TARGETS := \
	build/bin/quiver \
	build/bin/quiver-arrow \
	build/bin/quiver-bench \
	build/bin/quiver-launch \
	build/bin/quiver-server \
	build/bin/quiver-test \
	build/exec/quiver-arrow-qpid-proton-python \
	build/exec/quiver-server-activemq \
	build/exec/quiver-server-activemq-artemis \
	build/exec/quiver-server-builtin \
	build/exec/quiver-server-qpid-cpp \
	build/exec/quiver-server-qpid-dispatch \
	build/python/quiver/common.py

ifeq (${MAVEN_INSTALLED},yes)
TARGETS += \
	build/exec/quiver-arrow-activemq-artemis-jms \
	build/exec/quiver-arrow-activemq-jms \
	build/exec/quiver-arrow-qpid-jms \
	build/exec/quiver-arrow-vertx-proton
endif

ifeq (${NODEJS_INSTALLED},yes)
TARGETS += \
	build/exec/quiver-arrow-rhea
endif

ifeq (${QPID_MESSAGING_CPP_INSTALLED},yes)
TARGETS += \
	build/exec/quiver-arrow-qpid-messaging-cpp
endif

ifeq (${QPID_MESSAGING_PYTHON_INSTALLED},yes)
TARGETS += \
	build/exec/quiver-arrow-qpid-messaging-python
endif

ifeq (${QPID_PROTON_C_INSTALLED},yes)
TARGETS += \
	build/exec/quiver-arrow-qpid-proton-c
endif

ifeq (${QPID_PROTON_CPP_INSTALLED},yes)
TARGETS += \
	build/exec/quiver-arrow-qpid-proton-cpp
endif

CCFLAGS := -Os -std=c++11 -lstdc++
CFLAGS  := -Os

.PHONY: default
default: devel

.PHONY: help
help:
	@echo "build          Build the code"
	@echo "install        Install the code"
	@echo "clean          Clean up the source tree"
	@echo "devel          Build, install, and smoke test in this checkout"
	@echo "test           Run the tests"

.PHONY: clean
clean:
	rm -rf build
	rm -rf install
	find java -name target -type d -exec rm -rf {} +

.PHONY: build
build: ${TARGETS}

.PHONY: install
install: clean build do-install

.PHONY: do-install
do-install:
	scripts/install-files --name \*.py python ${DESTDIR}${QUIVER_HOME}/python
	scripts/install-files build/python ${DESTDIR}${QUIVER_HOME}/python
	scripts/install-files javascript ${DESTDIR}${QUIVER_HOME}/javascript
	scripts/install-files build/java ${DESTDIR}${QUIVER_HOME}/java
	scripts/install-files build/exec ${DESTDIR}${QUIVER_HOME}/exec
	scripts/install-files build/bin ${DESTDIR}${PREFIX}/bin

.PHONY: devel
devel: PREFIX := ${PWD}/install
devel: QUIVER_HOME := ${PREFIX}/lib/quiver
devel: build do-install
	scripts/smoke-test

.PHONY: test
test: devel
	quiver-test

.PHONY: big-test
big-test: test test-centos test-fedora test-ubuntu

.PHONY: test-centos
test-centos:
	sudo docker build -f scripts/test-centos.dockerfile -t quiver-test-centos .
	sudo docker run quiver-test-centos

.PHONY: test-fedora
test-fedora:
	sudo docker build -f scripts/test-fedora.dockerfile -t quiver-test-fedora .
	sudo docker run quiver-test-fedora

.PHONY: test-ubuntu
test-ubuntu:
	sudo docker build -f scripts/test-ubuntu.dockerfile -t quiver-test-ubuntu .
	sudo docker run quiver-test-ubuntu

.PHONY: check-dependencies
check-dependencies:
	scripts/check-dependencies

build/bin/%: bin/%.in
	scripts/configure-file -a quiver_home=${QUIVER_HOME} $< $@

build/exec/%: exec/%.in
	scripts/configure-file -a quiver_home=${QUIVER_HOME} $< $@

build/exec/quiver-arrow-qpid-proton-c: exec/quiver-arrow-qpid-proton-c.c
	@mkdir -p build/exec
	${CC} $< -o $@ ${CFLAGS} -lqpid-proton -lqpid-proton-proactor

build/exec/quiver-arrow-qpid-proton-cpp: exec/quiver-arrow-qpid-proton-cpp.cpp
	@mkdir -p build/exec
	${CXX} $< -o $@ ${CCFLAGS} -lqpid-proton -lqpid-proton-cpp

build/exec/quiver-arrow-qpid-messaging-cpp: exec/quiver-arrow-qpid-messaging-cpp.cpp
	@mkdir -p build/exec
	${CXX} $< -o $@ ${CCFLAGS} -lqpidmessaging -lqpidtypes

# XXX Use a template for the java rules

build/exec/quiver-arrow-vertx-proton: exec/quiver-arrow-vertx-proton.in build/java/quiver-vertx-proton.jar

build/java/quiver-vertx-proton.jar: java/quiver-vertx-proton/pom.xml $(shell find java/quiver-vertx-proton/src -type f)
	@mkdir -p build/java
	cd java/quiver-vertx-proton && mvn clean package
	cp java/quiver-vertx-proton/target/quiver-vertx-proton-1.0.0-SNAPSHOT-jar-with-dependencies.jar $@

build/exec/quiver-arrow-activemq-jms: exec/quiver-arrow-activemq-jms.in build/java/quiver-activemq-jms.jar

build/exec/quiver-arrow-activemq-artemis-jms: exec/quiver-arrow-activemq-artemis-jms.in build/java/quiver-activemq-artemis-jms.jar

build/exec/quiver-arrow-qpid-jms: exec/quiver-arrow-qpid-jms.in build/java/quiver-qpid-jms.jar

build/java/%.jar: java/pom.xml java/quiver-jms-driver/pom.xml $(shell find java/quiver-jms-driver/src -type f)
	@mkdir -p build/java
	cd java/quiver-jms-driver && mvn install
	cd java && mvn clean package
	cp java/$*/target/$*-1.0.0-SNAPSHOT-jar-with-dependencies.jar $@

build/python/%.py: python/%.py.in
	@mkdir -p build/python
	scripts/configure-file -a version=${VERSION} -a quiver_home=${QUIVER_HOME} $< $@

.PHONY: update-rhea
update-rhea:
	rm -rf javascript
	@mkdir -p javascript
	npm install rhea --prefix javascript

.PHONY: update-%
update-%:
	curl "https://raw.githubusercontent.com/ssorj/$*/master/python/$*.py" -o python/$*.py
