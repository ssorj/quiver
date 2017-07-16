NAME := quiver
SOURCES := build/SOURCES/${NAME}-SNAPSHOT.tar.gz

.PHONY: build
build: build/SRPMS/${NAME}-SNAPSHOT.src.rpm

.PHONY: clean
clean:
	rm -rf build

.PHONY: test
test: build/SRPMS/${NAME}-SNAPSHOT.src.rpm
	rpmbuild -D "_topdir ${PWD}/build" --rebuild $<
	@echo "Output: ${PWD}/$$(find build/RPMS -type f)"

build/commit:
	@mkdir -p build
	scripts/github-get-commit ssorj ${NAME} HEAD > $@

build/SPECS/${NAME}.spec: ${NAME}.spec.in build/commit
	@mkdir -p build/SPECS
	scripts/configure-file -a commit=$$(cat build/commit) $< $@

build/SOURCES/${NAME}-SNAPSHOT.tar.gz: build/commit
	@mkdir -p build/SOURCES
	scripts/github-get-archive ssorj ${NAME} $$(cat $<) $@

build/SRPMS/${NAME}-SNAPSHOT.src.rpm: build/SPECS/${NAME}.spec ${SOURCES}
	rpmbuild -D "_topdir ${PWD}/build" -bs $<
	@rm -f $@
	cp build/SRPMS/${NAME}-*.src.rpm $@
	@echo "Output: ${PWD}/$@"
