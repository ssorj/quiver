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

import os as _os
import pwd as _pwd
import signal as _signal
import socket as _socket
import sys as _sys
import threading as _threading

try:
    import http.server as _http
except ImportError: # pragma: nocover
    import BaseHTTPServer as _http

from plano import *

test_project_dir = join(get_parent_dir(get_parent_dir(__file__)), "test-project")

class test_project(working_dir):
    def __enter__(self):
        dir = super(test_project, self).__enter__()
        copy(test_project_dir, ".", inside=False)
        return dir

TINY_INTERVAL = 0.05

@test
def archive_operations():
    with working_dir():
        make_dir("some-dir")
        touch("some-dir/some-file")

        make_archive("some-dir")
        assert is_file("some-dir.tar.gz")

        extract_archive("some-dir.tar.gz", output_dir="some-subdir")
        assert is_dir("some-subdir/some-dir")
        assert is_file("some-subdir/some-dir/some-file")

        rename_archive("some-dir.tar.gz", "something-else")
        assert is_file("something-else.tar.gz")

        extract_archive("something-else.tar.gz")
        assert is_dir("something-else")
        assert is_file("something-else/some-file")

@test
def command_operations():
    class SomeCommand(BaseCommand):
        def __init__(self):
            self.parser = BaseArgumentParser()
            self.parser.add_argument("--interrupt", action="store_true")
            self.parser.add_argument("--explode", action="store_true")

        def parse_args(self, args):
            return self.parser.parse_args(args)

        def init(self, args):
            self.verbose = args.verbose
            self.interrupt = args.interrupt
            self.explode = args.explode

        def run(self):
            if self.verbose:
                print("Hello")

            if self.interrupt:
                raise KeyboardInterrupt()

            if self.explode:
                raise PlanoError("Exploded")

    SomeCommand().main([])
    SomeCommand().main(["--interrupt"])

    with expect_system_exit():
        SomeCommand().main(["--verbose", "--explode"])

@test
def console_operations():
    eprint("Here's a story")
    eprint("About a", "man named Brady")

    pprint(list_dir())
    pprint(PlanoProcess, 1, "abc", end="\n\n")

    flush()

    with console_color("red"):
        print("ALERT")

    print(cformat("AMBER ALERT", color="yellow"))
    print(cformat("NO ALERT"))

    cprint("CRITICAL ALERT", color="red", bright=True)

@test
def dir_operations():
    with working_dir():
        test_dir = make_dir("some-dir")
        test_file_1 = touch(join(test_dir, "some-file-1"))
        test_file_2 = touch(join(test_dir, "some-file-2"))

        result = list_dir(test_dir)
        assert join(test_dir, result[0]) == test_file_1, (join(test_dir, result[0]), test_file_1)

        result = list_dir(test_dir, "*-file-1")
        assert result == ["some-file-1"], (result, ["some-file-1"])

        result = list_dir(test_dir, exclude="*-file-1")
        assert result == ["some-file-2"], (result, ["some-file-2"])

        result = list_dir("some-dir", "*.not-there")
        assert result == [], result

        with working_dir():
            result = list_dir()
            assert result == [], result

        result = find(test_dir)
        assert result == [test_file_1, test_file_2], (result, [test_file_1, test_file_2])

        result = find(test_dir, "*-file-1")
        assert result == [test_file_1], (result, [test_file_1])

        result = find(test_dir, exclude="*-file-1")
        assert result == [test_file_2], (result, [test_file_2])

        with working_dir():
            result = find()
            assert result == [], result

    with working_dir():
        with working_dir("a-dir", quiet=True):
            touch("a-file")

        curr_dir = get_current_dir()
        prev_dir = change_dir("a-dir")
        new_curr_dir = get_current_dir()
        new_prev_dir = change_dir(curr_dir)

        assert curr_dir == prev_dir, (curr_dir, prev_dir)
        assert new_curr_dir == new_prev_dir, (new_curr_dir, new_prev_dir)

