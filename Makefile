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

export PATH := ${PWD}/install/bin:${PATH}

VERSION := $(shell cat VERSION.txt)

DESTDIR := ""
PREFIX := ${HOME}/.local
QUIVER_HOME = ${PREFIX}/lib/quiver

TARGETS := \
	build/bin/quiver \
	build/bin/quiver-arrow \
	build/bin/quiver-client-test \
	build/bin/quiver-server-test \
	build/bin/quiver-smoke-test \
	build/exec/arrow-activemq-jms \
	build/exec/arrow-activemq-artemis-jms \
	build/exec/arrow-qpid-jms \
	build/exec/arrow-vertx-proton \
	build/exec/arrow-rhea \
	build/exec/arrow-qpid-messaging-python \
	build/exec/arrow-qpid-proton-python \
	build/exec/arrow-qpid-messaging-cpp \
	build/java/quiver-activemq-artemis-jms.jar \
	build/java/quiver-activemq-jms.jar \
	build/java/quiver-qpid-jms.jar \
	build/java/quiver-vertx-proton.jar

CCFLAGS := -Os -std=c++11 -lstdc++ -lqpid-proton -lqpidmessaging -lqpidtypes

ifdef QPID_PROTON_CPP_ENABLED
	TARGETS += build/exec/arrow-qpid-proton-cpp
	CCFLAGS += -lqpid-proton-cpp
endif

.PHONY: default
default: devel

.PHONY: help
help:
	@echo "build          Build the code"
	@echo "install        Install the code"
	@echo "clean          Clean up the source tree"
	@echo "devel          Build, install, and run a basic test in this checkout"
	@echo "test           Run the tests"

.PHONY: clean
clean:
	rm -rf build
	rm -rf install
	rm -rf java/quiver-activemq-jms/target
	rm -rf java/quiver-activemq-artemis-jms/target
	rm -rf java/quiver-jms-driver/target
	rm -rf java/quiver-qpid-jms/target
	rm -rf java/quiver-vertx-proton/target

.PHONY: build
build: ${TARGETS}
	cp exec/amqp-test-broker build/exec

.PHONY: install
install: build
	@mkdir -p ${DESTDIR}${QUIVER_HOME}
	scripts/install-files python ${DESTDIR}${QUIVER_HOME}/python \*.py
	scripts/install-files javascript ${DESTDIR}${QUIVER_HOME}/javascript \*
	scripts/install-files build/java ${DESTDIR}${QUIVER_HOME}/java \*
	scripts/install-files build/exec ${DESTDIR}${QUIVER_HOME}/exec \*
	scripts/install-files build/bin ${DESTDIR}${PREFIX}/bin \*

.PHONY: devel
devel: PREFIX := ${PWD}/install
devel: install
	quiver-arrow send //localhost:12345/a/b/c --init-only
	quiver q0 --init-only

.PHONY: test
test: devel
	quiver-smoke-test

build/bin/%: bin/%.in
	@mkdir -p build/bin
	scripts/configure-file $< $@ quiver_home ${QUIVER_HOME}

build/exec/%: exec/%.in
	@mkdir -p build/exec
	scripts/configure-file $< $@ quiver_home ${QUIVER_HOME}

build/exec/%: exec/%.cpp
	@mkdir -p build/exec
	g++ $< -o $@ ${CCFLAGS}

build/java/quiver-vertx-proton.jar: java/quiver-vertx-proton/pom.xml $(shell find java/quiver-vertx-proton/src -type f)
	@mkdir -p build/java
	cd java/quiver-vertx-proton && mvn clean package
	cp java/quiver-vertx-proton/target/quiver-vertx-proton-${VERSION}-jar-with-dependencies.jar $@

build/java/%.jar: java/pom.xml java/quiver-jms-driver/pom.xml $(shell find java/quiver-jms-driver/src -type f)
	@mkdir -p build/java
	cd java/quiver-jms-driver && mvn install
	cd java/ && mvn clean package
	cp java/$*/target/$*-${VERSION}-jar-with-dependencies.jar $@

.PHONY: update-rhea
update-rhea:
	npm install rhea --prefix javascript

.PHONY: update-plano
update-plano:
	curl "https://raw.githubusercontent.com/ssorj/plano/master/python/plano.py" -o scripts/plano.py
