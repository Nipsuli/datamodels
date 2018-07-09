import dataclasses
import datetime
import typing
import pytest
import udatetime
import datamodel


@datamodel.datamodel
class Simple:
    x: int
    y: str


def test_type_to_str():
    A = typing.TypeVar('A', str, bytes)
    JSONstr = typing.NewType('JSONstr', str)
    te = [
        (str, 'str'),
        (int, 'int'),
        (A, 'A'),
        (JSONstr, 'JSONstr'),
        (typing.List, 'List[T]'),
        (typing.List[str], 'List[str]'),
        (Simple, 'Simple'),
        (typing.List[Simple], 'List[Simple]'),
        (typing.List[typing.List[str]], 'List[List[str]]'),
        (typing.Dict[str, int], 'Dict[str, int]'),
        (typing.Dict[str, typing.List[Simple]], 'Dict[str, List[Simple]]'),
        (typing.Union[str, Simple], 'Union[str, Simple]'),
        (typing.Optional[str], 'Optional[str]'),
        (typing.Tuple[str, A], 'Tuple[str, A]'),
        (typing.Tuple[str, ...], 'Tuple[str, ...]'),
        (typing.Callable[..., typing.Any], 'Callable[..., Any]'),  # well, not relevant for this, but what the heck...
        (typing.Callable[[str, str], typing.List[str]], 'Callable[[str, str], List[str]]'),
    ]
    for test, expected in te:
        assert expected == datamodel.utils.type_to_str(test)


def test_datamodel_sets_frozen_true():
    a = Simple(1, '2')
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.x = 2
    assert a.x == 1
    assert a.y == '2'


@datamodel.datamodel(frozen=False)
class SimpleNonFrozen:
    x: int
    y: str


def test_non_frozen_datamodel():
    a = SimpleNonFrozen(1, '2')
    a.x = 2
    assert a.x == 2
    assert a.y == '2'


def _assert_serialization_deserialization(obj, expected_dict, expected_json):
    serializeable_dict = obj.to_serializeable()
    assert expected_dict == serializeable_dict
    json_str = obj.to_json()
    assert expected_json == json_str
    obj1 = obj.__class__.from_dict(serializeable_dict)
    obj2 = obj.__class__.from_json(json_str)
    assert obj == obj1 == obj2
    assert obj1 is not obj
    assert obj2 is not obj


def test_simple_model_serialization_deserialization():
    _assert_serialization_deserialization(
        Simple(1, '1'),
        expected_dict={'x': 1, 'y': '1'},
        expected_json='{"x": 1, "y": "1"}'
    )


@datamodel.datamodel
class WithDates:
    d: datetime.date
    dt: datetime.datetime


def test_datetime_serialization_deserialization():
    dt = datamodel.utils.udatetime_tz_to_dateutils_tz(udatetime.now())
    _assert_serialization_deserialization(
        WithDates(dt.date(), dt),
        expected_dict={'d': dt.date().isoformat(), 'dt': dt.isoformat()},
        expected_json=f'{{"d": "{dt.date().isoformat()}", "dt": "{dt.isoformat()}"}}'
    )


@datamodel.datamodel
class SimpleWithCollections:
    x: typing.List[str]
    y: typing.Dict[str, int]


def test_simple_collections_serialization_deserialization():
    _assert_serialization_deserialization(
        SimpleWithCollections(['a', 'b'], {'a': 1, 'b': 2}),
        expected_dict={'x': ['a', 'b'], 'y': {'a': 1, 'b': 2}},
        expected_json='{"x": ["a", "b"], "y": {"a": 1, "b": 2}}'
    )


@datamodel.datamodel
class NestedDataClasses:
    a: Simple
    b: typing.List[Simple]
    c: typing.Dict[str, Simple]


def test_nested_dataclasses():
    a = Simple(1, 'a')
    b = [Simple(i, 'b') for i in range(3)]
    c = {'c': Simple(3, 'c')}
    _assert_serialization_deserialization(
        NestedDataClasses(a, b, c),
        expected_dict={
            'a': {'x': 1, 'y': 'a'},
            'b': [{'x': 0, 'y': 'b'}, {'x': 1, 'y': 'b'}, {'x': 2, 'y': 'b'}],
            'c': {'c': {'x': 3, 'y': 'c'}}
        },
        expected_json='{"a": {"x": 1, "y": "a"}, ' +
                      '"b": [{"x": 0, "y": "b"}, {"x": 1, "y": "b"}, {"x": 2, "y": "b"}], ' +
                      '"c": {"c": {"x": 3, "y": "c"}}}'
    )


@datamodel.datamodel
class WithDefaultValues:
    x: int
    y: int = 2


def test_from_dict_with_not_enough_values():
    assert WithDefaultValues(1) == WithDefaultValues.from_dict({'x': 1})


def test_that_extrafields_are_ignored():
    assert WithDefaultValues(1) == WithDefaultValues.from_dict({'x': 1, 'extra_field': 'foo bar'})


def test_custom_hooks_are_overwriten():
    default = datamodel._structure_hooks['str']

    @datamodel.structure_hook('str')
    def capitalize(v, _):
        return v.capitalize()

    a = Simple.from_dict({'x': 1, 'y': 'foo'})
    assert a.y == 'Foo'

    @datamodel.structure_hook('str')
    def take_first(v, _):
        return v[0]

    a = Simple.from_dict({'x': 1, 'y': 'foo'})
    assert a.y == 'f'

    datamodel._structure_hooks['str'] = default
    a = Simple.from_dict({'x': 1, 'y': 'foo'})
    assert a.y == 'foo'


CapitalStr = typing.NewType('CapitalStr', str)


@datamodel.datamodel
class WithCustomType:
    foo: str
    faa: CapitalStr


def test_custom_hooks_for_custom_defined_types():
    @datamodel.structure_hook('CapitalStr')
    def capitalize(v, _):
        return v.capitalize()

    a = WithCustomType.from_dict({'foo': 'monkey', 'faa': 'monkey'})
    assert a.foo == 'monkey'
    assert a.faa == 'Monkey'

    datamodel._structure_hooks.pop('CapitalStr')
    a = WithCustomType.from_dict({'foo': 'monkey', 'faa': 'monkey'})
    assert a.foo == 'monkey'
    assert a.faa == 'monkey'


@datamodel.datamodel
class PrimitiveValues:
    s: str
    i: int
    f: float
    c: complex
    bo: bool
    by: bytes


def test_primitive_values_from_dict():
    a = PrimitiveValues.from_dict({
        's': 123,
        'i': 1.45,
        'f': '123',
        'c': 2,
        'bo': 'foo bar',
        'by': 'foo',
    })
    expected = PrimitiveValues(
        s='123',
        i=1,
        f=123.0,
        c=(2+0j),
        bo=True,
        by=b'foo',
    )
    assert a == expected
    assert a == PrimitiveValues.from_json(expected.to_json())
