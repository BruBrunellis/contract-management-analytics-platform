import importlib.util
import shutil
import sys
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTEST_TEMP_ROOT = PROJECT_ROOT / ".pytest_tmp"


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    """Give each test session a fresh temporary directory on Windows."""
    PYTEST_TEMP_ROOT.mkdir(exist_ok=True)
    session_temp_dir = PYTEST_TEMP_ROOT / f"run-{uuid.uuid4().hex}"
    config.option.basetemp = session_temp_dir
    config._session_temp_dir = session_temp_dir


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """Apply the directory after pytest has created its temporary-path factory."""
    session.config._tmp_path_factory._given_basetemp = session.config._session_temp_dir


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Remove the session directory without touching another test run."""
    shutil.rmtree(session.config._session_temp_dir, ignore_errors=True)


def load_module(filename):
    path = PROJECT_ROOT / "2.scr" / "1.generator" / filename
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_staging_module(filename="stg_empresas.py"):
    path = PROJECT_ROOT / "2.scr" / "2.etl" / filename
    if str(path.parent) not in sys.path:
        sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_pipeline_runner():
    path = PROJECT_ROOT / "2.scr" / "run_pipeline.py"
    spec = importlib.util.spec_from_file_location("run_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