@test
def env_operations():
    result = join_path_var("a", "b", "c", "a")
    assert result == "a:b:c", result

    curr_dir = get_current_dir()

    with working_dir("."):
        assert get_current_dir() == curr_dir, (get_current_dir(), curr_dir)

    result = get_home_dir()
    assert result == ENV["HOME"], result

    result = get_home_dir("alice")
    assert result.endswith("alice"), result

    user = _pwd.getpwuid(_os.getuid())[0]
    result = get_user()
    assert result == user, (result, user)

    result = get_hostname()
    assert result, result

    result = get_program_name()
    assert result, result

    result = get_program_name("alpha beta")
    assert result == "alpha", result

    result = get_program_name("X=Y alpha beta")
    assert result == "alpha", result

    result = which("echo")
    assert result, result

    with working_env(YES_I_AM_SET=1):
        check_env("YES_I_AM_SET")

        with expect_error():
            check_env("NO_I_AM_NOT")

        with working_env(I_AM_SET_NOW=1, amend=False):
            check_env("I_AM_SET_NOW")
            assert "YES_I_AM_SET" not in ENV, ENV

    with working_env(SOME_VAR=1):
        assert ENV["SOME_VAR"] == "1", ENV.get("SOME_VAR")

        with working_env(SOME_VAR=2):
            assert ENV["SOME_VAR"] == "2", ENV.get("SOME_VAR")

    with expect_error():
        check_program("not-there")

    with expect_error():
        check_module("not_there")

    with expect_output(contains="ARGS:") as out:
        with open(out, "w") as f:
            print_env(file=f)

@test
def file_operations():
    with working_dir():
        alpha_dir = make_dir("alpha-dir")
        alpha_file = touch(join(alpha_dir, "alpha-file"))
        alpha_link = make_link(join(alpha_dir, "alpha-file-link"), "alpha-file")
        alpha_broken_link = make_link(join(alpha_dir, "broken-link"), "no-such-file")

        beta_dir = make_dir("beta-dir")
        beta_file = touch(join(beta_dir, "beta-file"))
        beta_link = make_link(join(beta_dir, "beta-file-link"), "beta-file")
        beta_broken_link = make_link(join(beta_dir, "broken-link"), join("..", alpha_dir, "no-such-file"))
        beta_another_link = make_link(join(beta_dir, "broken-link"), join("..", alpha_dir, "alpha-file-link"))

        assert exists(beta_link)
        assert exists(beta_file)

        with working_dir("beta-dir"):
            assert is_file(read_link("beta-file-link"))

        copied_file = copy(alpha_file, beta_dir)
        assert copied_file == join(beta_dir, "alpha-file"), copied_file
        assert is_file(copied_file), list_dir(beta_dir)

        copied_link = copy(beta_link, join(beta_dir, "beta-file-link-copy"))
        assert copied_link == join(beta_dir, "beta-file-link-copy"), copied_link
        assert is_link(copied_link), list_dir(beta_dir)

        copied_dir = copy(alpha_dir, beta_dir)
        assert copied_dir == join(beta_dir, "alpha-dir"), copied_dir
        assert is_link(join(copied_dir, "alpha-file-link"))

        moved_file = move(beta_file, alpha_dir)
        assert moved_file == join(alpha_dir, "beta-file"), moved_file
        assert is_file(moved_file), list_dir(alpha_dir)
        assert not exists(beta_file), list_dir(beta_dir)

        moved_dir = move(beta_dir, alpha_dir)
        assert moved_dir == join(alpha_dir, "beta-dir"), moved_dir
        assert is_dir(moved_dir), list_dir(alpha_dir)
        assert not exists(beta_dir)

        gamma_dir = make_dir("gamma-dir")
        gamma_file = touch(join(gamma_dir, "gamma-file"))

        delta_dir = make_dir("delta-dir")
        delta_file = touch(join(delta_dir, "delta-file"))

        copy(gamma_dir, delta_dir, inside=False)
        assert is_file(join("delta-dir", "gamma-file"))

        move(gamma_dir, delta_dir, inside=False)
        assert is_file(join("delta-dir", "gamma-file"))
        assert not exists(gamma_dir)

        epsilon_dir = make_dir("epsilon-dir")
        epsilon_file_1 = touch(join(epsilon_dir, "epsilon-file-1"))
        epsilon_file_2 = touch(join(epsilon_dir, "epsilon-file-2"))
        epsilon_file_3 = touch(join(epsilon_dir, "epsilon-file-3"))
        epsilon_file_4 = touch(join(epsilon_dir, "epsilon-file-4"))

        remove("not-there")

        remove(epsilon_file_2)
        assert not exists(epsilon_file_2)

        remove(epsilon_dir)
        assert not exists(epsilon_file_1)
        assert not exists(epsilon_dir)

        remove([epsilon_file_3, epsilon_file_4])
        assert not exists(epsilon_file_3)
        assert not exists(epsilon_file_4)

        file = write("xes", "x" * 10)
        result = get_file_size(file)
        assert result == 10, result

