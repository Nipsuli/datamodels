# Datamodel

Basically extension to python 3.7 dataclass, implements methods: `to_json`, `to_serializeable`, `from_dict` and `from_json` to the classes for (de)serialization. If one uses `datamodel` decorator with kwargs, those kwargs are passed to `dataclass`.

(De-)Serializes also `datetime.date` and `datetime.datetime` -objects. That step happens in `to_serializeable`, so it's safe to call `json.dumps` on dicts returned by `to_serializeable`. Basically `to_json` does just that. Also `from_json` is just `from_dict(json.loads(stuff))`.

In `from_dict` and `from_json` dates need to be ISO8601 formated strings so `YYYY-MM-DD` and datetimes  RFC3339 formated strings so `YYYY-MM-DDThh:mm:ss.msmsmsTZInfo` or `datetime` objects.

## Basic usage:

```python
import datetime
from typing import List
from dataclasses import is_dataclass
from datamodel import datamodel
from dateutil.tz import tzoffset


@datamodel
class A:
    x: int
    y: List[str]
    dt: datetime.datetime


a1 = A(1, ['a', 'b'], datetime.datetime(2018, 7, 2, 12, tzinfo=tzoffset(None, 0)))
json_str = a1.to_json()
a2 = A.from_json(json_str)

assert a1 == a2
assert is_dataclass(a1)
assert is_dataclass(a2)
assert json_str == '{"x": 1, "y": ["a", "b"], "dt": "2018-07-02T12:00:00+00:00"}'
```

## Structuring and unstructuring

`from_dict` tries it's best to structure objects, so if fields are missing from the dict, but the class has default values, not a problem. And if there are any extra fields, those are just ignored. Also default hooks for primitive types and date objects convert input values to correct type.

Supported types:
* Primitive values, `from_dict` runs them through the basic functions with same names
  * e.g. if type is `int` we call to the value `int(v)` when structuring
* `Any` just through and through to both directions
* `Optional`
* `Union[T0, T1, ...]`
  * `from_dict` tries to structure value in the order of the possible types and picks the first that runs without exception
* `List`
  * `from_dict` accepts any `Iterable`
* `Dict`
  * `from_dict` accepts any `Mapping`
* `Tuple`
  * `to_serializeable` converts into lists
* `dataclass` and `datamodel` instances
  * `dataclass` handling slower than `datamodel` as `datamodel`s have generated code for structuring
* `datetime.datetime` and `datetime.date`:
  * `to_serializeable` converts to ISO 8601 str
  * `from_dict` accepts ISO 8601 formatted str or `datetime.datetime`/`datetime.date` object and converts to correct type
* `Set` and `FrozenSet`
  * `to_serializeable` converts into lists
  * `from_dict` accepts any `Iterable`, and converts to `Set` / `Frozenset`


## Stucturing and unstructuring hooks

For missing types one can register custom (un)structuring functions with `structure_hook` and `unstructure_hook` decorators. One can override the default hooks as well. The argument to the hooks is basically the `__name__` attribute of the class. Check `test_type_to_str` for example cases.

```python
import typing
from datamodel import datamodel, structure_hook, unstructure_hook

class FooBar:
    pass


d = {'foo_bars': [<list of stuff>]}


@structure_hook('FooBar')
def my_foobar_from_raw_data(value):
    # this will be called on each element of the [<list of stuff>]
    pass


@unstructure_hook('FooBar')
def my_foobar_to_raw_data(value):
    pass


@datamodel
class FooBarContainer:
    foo_bars = typing.List[FooBar]

foo = FooBarContainer.from_dict(d)
foo_d = foo.to_serializeable()

# and if the functions are inverses
assert foo_d == d
```

The hooks need to be registered *before* the `datamodel` definition as the decorator builds custom code for structuring. So in the example above the built `from_dict` function for `FooBarContainer` is similar as:
```python
@dataclass
class FooBarContainer:
    foo_bars = typing.List[FooBar]

    @classmethod
    def from_dict(cls, d):
        return cls(
            foo_bars=list(my_foobar_from_raw_data(v) for v in d["foo_bars"])
        )

```

## Extensions

If one wants to have some default kwargs passed to `dataclass` decorator one can register functions with `datamodel.dataclass_kwargs_extension`. The decorated functions will receive all kwargs given to `datamodel` decorator and must return dict containing the new kwags.

There exists default extension `frozen` to make `datamodels` immutable by default. Same as decorating each class with `@datamodel(frozen=True)`

```python
import datamodel.extensions.frozen
from datamodel import datamodel

@datamodel
class Simple:
    x: int
    y: str


a = Simple(1, '2')
a.x = 2  # raises dataclasses.FrozenInstanceError

assert a.x == 1
assert a.y == '2'
```

## JSON encoder

One can set custom JSON encoder if one wants so. This one is passed to `json.dumps` as `cls` kwarg.

```python
class MyAwsomeJSONEncoder(json.JSONEncoder):
    # your special implementations
    pass

datamodel.set_json_encoder(MyAwsomeJSONEncoder)
```

## Tests

Using docker run test wathcer: `docker-compose run dev ptw -v`

And with flake8: `docker-compose run dev ptw -v -- --flake8`

Run coverage: `docker-compose run dev pytest -v --cov-report html --cov-report term:skip-covered --cov=datamodel/`

Otherwise pep8 but max line length is 120

## Todo
* package to pypi
* add CI
* create class extension possibility, type checker could be one of those


## Background
This package is based on ideas used in similar internal package at [PrompterAI](https://prompter.ai/). That one is based on the awesome [attrs](http://www.attrs.org/en/stable/) package and structuring and un-structuring is handled by [cattrs](https://github.com/Tinche/cattrs). In addition that one has runtime type checks implemented with [typeguard](https://github.com/agronholm/typeguard). Why runtime type checks you might ask? Simply: I do not trust external API's and even less people who write code on top of those API's, least my self.

Naturally that one had little bit more of functionalities as it was based on `attrs`, but I feel that `dataclass` provides enough functionalities for most cases, and it's standard library. Decided to build this one from scratch, instead of just publishing the PrompterAI `datamodel` module as that one also relied on other internal modules, example for `datetime` handling.

There exists also [dataclasses-json](https://github.com/lidatong/dataclasses-json) package. But it doesn't seem to handle `datetimes` (at the time of writing) and it's not that extendable. Also I just don't like that one needs to inherit from the `DataClassJsonMixin`.

About the extendability, I really like the possibility in `cattrs` to add custom hooks with `register_unstructure_hook` and `register_structure_hook` which I'm bit trying to mimic with the `structure_hook` and `unstructure_hook` decorators.
