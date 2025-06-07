import argparse
from unittest.mock import patch

import pytest

from jmullan.cmd import auto_config


@pytest.fixture
def environment():
    fake_environ = {}
    with patch("jmullan.cmd.auto_config.get_environ") as mock_get_environ:
        mock_get_environ.side_effect = lambda k, d=None: fake_environ.get(k, d)
        yield fake_environ


@pytest.fixture
def pretend_stdout_is_a_tty():
    with patch("jmullan.cmd.auto_config.stdout_is_a_tty") as mock_stdout_is_a_tty:
        mock_stdout_is_a_tty.return_value = True
        yield mock_stdout_is_a_tty


@pytest.fixture
def pretend_stdout_is_not_a_tty():
    with patch("jmullan.cmd.auto_config.stdout_is_a_tty") as mock_stdout_is_a_tty:
        mock_stdout_is_a_tty.return_value = False
        yield mock_stdout_is_a_tty


def test_get_environ(environment: dict):
    environment["foo"] = "bar"
    assert auto_config.get_environ("foo") == "bar"
    assert auto_config.get_environ("qqq") is None


def test_a_help_formatter_simple():
    parser = argparse.ArgumentParser(
        prog="program",
        formatter_class=auto_config.AHelpFormatter,
        description="This is a parser",
        epilog="This is an epilog",
    )
    expected = """usage: program [-h]

This is a parser

options:
  -h, --help  show this help message and exit

This is an epilog
"""
    help_text = parser.format_help()
    assert help_text == expected


def test_a_help_formatter_colors(environment, pretend_stdout_is_not_a_tty):
    parser = argparse.ArgumentParser(
        prog="program", formatter_class=auto_config.AHelpFormatter, description="This is a parser"
    )
    auto_config.add_colors_argument(parser)
    expected = """usage: program [-h] [--colors | --no-colors]

This is a parser

options:
  -h, --help   show this help message and exit

Enable colored highlighting? (Colors currently defaulting to off):
  Env: $NO_COLOR=(not set): Set to 1 to disable colors by default
       $CLICOLOR_FORCE=(not set): Set to 1 to enable colors by default
       $CLICOLOR=(not set): Set to 1 to enable colors if stdout is a tty (no)
       $TERM=(not set): cannot guess this terminal's color capabilities

  Force the color setting:
  --colors     Force colors on
  --no-colors  Force colors off
"""
    help_text = parser.format_help()
    assert help_text == expected


def test_a_help_formatter_colors_2(environment, pretend_stdout_is_a_tty):
    parser = argparse.ArgumentParser(
        prog="program", formatter_class=auto_config.AHelpFormatter, description="This is a parser"
    )
    auto_config.add_colors_argument(parser)
    expected = """usage: program [-h] [--colors | --no-colors]

This is a parser

options:
  -h, --help   show this help message and exit

Enable colored highlighting? (Colors currently defaulting to on):
  Env: $NO_COLOR=(not set): Set to 1 to disable colors by default
       $CLICOLOR_FORCE=(not set): Set to 1 to enable colors by default
       $CLICOLOR=(not set): Set to 1 to enable colors if stdout is a tty (yes)
       $TERM=(not set): cannot guess this terminal's color capabilities

  Force the color setting:
  --colors     Force colors on
  --no-colors  Force colors off
"""
    help_text = parser.format_help()
    assert help_text == expected


def test_a_help_formatter_boolean_1(environment: dict):
    parser = argparse.ArgumentParser(
        prog="program",
        formatter_class=auto_config.AHelpFormatter,
        description="This is a parser",
        epilog="This is an epilog",
    )
    auto_config.add_boolean_argument(parser, "Do a thing", "foo-bar", ["FOOBAR", "FOO_BAR"], True)
    expected = """usage: program [-h]

This is a parser

options:
  -h, --help  show this help message and exit

  [--foo-bar (default) | --no-foo-bar] Do a thing:
    · $FOOBAR=(not set)
    · $FOO_BAR=(not set)

This is an epilog
"""
    help_text = parser.format_help()
    assert help_text == expected


def test_a_help_formatter_boolean_2(environment: dict):
    parser = argparse.ArgumentParser(prog="program", formatter_class=auto_config.AHelpFormatter)
    auto_config.add_boolean_argument(parser, "Do a thing", "foo-bar", ["FOOBAR", "FOO_BAR"], False)
    expected = """usage: program [-h]

options:
  -h, --help  show this help message and exit

  [--foo-bar | --no-foo-bar (default)] Do a thing:
    · $FOOBAR=(not set)
    · $FOO_BAR=(not set)
"""
    help_text = parser.format_help()
    assert help_text == expected


def test_a_help_formatter_boolean_3(environment: dict):
    environment["FOOBAR"] = "true"

    parser = argparse.ArgumentParser(prog="program", formatter_class=auto_config.AHelpFormatter)
    auto_config.add_boolean_argument(parser, "Do a thing", "foo-bar", ["FOOBAR", "FOO_BAR"], False)
    expected = """usage: program [-h]

options:
  -h, --help  show this help message and exit

  [--foo-bar (set by $FOOBAR=true) | --no-foo-bar] Do a thing:
    ✓ $FOOBAR=true
    · $FOO_BAR=(not set)
"""
    help_text = parser.format_help()
    assert help_text == expected


def test_a_help_formatter_boolean_4(environment: dict):
    environment["FOOBAR"] = "false"

    parser = argparse.ArgumentParser(prog="program", formatter_class=auto_config.AHelpFormatter)
    auto_config.add_boolean_argument(parser, "Do a thing", "foo-bar", ["FOOBAR", "FOO_BAR"], False)
    expected = """usage: program [-h]

options:
  -h, --help  show this help message and exit

  [--foo-bar | --no-foo-bar (set by $FOOBAR=false)] Do a thing:
    ✗ $FOOBAR=false
    · $FOO_BAR=(not set)
"""
    help_text = parser.format_help()
    assert help_text == expected
