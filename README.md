# Datamodel

Basically extension to python 3.7 dataclass, implements methods: `to_json`, `to_serializeable`, `from_dict` and `from_json` to the classes for (de)serialization. Thinking also optional run time type checks. Also sets by default `frozen=True` for `dataclass`. If one uses `datamodel` decorator with args, those args are passed to `dataclass`.

(De-)Serializes also `datetime.date` and `datetime.datetime` -objects. That step happens in `to_serializeable`, so it should be safe to call `json.dumps` on dicts returned by `to_serializeable`. Basically `to_json` does just that. Also `from_json` is just `from_dict(json.loads(stuff))`.

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

`from_dict` tries it's best to structure objects, so if fields are missing from the dict, but the class has default values, no problemo. And if there are any extra fields, those are just ignored.

Supported:
* Primitive values, `from_dict` runs them through the basic functions with same names
* `Any` just through and through to both directions
* `Optional`
* `Union[T0, T1, ...]`: in `from_dict` tries in to structure in the order of the possible values
* `List`
* `Dict`
* `Tuple`
* `dataclass` instances
* `datetime.datetime` and `datetime.date`:
  * `to_serializeable` converts to ISO 8601 str
  * `from_dict` accepts ISO 8601 formatted str or `datetime.datetime` (`datetime.date`) and converts to correct type
* `Set` and `FrozenSet` (TODO)
  * `to_serializeable` converts into lists
  * `from_dict` accepts also lists, which are converted to `Set` / `Frozenset`

For missing types one can also register custom functions with `structure_hook` and `unstructure_hook` decorators. Check `test_type_to_str` for examples of type str formatting.

```python
import typing
from datamodel import datamodel, structure_hook, unstructure_hook

class FooBar:
    pass


@datamodel
class FooBarContainer:
    foo_bars = typing.List[FooBar]


d = {'foo_bars': [<list of stuff>]}


@structure_hook('List[Foobar]')
def my_foobar_list_from_raw_data(type_, value):
    # the 'type_' will be typing.List[Foobar]
    # the 'value' will be [<list of stuff>]
    pass

@unstructure_hook('List[Foobar]')
def my_foobar_list_to_raw_data(value):
    # the value will be List[FooBar]
    pass

foo = FooBarContainer.from_dict(d)
foo_d = foo.to_serializeable()

# and if the functions are inverses
assert foo_d == d
```

## JSON encoder

One can set custom JSON encoder, the default encoder encodes `datetime.datetime` and `datetime.date` objects as well

```python
class MyAwsomeJSONEncoder(json.JSONEncoder):
    # your special implementations
    pass

datamodel.set_json_encoder(MyAwsomeJSONEncoder)
```

## Tests

Using docker run test wathcer: `docker-compose run dev ptw -v`
And with flake8: `docker-compose run dev ptw -v -- --flake8`

Otherwise pep8 but max line length is 120

## Todo / Ideas
* package to pypi
* add CI
* optional run time type checks (perhaps)
* create extension possibility, type checker could be one of those
* Create code for structuring and un structuring?


## Background
This package is based on ideas used in similar internal package at [PrompterAI](https://prompter.ai/). That one is based on the awesome [attrs](http://www.attrs.org/en/stable/) package and structuring and un-structuring is handled by [cattrs](https://github.com/Tinche/cattrs). In addition that one has runtime type checks implemented with [typeguard](https://github.com/agronholm/typeguard). Why you might ask? Simply: I do not trust external API's and even less people who write code on top of those API's (least my self).

Naturally that one had little bit more of functionalities as it was based on `attrs`, but I feel that `dataclass` provides enough functionalities for most cases, and it's standard library. Decided to build this one from scratch, instead of just publishing the PrompterAI `datamodel` module as that one also relied on other internal packages example in `datetime` handling.

There exists also [dataclasses-json](https://github.com/lidatong/dataclasses-json) package. But it doesn't seem to handle `datetimes` (at the time of writing) and it's not that extendable. Also I just don't like that one needs to inherit from the `DataClassJsonMixin`.

About the extendability, I really like the possibility in `cattrs` to add custom hooks with `register_unstructure_hook` and `register_structure_hook` which I'm bit trying to mimic with the `structure_hook` and `unstructure_hook` decorators.
