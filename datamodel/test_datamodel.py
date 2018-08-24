import dataclasses
import datetime
import typing
import pytest
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
        (datetime.datetime, 'datetime'),
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


def test_simple_model_serialization_converts_basic_types():
    dm = Simple.from_dict({'x': '1', 'y': 2})
    assert dm.x == 1
    assert dm.y == '2'


@datamodel.datamodel
class WithDates:
    d: datetime.date
    dt: datetime.datetime


def test_datetime_serialization_deserialization():
    dt = datetime.datetime.now()
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
    dm = NestedDataClasses(a, b, c)
    assert isinstance(dm.a, Simple)
    assert all(isinstance(v, Simple) for v in dm.b)
    assert all(isinstance(v, Simple) for v in dm.c.values())
    _assert_serialization_deserialization(
        dm,
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
class NestedDataClassesList:
    a: typing.List[Simple]


def test_nested_dataclasses_dataclass_only_in_nested_field():
    d = {'a': [{'x': 0, 'y': 'b'}, {'x': 1, 'y': 'b'}, {'x': 2, 'y': 'b'}]}
    dm = NestedDataClassesList.from_dict(d)
    assert all(isinstance(v, Simple) for v in dm.a)
    _assert_serialization_deserialization(
        dm,
        expected_dict=d,
        expected_json='{"a": [{"x": 0, "y": "b"}, {"x": 1, "y": "b"}, {"x": 2, "y": "b"}]}'
    )


@datamodel.datamodel
class WithDefaultValues:
    x: int
    y: int = 2
    z: typing.List[int] = dataclasses.field(default_factory=list)


def test_from_dict_with_not_enough_values_only_required():
    assert WithDefaultValues(1, 2, []) == WithDefaultValues.from_dict({'x': 1})


def test_from_dict_fails_for_missing_values_with_no_default():
    with pytest.raises(KeyError):
        WithDefaultValues.from_dict({'y': 1})


def test_from_dict_with_not_enough_values_single_value_missing():
    assert WithDefaultValues(1, 2, [1, 2]) == WithDefaultValues.from_dict({'x': 1, 'z': [1, 2]})


def test_from_dict_with_not_enough_values_collection_value_missing():
    assert WithDefaultValues(1, 3, []) == WithDefaultValues.from_dict({'x': 1, 'y': 3})


def test_that_extrafields_are_ignored():
    assert WithDefaultValues(1, 1, []) == WithDefaultValues.from_dict({'x': 1, 'y': 1, 'extra_field': 'foo bar'})


class Foo:
    pass


@datamodel.datamodel
class AnyContainer:
    a: typing.Any


def test_any_goes_through_both_ways():
    foo = Foo()
    dm = AnyContainer.from_dict({'a': foo})
    assert dm.a == foo


def test_hooks_can_overwrite():
    @datamodel.structure_hook('str')
    def capitalize(v):
        return v.capitalize()

    @datamodel.datamodel
    class Simple:
        x: int
        y: str

    a = Simple.from_dict({'x': 1, 'y': 'foo'})
    assert a.y == 'Foo'

    @datamodel.structure_hook('str')
    def take_first(v):
        return v[0]

    @datamodel.datamodel
    class Simple:
        x: int
        y: str

    a = Simple.from_dict({'x': 1, 'y': 'foo'})
    assert a.y == 'f'

    datamodel._structure_hooks.pop('str')

    @datamodel.datamodel
    class Simple:
        x: int
        y: str

    a = Simple.from_dict({'x': 1, 'y': 'foo'})
    assert a.y == 'foo'


CapitalStr = typing.NewType('CapitalStr', str)


def test_custom_hooks_for_custom_defined_types():
    # one needs to define both
    @datamodel.structure_hook('CapitalStr')
    @datamodel.unstructure_hook('CapitalStr')
    def capitalize(v):
        return v.capitalize()

    @datamodel.datamodel
    class WithCustomType:
        foo: str
        faa: CapitalStr

    a = WithCustomType.from_dict({'foo': 'monkey', 'faa': 'monkey'})
    assert a.foo == 'monkey'
    assert a.faa == 'Monkey'
    datamodel._structure_hooks.pop('CapitalStr')


def test_custom_hooks_are_required_for_custom_defined_types():

    with pytest.raises(ValueError) as e:
        @datamodel.datamodel
        class WithCustomType:
            foo: str
            faa: CapitalStr

    assert 'No structure hook function for type: CapitalStr' in str(e)


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


@datamodel.datamodel
class WithSets:
    a: typing.Set[int]
    b: typing.FrozenSet[int]


def test_stucturing_sets():
    d = {'a': {1, 2}, 'b': frozenset({4, 5})}
    dm = WithSets.from_dict(d)
    assert dm.a == {1, 2}
    assert dm.b == frozenset({4, 5})


def test_structuring_sets_from_other_iterables():
    d = {'a': range(3), 'b': [5, 6]}
    dm = WithSets.from_dict(d)
    assert dm.a == {0, 1, 2}
    assert dm.b == frozenset({5, 6})


@datamodel.datamodel
class WithTuples:
    a: typing.Tuple[int, ...]
    b: typing.Tuple[int, str, str]
    c: typing.Tuple[str]


def test_structuring_tuples_from_tuples():
    d = {'a': (1, 2, 3), 'b': (4, 'a', 'b'), 'c': (1,)}
    dm = WithTuples.from_dict(d)
    assert dm.a == (1, 2, 3)
    assert dm.b == (4, 'a', 'b')
    assert dm.c == ('1',)
    _assert_serialization_deserialization(
        dm,
        expected_dict={'a': [1, 2, 3], 'b': [4, 'a', 'b'], 'c': ['1']},
        expected_json='{"a": [1, 2, 3], "b": [4, "a", "b"], "c": ["1"]}'
    )


def test_structuring_tuples_from_other_iterables():
    d = {'a': range(3), 'b': [4, 'a', 'b'], 'c': [1]}
    dm = WithTuples.from_dict(d)
    assert dm.a == (0, 1, 2)
    assert dm.b == (4, 'a', 'b')
    assert dm.c == ('1',)
    _assert_serialization_deserialization(
        dm,
        expected_dict={'a': [0, 1, 2], 'b': [4, 'a', 'b'], 'c': ['1']},
        expected_json='{"a": [0, 1, 2], "b": [4, "a", "b"], "c": ["1"]}'
    )


@datamodel.datamodel
class WithNoInit:
    a: int
    b: int = dataclasses.field(init=False, default=2)
    c: int = dataclasses.field(init=False, default_factory=lambda: 3)


def test_no_init_values():
    d = {'a': 4}
    dm = WithNoInit.from_dict(d)
    assert dm.a == 4
    assert dm.b == 2
    assert dm.c == 3


@datamodel.datamodel
class WithOptional:
    x: typing.Optional[int]


def test_structure_optional():
    d = {'x': 1}
    dm = WithOptional.from_dict(d)
    assert dm.x == 1
    _assert_serialization_deserialization(
        dm,
        expected_dict=d,
        expected_json='{"x": 1}'
    )
    d = {'x': None}
    dm = WithOptional.from_dict(d)
    assert dm.x is None
    _assert_serialization_deserialization(
        dm,
        expected_dict=d,
        expected_json='{"x": null}'
    )


@datamodel.datamodel
class WithOptionalObject:
    x: typing.Optional[Simple]


def test_structure_optional_with_object():
    d = {'x': {'x': 1, 'y': '2'}}
    dm = WithOptionalObject.from_dict(d)
    assert isinstance(dm.x, Simple)
    _assert_serialization_deserialization(
        dm,
        expected_dict=d,
        expected_json='{"x": {"x": 1, "y": "2"}}'
    )
    d = {'x': None}
    dm = WithOptionalObject.from_dict(d)
    assert dm.x is None
    _assert_serialization_deserialization(
        dm,
        expected_dict=d,
        expected_json='{"x": null}'
    )


@datamodel.datamodel
class WithUnion:
    x: typing.Union[int, str]


def test_stucture_union():
    d = {'x': 1}
    dm = WithUnion.from_dict(d)
    assert dm.x == 1
    _assert_serialization_deserialization(
        dm,
        expected_dict=d,
        expected_json='{"x": 1}'
    )
    d = {'x': 'asdf'}
    dm = WithUnion.from_dict(d)
    assert dm.x == 'asdf'
    _assert_serialization_deserialization(
        dm,
        expected_dict=d,
        expected_json='{"x": "asdf"}'
    )


@datamodel.datamodel
class WithUnion2:
    x: typing.Union[int, float]


def test_structure_union_fails():
    d = {'x': '1'}
    dm = WithUnion2.from_dict(d)
    assert dm.x == 1
    d = {'x': 'adsf'}
    with pytest.raises(ValueError) as e:
        dm = WithUnion2.from_dict(d)
    assert 'Could not structure type: Union[int, float] from value: adsf' in str(e)


@dataclasses.dataclass
class InnerDataClass:
    x: int
    y: str
    dt: datetime.datetime
    l: typing.List[int]


@datamodel.datamodel
class DataClassContainer:
    dc: InnerDataClass
    dcl: typing.List[InnerDataClass]


def test_structuring_of_inner_dataclasses():
    dt = datetime.datetime.now()
    dc = {'x': 1, 'y': 'a', 'dt': dt, 'l': [1, 2]}
    d = {'dc': dc, 'dcl': [dc]}
    dm = DataClassContainer.from_dict(d)
    assert dm.dc == InnerDataClass(**dc)
    assert dm.dcl == [InnerDataClass(**dc)]
    dc_dict = {'x': 1, 'y': 'a', 'dt': dt.isoformat(), 'l': [1, 2]}
    dc_json = f'{{"x": 1, "y": "a", "dt": "{dt.isoformat()}", "l": [1, 2]}}'
    _assert_serialization_deserialization(
        dm,
        expected_dict={'dc': dc_dict, 'dcl': [dc_dict]},
        expected_json=f'{{"dc": {dc_json}, "dcl": [{dc_json}]}}'
    )
