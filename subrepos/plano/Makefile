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

# A workaround for an install-with-prefix problem in Fedora 36
#
# https://docs.fedoraproject.org/en-US/fedora/latest/release-notes/developers/Development_Python/#_pipsetup_py_installation_with_prefix
# https://bugzilla.redhat.com/show_bug.cgi?id=2026979

export RPM_BUILD_ROOT := fake

.PHONY: build
build:
	python -m build

.PHONY: test
test: clean build
	python -m venv build/venv
	. build/venv/bin/activate && pip install --force-reinstall dist/plano-*-py3-none-any.whl
	. build/venv/bin/activate && plano-self-test

.PHONY: install
install: build
	pip install --user --force-reinstall dist/plano-*-py3-none-any.whl

.PHONY: clean
clean:
	rm -rf build dist htmlcov .coverage

.PHONY: docs
docs:
	mkdir -p build
	sphinx-build -M html docs build/docs

.PHONY: coverage
coverage: build
	python -m venv build/venv
	. build/venv/bin/activate && pip install --force-reinstall dist/plano-*-py3-none-any.whl
	. build/venv/bin/activate && PYTHONPATH=build/venv/lib/python3.10/site-packages coverage3 run --omit /tmp/\*,\*/yaml/\* build/venv/bin/plano-self-test
	coverage3 report
	coverage3 html
	@echo file:${CURDIR}/htmlcov/index.html

.PHONY: upload
upload: build
	twine upload --repository testpypi dist/*