@test
def http_operations():
    class Handler(_http.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"[1]")

        def do_POST(self):
            length = int(self.headers["content-length"])
            content = self.rfile.read(length)

            self.send_response(200)
            self.end_headers()
            self.wfile.write(content)

        def do_PUT(self):
            length = int(self.headers["content-length"])
            content = self.rfile.read(length)

            self.send_response(200)
            self.end_headers()

    class ServerThread(_threading.Thread):
        def __init__(self, server):
            _threading.Thread.__init__(self)
            self.server = server

        def run(self):
            self.server.serve_forever()

    host, port = "localhost", get_random_port()
    url = "http://{0}:{1}".format(host, port)
    server = _http.HTTPServer((host, port), Handler)
    server_thread = ServerThread(server)

    server_thread.start()

    try:
        with working_dir():
            result = http_get(url)
            assert result == "[1]", result

            result = http_get(url, insecure=True)
            assert result == "[1]", result

            result = http_get(url, output_file="a")
            output = read("a")
            assert result is None, result
            assert output == "[1]", output

            result = http_get_json(url)
            assert result == [1], result

            file_b = write("b", "[2]")

            result = http_post(url, read(file_b), insecure=True)
            assert result == "[2]", result

            result = http_post(url, read(file_b), output_file="x")
            output = read("x")
            assert result is None, result
            assert output == "[2]", output

            result = http_post_file(url, file_b)
            assert result == "[2]", result

            result = http_post_json(url, parse_json(read(file_b)))
            assert result == [2], result

            file_c = write("c", "[3]")

            result = http_put(url, read(file_c), insecure=True)
            assert result is None, result

            result = http_put_file(url, file_c)
            assert result is None, result

            result = http_put_json(url, parse_json(read(file_c)))
            assert result is None, result
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join()

@test
def io_operations():
    with working_dir():
        input_ = "some-text\n"
        file_a = write("a", input_)
        output = read(file_a)

        assert input_ == output, (input_, output)

        pre_input = "pre-some-text\n"
        post_input = "post-some-text\n"

        prepend(file_a, pre_input)
        append(file_a, post_input)

        output = tail(file_a, 100)
        tailed = tail(file_a, 1)

        assert output.startswith(pre_input), (output, pre_input)
        assert output.endswith(post_input), (output, post_input)
        assert tailed == post_input, (tailed, post_input)

        input_lines = [
            "alpha\n",
            "beta\n",
            "gamma\n",
        ]

        file_b = write_lines("b", input_lines)
        output_lines = read_lines(file_b)

        assert input_lines == output_lines, (input_lines, output_lines)

        pre_lines = ["pre-alpha\n"]
        post_lines = ["post-gamma\n"]

        prepend_lines(file_b, pre_lines)
        append_lines(file_b, post_lines)

        output_lines = tail_lines(file_b, 100)
        tailed_lines = tail_lines(file_b, 1)

        assert output_lines[0] == pre_lines[0], (output_lines[0], pre_lines[0])
        assert output_lines[4] == post_lines[0], (output_lines[4], post_lines[0])
        assert tailed_lines[0] == post_lines[0], (tailed_lines[0], post_lines[0])

        file_c = touch("c")
        assert is_file(file_c), file_c

        file_d = write("d", "front@middle@@middle@back")
        replace_in_file(file_d, "@middle@", "M", count=1)
        result = read(file_d)
        assert result == "frontM@middle@back", result

        file_e = write("e", "123")
        file_f = write("f", "456")
        concatenate("g", (file_e, "not-there", file_f))
        result = read("g")
        assert result == "123456", result

