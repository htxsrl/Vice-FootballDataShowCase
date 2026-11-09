"""M0: struttura del codice, cartelle dei dati e dipendenze presenti nel container."""

import importlib

import pytest

from vice.config import get_settings


@pytest.mark.parametrize("modulo", ["vice.data", "vice.analysis", "vice.agent", "vice.views", "scripts"])
def test_pacchetti_importabili(modulo):
    importlib.import_module(modulo)


def test_cartelle_dei_dati():
    s = get_settings()
    assert s.processed_dir == s.data_dir / "processed"
    assert s.raw_dir == s.data_dir / "raw"
    assert s.processed_dir.is_dir()
    assert (s.data_dir / "README.md").is_file()


def test_dipendenze_di_analisi():
    import numpy
    import pandas
    import pyarrow

    assert int(pandas.__version__.split(".")[0]) >= 3
    assert numpy.__version__ and pyarrow.__version__
