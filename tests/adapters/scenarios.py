import shutil
from pathlib import Path

from agentctl.domain import Source

FIXTURES_DIRECTORY = Path(__file__).parent.parent / "fixtures"


def copy_fixture_scenario(tmp_path: Path, source: Source, scenario_name: str) -> Path:
    """Copy one on-disk scenario out of `tests/fixtures/<source>/` into `tmp_path`.

    Adapters stat and read the tree they are pointed at, so every scenario is
    copied rather than read in place — a test can then write into it without
    dirtying the fixtures the next test reads.
    """
    destination = tmp_path / scenario_name
    shutil.copytree(FIXTURES_DIRECTORY / source.value / scenario_name, destination)
    return destination