@test
def iterable_operations():
    result = unique([1, 1, 1, 2, 2, 3])
    assert result == [1, 2, 3], result

    result = skip([1, "", 2, None, 3])
    assert result == [1, 2, 3], result

    result = skip([1, "", 2, None, 3], 2)
    assert result == [1, "", None, 3], result

@test
def json_operations():
    with working_dir():
        input_data = {
            "alpha": [1, 2, 3],
        }

        file_a = write_json("a", input_data)
        output_data = read_json(file_a)

        assert input_data == output_data, (input_data, output_data)

        json = read(file_a)
        parsed_data = parse_json(json)
        emitted_json = emit_json(input_data)

        assert input_data == parsed_data, (input_data, parsed_data)
        assert json == emitted_json, (json, emitted_json)

@test
def link_operations():
    with working_dir():
        make_dir("some-dir")
        path = get_absolute_path(touch("some-dir/some-file"))

        with working_dir("another-dir"):
            link = make_link("a-link", path)
            linked_path = read_link(link)
            assert linked_path == path, (linked_path, path)

@test
def logging_operations():
    error("Error!")
    warn("Warning!")
    notice("Take a look!")
    notice(123)
    debug("By the way")
    debug("abc{0}{1}{2}", 1, 2, 3)

    with expect_exception(RuntimeError):
        fail(RuntimeError("Error!"))

    with expect_error():
        fail("Error!")

    for level in ("debug", "notice", "warn", "error"):
        with expect_output(contains="Hello") as out:
            with logging_disabled():
                with logging_enabled(level=level, output=out):
                    log(level, "hello")

    with expect_output(equals="") as out:
        with logging_enabled(output=out):
            with logging_disabled():
                error("Yikes")

@test
def path_operations():
    with working_dir("/"):
        curr_dir = get_current_dir()
        assert curr_dir == "/", curr_dir

        path = "a/b/c"
        result = get_absolute_path(path)
        assert result == join(curr_dir, path), result

    path = "/x/y/z"
    result = get_absolute_path(path)
    assert result == path, result

    path = "/x/y/z"
    assert is_absolute(path)

    path = "x/y/z"
    assert not is_absolute(path)

    path = "a//b/../c/"
    result = normalize_path(path)
    assert result == "a/c", result

    path = "/a/../c"
    result = get_real_path(path)
    assert result == "/c", result

    path = "/a/b"
    result = get_relative_path(path, "/a/c")
    assert result == "../b", result

    path = "/a/b"
    result = get_file_url(path)
    assert result == "file:/a/b", result

    with working_dir():
        result = get_file_url("afile")
        assert result == "file:{0}/afile".format(get_current_dir()), result

    path = "/alpha/beta.ext"
    path_split = "/alpha", "beta.ext"
    path_split_extension = "/alpha/beta", ".ext"
    name_split_extension = "beta", ".ext"

    result = join(*path_split)
    assert result == path, result

    result = split(path)
    assert result == path_split, result

    result = split_extension(path)
    assert result == path_split_extension, result

    result = get_parent_dir(path)
    assert result == path_split[0], result

    result = get_base_name(path)
    assert result == path_split[1], result

    result = get_name_stem(path)
    assert result == name_split_extension[0], result

    result = get_name_stem("alpha.tar.gz")
    assert result == "alpha", result

    result = get_name_extension(path)
    assert result == name_split_extension[1], result

    with working_dir():
        touch("adir/afile")

        check_exists("adir")
        check_exists("adir/afile")
        check_dir("adir")
        check_file("adir/afile")

        with expect_error():
            check_exists("adir/notafile")

        with expect_error():
            check_file("adir/notafile")

        with expect_error():
            check_file("adir")

        with expect_error():
            check_dir("not-there")

        with expect_error():
            check_dir("adir/afile")

        await_exists("adir/afile")

        with expect_timeout():
            await_exists("adir/notafile", timeout=TINY_INTERVAL)

@test
def port_operations():
    result = get_random_port()
    assert result >= 49152 and result <= 65535, result

    server_port = get_random_port()
    server_socket = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)

    try:
        server_socket.bind(("localhost", server_port))
        server_socket.listen(5)

        await_port(server_port)
        await_port(str(server_port))

        check_port(server_port)

        with expect_error():
            get_random_port(min=server_port, max=server_port)
    finally:
        server_socket.close()

    with expect_timeout():
        await_port(get_random_port(), timeout=TINY_INTERVAL)

