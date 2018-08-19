import dataclasses
import pytest
import datamodel


@pytest.fixture
def extension_cleanup():
    yield
    datamodel._dataclass_kwargs_extensions = []


def test_frozen_instances_are_frozen_by_default(extension_cleanup):
    import datamodel.extensions.frozen

    @datamodel.datamodel
    class Simple:
        x: int
        y: str

    a = Simple(1, '2')
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.x = 2
    assert a.x == 1
    assert a.y == '2'


def test_frozen_frozen_flag_can_be_owerwritten(extension_cleanup):
    import datamodel.extensions.frozen

    @datamodel.datamodel(frozen=False)
    class SimpleNonFrozen:
        x: int
        y: str

    a = SimpleNonFrozen(1, '2')
    a.x = 2
    assert a.x == 2
    assert a.y == '2'
