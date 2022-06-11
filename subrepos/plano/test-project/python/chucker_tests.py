from plano import *

@test
def test_hello():
    print("Hello")

@test
def test_goodbye():
    print("Goodbye")

@test(disabled=True)
def test_badbye():
    print("Badbye")
    assert False

@test
def test_skipped():
    raise PlanoTestSkipped("Test coverage")

@test(disabled=True)
def test_keyboard_interrupt():
    raise KeyboardInterrupt()

@test(disabled=True, timeout=0.05)
def test_timeout():
    sleep(10, quiet=True)
    assert False

@test(disabled=True)
def test_process_error():
    run("expr 1 / 0")

@test(disabled=True)
def test_system_exit():
    exit(1)