@test
def process_operations():
    result = get_process_id()
    assert result, result

    proc = run("date")
    assert proc is not None, proc

    print(repr(proc))

    run("date", stash=True)

    proc = run(["echo", "hello"], check=False)
    assert proc.exit_code == 0, proc.exit_code

    proc = run("cat /uh/uh", check=False)
    assert proc.exit_code > 0, proc.exit_code

    with expect_output() as out:
        run("date", output=out)

    run("date", output=DEVNULL)
    run("date", stdin=DEVNULL)
    run("date", stdout=DEVNULL)
    run("date", stderr=DEVNULL)

    run("echo hello", quiet=True)
    run("echo hello | cat", shell=True)
    run(["echo", "hello"], shell=True)

    with expect_error():
        run("/not/there")

    with expect_error():
        run("cat /whoa/not/really", stash=True)

    result = call("echo hello")
    assert result == "hello\n", result

    result = call("echo hello | cat", shell=True)
    assert result == "hello\n", result

    with expect_error():
        call("cat /whoa/not/really")

    if PYTHON3:
        proc = start("sleep 10")

        with expect_timeout():
            wait(proc, timeout=TINY_INTERVAL)

    proc = start("echo hello")
    sleep(TINY_INTERVAL)
    stop(proc)

    proc = start("sleep 10")
    stop(proc)

    proc = start("sleep 10")
    kill(proc)
    sleep(TINY_INTERVAL)
    stop(proc)

    proc = start("date --not-there")
    sleep(TINY_INTERVAL)
    stop(proc)

    with start("sleep 10"):
        sleep(TINY_INTERVAL)

    with working_dir():
        touch("i")

        with start("date", stdin="i", stdout="o", stderr="e"):
            pass

    with expect_system_exit():
        exit()

    with expect_system_exit():
        exit(verbose=True)

    with expect_system_exit():
        exit("abc")

    with expect_system_exit():
        exit("abc", verbose=True)

    with expect_system_exit():
        exit(Exception())

    with expect_system_exit():
        exit(Exception(), verbose=True)

    with expect_system_exit():
        exit(123)

    with expect_system_exit():
        exit(123, verbose=True)

    with expect_system_exit():
        exit(-123)

    with expect_exception(PlanoException):
        exit(object())

@test
def string_operations():
    result = replace("ab", "a", "b")
    assert result == "bb", result

    result = replace("aba", "a", "b", count=1)
    assert result == "bba", result

    result = remove_prefix(None, "xxx")
    assert result == "", result

    result = remove_prefix("anterior", "ant")
    assert result == "erior", result

    result = remove_prefix("anterior", "ext")
    assert result == "anterior", result

    result = remove_suffix(None, "xxx")
    assert result == "", result

    result = remove_suffix("exterior", "ior")
    assert result == "exter", result

    result = remove_suffix("exterior", "nal")
    assert result == "exterior"

    result = shorten("abc", 2)
    assert result == "ab", result

    result = shorten("abc", None)
    assert result == "abc", result

    result = shorten("abc", 10)
    assert result == "abc", result

    result = shorten("ellipsis", 6, ellipsis="...")
    assert result == "ell...", result

    result = shorten(None, 6)
    assert result == "", result

    result = plural(None)
    assert result == "", result

    result = plural("")
    assert result == "", result

    result = plural("test")
    assert result == "tests", result

    result = plural("test", 1)
    assert result == "test", result

    result = plural("bus")
    assert result == "busses", result

    result = plural("bus", 1)
    assert result == "bus", result

    result = plural("terminus", 2, "termini")
    assert result == "termini", result

    result = capitalize(None)
    assert result == "", result

    result = capitalize("")
    assert result == "", result

    result = capitalize("hello, Frank")
    assert result == "Hello, Frank", result

    encoded_result = base64_encode(b"abc")
    decoded_result = base64_decode(encoded_result)
    assert decoded_result == b"abc", decoded_result

    encoded_result = url_encode("abc=123&yeah!")
    decoded_result = url_decode(encoded_result)
    assert decoded_result == "abc=123&yeah!", decoded_result

