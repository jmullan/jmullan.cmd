from jmullan.cmd import cmd


class MyMain(cmd.Main):
    def main(self) -> None:
        super().setup()


def test_main():
    # this is just a stub that only tests that we can load the module and use the class
    test_main = MyMain()
    assert test_main is not None
    test_main.main()
