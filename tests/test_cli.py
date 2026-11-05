import pytest

from promo_finder.cli import main


def test_cli_requires_a_subcommand():
    with pytest.raises(SystemExit):
        main([])