@test
def temp_operations():
    system_temp_dir = get_system_temp_dir()

    result = make_temp_file()
    assert result.startswith(system_temp_dir), result

    result = make_temp_file(suffix=".txt")
    assert result.endswith(".txt"), result

    result = make_temp_dir()
    assert result.startswith(system_temp_dir), result

    with temp_dir() as d:
        assert is_dir(d), d
        list_dir(d)

    with temp_file() as f:
        assert is_file(f), f
        write(f, "test")

    with working_dir() as d:
        assert is_dir(d), d
        list_dir(d)

    user_temp_dir = get_user_temp_dir()
    assert user_temp_dir, user_temp_dir

    ENV.pop("XDG_RUNTIME_DIR", None)

    user_temp_dir = get_user_temp_dir()
    assert user_temp_dir, user_temp_dir

@test
def test_operations():
    with test_project():
        with working_module_path("python"):
            import chucker
            import chucker_tests

            print_tests(chucker_tests)

            for verbose in (False, True):
                run_tests(chucker_tests, verbose=verbose)
                run_tests(chucker_tests, exclude="*hello*", verbose=verbose)

                with expect_error():
                    run_tests(chucker, verbose=verbose)

                with expect_error():
                    run_tests(chucker_tests, enable="*badbye*", verbose=verbose)

                with expect_error():
                    run_tests(chucker_tests, enable="*badbye*", fail_fast=True, verbose=verbose)

                with expect_exception(KeyboardInterrupt):
                    run_tests(chucker_tests, enable="test_keyboard_interrupt", verbose=verbose)

                with expect_error():
                    run_tests(chucker_tests, enable="test_timeout", verbose=verbose)

                with expect_error():
                    run_tests(chucker_tests, enable="test_process_error", verbose=verbose)

                with expect_error():
                    run_tests(chucker_tests, enable="test_system_exit", verbose=verbose)

            with expect_system_exit():
                PlanoTestCommand().main(["--module", "nosuchmodule"])

            def run_command(*args):
                PlanoTestCommand(chucker_tests).main(args)

            run_command("--verbose")
            run_command("--list")

            with expect_system_exit():
                run_command("--enable", "*badbye*")

            with expect_system_exit():
                run_command("--enable", "*badbye*", "--verbose")

    try:
        with expect_exception():
            pass
        raise Exception() # pragma: nocover
    except AssertionError:
        pass

    with expect_output(equals="abc123", contains="bc12", startswith="abc", endswith="123") as out:
        write(out, "abc123")

@test
def time_operations():
    start_time = get_time()

    sleep(TINY_INTERVAL)

    assert get_time() - start_time > TINY_INTERVAL

    with expect_system_exit():
        with start("sleep 10"):
            from plano import _default_sigterm_handler
            _default_sigterm_handler(_signal.SIGTERM, None)

    result = format_duration(0.1)
    assert result == "0.1s", result

    result = format_duration(1)
    assert result == "1s", result

    result = format_duration(1, align=True)
    assert result == "1.0s", result

    result = format_duration(60)
    assert result == "60s", result

    result = format_duration(3600)
    assert result == "1h", result

    with Timer() as timer:
        sleep(TINY_INTERVAL)
        assert timer.elapsed_time > TINY_INTERVAL

    assert timer.elapsed_time > TINY_INTERVAL

    with expect_timeout():
        with Timer(timeout=TINY_INTERVAL) as timer:
            sleep(10)

@test
def unique_id_operations():
    id1 = get_unique_id()
    id2 = get_unique_id()

    assert id1 != id2, (id1, id2)

    result = get_unique_id(1)
    assert len(result) == 2

    result = get_unique_id(16)
    assert len(result) == 32

@test
def value_operations():
    result = nvl(None, "a")
    assert result == "a", result

    result = nvl("b", "a")
    assert result == "b", result

    assert is_string("a")
    assert not is_string(1)

    for value in (None, "", (), [], {}):
        assert is_empty(value), value

    for value in (object(), " ", (1,), [1], {"a": 1}):
        assert not is_empty(value), value

    result = pformat({"z": 1, "a": 2})
    assert result == "{'a': 2, 'z': 1}", result

    result = format_empty((), "[nothing]")
    assert result == "[nothing]", result

    result = format_empty((1,), "[nothing]")
    assert result == (1,), result

    result = format_not_empty("abc", "[{0}]")
    assert result == "[abc]", result

    result = format_not_empty({}, "[{0}]")
    assert result == {}, result

    result = format_repr(Namespace(a=1, b=2), limit=1)
    assert result == "Namespace(a=1)", result

    result = Namespace(a=1, b=2)
    assert result.a == 1, result
    assert result.b == 2, result
    assert "a" in result, result
    assert "c" not in result, result
    repr(result)

    other = Namespace(a=1, b=2, c=3)
    assert result != other, (result, other)

