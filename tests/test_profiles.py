from pathlib import Path

import pytest
import yaml

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


@pytest.mark.parametrize("profile_path", sorted(PROFILES_DIR.glob("*.yml")))
def test_profile_yaml_is_well_formed(profile_path):
    with profile_path.open(encoding="utf-8") as fh:
        yaml.safe_load(fh)
