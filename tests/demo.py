import logging
from jmullan.cmd import auto_config
from jmullan.cmd import cmd
from jmullan.logging.easy_logging import easy_initialize_logging

logger = logging.getLogger(__name__)

class DemoMain(cmd.Main):
    def __init__(self):
        cmd.Main.__init__(self)
        auto_config.add_boolean_argument(
            self.parser,
            """Enable hyperspace for fast travel.""",
            "hyperspace",
            ["HYPERSPACE", "HYPERSPACE_ENABLED"],
            False
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
            print("Hyperspace is enabled!")
        else:
            print("Hyperspace is disabled!")

if __name__ == "__main__":
    demo = DemoMain()
    demo.main()