@test
def yaml_operations():
    try:
        import yaml as _yaml
    except ImportError:
        raise PlanoTestSkipped("PyYAML is not available")

    with working_dir():
        input_data = {
            "alpha": [1, 2, 3],
        }

        file_a = write_yaml("a", input_data)
        output_data = read_yaml(file_a)

        assert input_data == output_data, (input_data, output_data)

        yaml = read(file_a)
        parsed_data = parse_yaml(yaml)
        emitted_yaml = emit_yaml(input_data)

        assert input_data == parsed_data, (input_data, parsed_data)
        assert yaml == emitted_yaml, (yaml, emitted_yaml)

@test
def plano_command():
    if PYTHON2: # pragma: nocover
        raise PlanoTestSkipped("The plano command is not supported on Python 2")

    with working_dir():
        PlanoCommand().main([])

    with working_dir():
        write("Planofile", "garbage")

        with expect_system_exit():
            PlanoCommand().main([])

    with expect_system_exit():
        PlanoCommand("no-such-file").main([])

    with expect_system_exit():
        PlanoCommand().main(["-f", "no-such-file"])

    def run_command(*args):
        PlanoCommand().main(["-f", test_project_dir] + list(args))

    with test_project():
        run_command()
        run_command("--help")
        run_command("--quiet")
        run_command("--init-only")

        run_command("build")
        run_command("install")
        run_command("clean")

        with expect_system_exit():
            run_command("build", "--help")

        with expect_system_exit():
            run_command("no-such-command")

        with expect_system_exit():
            run_command("no-such-command", "--help")

        with expect_system_exit():
            run_command("--help", "no-such-command")

        run_command("extended-command", "a", "b", "--omega", "z")

        with expect_system_exit():
            run_command("echo")

        with expect_exception(contains="Trouble"):
            run_command("echo", "Hello", "--trouble")

        run_command("echo", "Hello", "--count", "5")

        with expect_system_exit():
            run_command("echo", "Hello", "--count", "not-an-int")

        run_command("haberdash", "ballcap", "fedora", "hardhat", "--last", "turban")
        result = read_json("haberdash.json")
        assert result == ["ballcap", "fedora", "hardhat", "turban"], result

        run_command("haberdash", "ballcap", "--last", "turban")
        result = read_json("haberdash.json")
        assert result == ["ballcap", "turban"], result

        run_command("haberdash", "ballcap")
        result = read_json("haberdash.json")
        assert result == ["ballcap", "bowler"], result

        run_command("balderdash", "bunk", "poppycock")
        result = read_json("balderdash.json")
        assert result == ["bunk", "poppycock", "rubbish"], result

        run_command("balderdash", "bunk")
        result = read_json("balderdash.json")
        assert result == ["bunk", "malarkey", "rubbish"], result

        run_command("balderdash", "bunk", "--other", "bollocks")
        result = read_json("balderdash.json")
        assert result == ["bunk", "malarkey", "bollocks"], result

@test
def plano_shell_command():
    python_dir = get_absolute_path("python")

    with working_dir():
        write("script1", "garbage")

        with expect_exception(NameError):
            PlanoShellCommand().main(["script1"])

        write("script2", "print_env()")

        PlanoShellCommand().main(["script2"])

        PlanoShellCommand().main(["--command", "print_env()"])

        write("command", "from plano import *; PlanoShellCommand().main()")

        with working_env(PYTHONPATH=python_dir):
            run("{0} command".format(_sys.executable), input="cprint('Hi!', color='green'); exit()")
            run("echo \"cprint('Bi!', color='red')\" | {0} command -".format(_sys.executable), shell=True)

    with expect_system_exit():
        PlanoShellCommand().main(["no-such-file"])
