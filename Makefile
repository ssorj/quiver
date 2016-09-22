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

DESTDIR := ""
PREFIX := ${HOME}/.local
QUIVER_HOME = ${PREFIX}/lib/quiver

TARGETS = \
	build/bin/quiver \
	build/bin/quiver-launch \
	build/exec/quiver-activemq-jms \
	build/exec/quiver-activemq-artemis-jms \
	build/exec/quiver-qpid-jms \
	build/exec/quiver-qpid-messaging-cpp \
	build/exec/quiver-qpid-messaging-python \
	build/exec/quiver-qpid-proton-cpp \
	build/exec/quiver-qpid-proton-python \
	build/exec/quiver-vertx-proton \
	build/exec/quiver-rhea

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
	rm -rf java/target

.PHONY: build
build: ${TARGETS} build-jms build-vertx-proton

.PHONY: build-jms
build-jms:
	@mkdir -p build/java
	cd java/jms && mvn clean package
	cp java/jms/target/quiver-jms-*-jar-with-dependencies.jar build/java/quiver-jms.jar

.PHONY: build-vertx-proton
build-vertx-proton:
	@mkdir -p build/java
	cd java/vertx-proton && mvn clean package
	cp java/vertx-proton/target/quiver-vertx-proton-*-jar-with-dependencies.jar build/java/quiver-vertx-proton.jar

.PHONY: install
install: build
	mkdir -p ${DESTDIR}${QUIVER_HOME}
	scripts/install-files python ${DESTDIR}${QUIVER_HOME}/python \*.py
	scripts/install-files javascript ${DESTDIR}${QUIVER_HOME}/javascript \*
	scripts/install-files build/java ${DESTDIR}${QUIVER_HOME}/java \*
	scripts/install-files build/exec ${DESTDIR}${QUIVER_HOME}/exec \*
	scripts/install-executable build/bin/quiver ${DESTDIR}${PREFIX}/bin/quiver
	scripts/install-executable build/bin/quiver-launch ${DESTDIR}${PREFIX}/bin/quiver-launch

.PHONY: devel
devel: PREFIX := ${PWD}/install
devel: clean install
	quiver --help > /dev/null
	quiver-launch --help > /dev/null

.PHONY: test
test: devel
	scripts/smoke-test 10

build/bin/%: bin/%.in
	@mkdir -p build/bin
	scripts/configure-file $< $@ quiver_home ${QUIVER_HOME}

build/exec/%: exec/%.in
	@mkdir -p build/exec
	scripts/configure-file $< $@ quiver_home ${QUIVER_HOME}

build/exec/quiver-qpid-messaging-cpp: exec/quiver-qpid-messaging-cpp.cpp
	@mkdir -p build/exec
	gcc -std=c++11 -lqpidmessaging -lqpidtypes -lstdc++ $< -o $@

build/exec/quiver-qpid-proton-cpp: exec/quiver-qpid-proton-cpp.cpp
	@mkdir -p build/exec
	gcc -std=c++11 -lqpid-proton -lstdc++ $< -o $@

.PHONY: update-rhea
update-rhea:
	npm install rhea --prefix javascript

.PHONY: update-plano
update-plano:
	curl "https://raw.githubusercontent.com/ssorj/plano/master/python/plano.py" -o scripts/plano.py
