export PATH := ${PWD}/install/bin:${PATH}

DESTDIR := ""
PREFIX := ${HOME}/.local
QUIVER_HOME = ${PREFIX}/share/quiver

.PHONY: default
default: devel

.PHONY: help
help:
	@echo "build          Build the code"
	@echo "install        Install the code"
	@echo "clean          Clean up the source tree"
	@echo "devel          Build, install, and test in this checkout"

.PHONY: clean
clean:
	rm -rf build
	rm -rf install

.PHONY: build
build: build/libexec/quiver/quiver-qpid-messaging-cpp
	scripts/configure-file bin/quiver.in build/bin/quiver \
		quiver_home ${QUIVER_HOME}
	scripts/configure-file bin/quiver-proton-python.in \
		build/libexec/quiver/quiver-proton-python \
		quiver_home ${QUIVER_HOME}
	scripts/configure-file bin/quiver-qpid-messaging-python.in \
		build/libexec/quiver/quiver-qpid-messaging-python \
		quiver_home ${QUIVER_HOME}

.PHONY: install
install: build
	mkdir -p ${QUIVER_HOME}
	scripts/install-files python ${DESTDIR}${PREFIX}${QUIVER_HOME}/python \*.py
	scripts/install-executable build/bin/quiver ${DESTDIR}${PREFIX}/bin/quiver
	scripts/install-executable build/libexec/quiver/quiver-proton-python \
		${DESTDIR}${PREFIX}/libexec/quiver/quiver-proton-python
	scripts/install-executable build/libexec/quiver/quiver-qpid-messaging-python \
		${DESTDIR}${PREFIX}/libexec/quiver/quiver-qpid-messaging-python

.PHONY: devel
devel: PREFIX := ${PWD}/install
devel: clean install
#	scripts/test-external-server qpid-messaging-python q0
	scripts/smoke-test

build/libexec/quiver/quiver-qpid-messaging-cpp: bin/quiver-qpid-messaging-cpp.cpp
	mkdir -p build/libexec/quiver
	gcc -std=c++11 -lqpidmessaging -lqpidtypes -lstdc++ $< -o $@
