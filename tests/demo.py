import logging
from sys import stdout

from jmullan.logging.easy_logging import easy_initialize_logging

from jmullan.cmd import auto_config, cmd

logger = logging.getLogger(__name__)


class DemoMain(cmd.Main):
    def __init__(self):
        cmd.Main.__init__(self)
        auto_config.add_boolean_argument(
            self.parser,
            """Enable hyperspace for fast travel.""",
            "hyperspace",
            ["HYPERSPACE", "HYPERSPACE_ENABLED"],
            False,
        )

    def setup(self) -> None:
        super().setup()
        if self.args.verbose:
            easy_initialize_logging("DEBUG")
        elif self.args.quiet:
            easy_initialize_logging("ERROR")
        else:
            easy_initialize_logging("INFO")

    def main(self):
        super().main()
        logger.debug("Starting the demo")
        if self.args.hyperspace:
            stdout.write("Hyperspace is enabled!\n")
        else:
            stdout.write("Hyperspace is disabled!\n")
        stdout.write("Thank you\n")


if __name__ == "__main__":
    demo = DemoMain()
    demo.main()
