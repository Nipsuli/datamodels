import copy
import json
import datetime
import typing
from typing import Callable, Dict, Any, TypeVar, Type, Union, NewType
from dataclasses import _is_dataclass_instance, fields, dataclass, is_dataclass, _set_new_attribute, _create_fn
from datamodel import utils


T = TypeVar('T')
V = TypeVar('V')

JSONstr = NewType('JSONstr', str)
ISO8601str = NewType('ISO8601str', str)

# admin
_json_encoder = json.JSONEncoder
_structure_hooks = {}
_unstructure_hooks = {}

_direct_through = {int, str, float, complex, bool, bytes, Any}


def set_json_encoder(json_encoder):
    global _json_encoder
    _json_encoder = json_encoder


def register_structure_hook(type_name_str, decoder):
    global _structure_hooks
    _structure_hooks[type_name_str] = decoder


def register_unstructure_hook(type_name_str, decoder):
    global _unstructure_hooks
    _unstructure_hooks[type_name_str] = decoder


def structure_hook(type_name_str: str):
    def wrapper(fn: Callable[[V, Type[T]], T]) -> Callable[[V, Type[T]], T]:
        register_structure_hook(type_name_str, fn)
        return fn
    return wrapper


def unstructure_hook(type_name_str: str):
    def wrapper(fn: Callable[[T], V]) -> Callable[[T], V]:
        register_unstructure_hook(type_name_str, fn)
        return fn
    return wrapper


# default hooks
@unstructure_hook('date')
@unstructure_hook('datetime')
def _unstructure_date_or_datetime(d: Union[datetime.date, datetime.datetime]) -> ISO8601str:
    return d.isoformat()


@unstructure_hook('complex')
def _to_str(v):
    return str(v)


@unstructure_hook('bytes')
def _byte_decode(v):
    return v.decode('utf-8')


@structure_hook('datetime')
def _structure_date(v: Union[datetime.datetime, str], t: Type[datetime.datetime]) -> datetime.datetime:
    if type(v) == datetime.datetime:
        return v
    elif type(v) == str:
        return utils.datetime_from_string(v)
    else:
        raise ValueError(f'Cannot parse {v} as datetime')


@structure_hook('date')
def _structure_datetime(v: Union[datetime.datetime, datetime.date, str], t: Type[datetime.date]) -> datetime.date:
    if type(v) == datetime.datetime:
        return v.date()
    elif type(v) == datetime.date:
        return v
    elif type(v) == str and v[4] == v[7] == '-':
        return datetime.date(int(v[:4]), int(v[5:7]), int(v[8:10]))
    else:
        raise ValueError(f'Cannot parse {v} as date')


@structure_hook('str')
@structure_hook('int')
@structure_hook('float')
@structure_hook('complex')
@structure_hook('bool')
@structure_hook('bytes')
def _structure_primitive(v, t):
    if t == bytes and type(v) == str:
        return t(v, 'utf8')
    return t(v)


@unstructure_hook('str')
@unstructure_hook('int')
@unstructure_hook('float')
@unstructure_hook('bool')
@structure_hook('Any')
@structure_hook('None')
def _direct_through(v, _=None):
    return v


def _structure_dataclass(t: Type[T], v: Dict[str, Any]) -> T:
    initkw = {}
    # to support case: from __future__ import annotations
    field_and_types = typing.get_type_hints(t)
    field_names = set(f.name for f in fields(t))  # just in case
    for field_name, field_type in field_and_types.items():
        if field_name in field_names and field_name in v:
            initkw[field_name] = _structure_value(field_type, v[field_name])

    return t(**initkw)


def _structure_value(t: Type[T], v: Any) -> T:
    hook = _structure_hooks.get(utils.type_to_str(t))
    if hook:
        return hook(v, t)
    elif is_dataclass(t):
        return _structure_dataclass(t, v)
    else:
        origin_type = getattr(t, '__origin__', None)
        if origin_type:
            if origin_type in {list, tuple}:
                return origin_type(_structure_value(t.__args__[0], iv) for iv in v)
            elif origin_type == dict:
                return {_structure_value(t.__args__[0], ik): _structure_value(t.__args__[1], iv)
                        for ik, iv in v.items()}
            elif origin_type == typing.Union:
                if len(t.__args__) == 2 and t.__args__[1] == type(None):  # noqa: E721: this is Optional[T]:
                    return _structure_value(t.__args__[0], v)
                else:
                    for t_arg in t.__args__:
                        try:
                            return _structure_value(t_arg, v)
                        except Exception:
                            pass
        else:
            # raise ValueError(f'Unhandled type: {t}')
            return v


def _build_from_dict(cls):
    field_and_types = typing.get_type_hints(cls)

    body_lines = []
    globals = {'_structure_hooks': _structure_hooks, 'cls': cls}

    for f in fields(cls):
        # have to check case:
        # * from __future__ import annotations
        # * custom defined classes
        # combination with late annotation etc
        type_str = utils.type_to_str(field_and_types[(f.name)])
        body_lines.append(f' {f.name}=_structure_hooks.get("{type_str}")(d["{f.name}"], {type_str}),\n')

    return _create_fn('from_dict_new',
                      ['cls', 'd'],
                      ['return cls(\n'] + body_lines + [')'],
                      globals=globals)


def _json_load(cls: Type[T], json_str: JSONstr) -> T:
    return cls.from_dict(json.loads(json_str))


def _json_dump(obj: T) -> JSONstr:
    return json.dumps(obj.to_serializeable(), cls=_json_encoder)


def _to_serializeable(obj, dict_factory=dict):
    # basically same as dataclasses._asdict_inner, but adds handling for custom un structure hooks
    hook = _unstructure_hooks.get(utils.type_to_str(type(obj)))
    if hook:
        return hook(obj)
    elif _is_dataclass_instance(obj):
        result = []
        for f in fields(obj):
            value = _to_serializeable(getattr(obj, f.name), dict_factory)
            result.append((f.name, value))
        return dict_factory(result)
    elif isinstance(obj, (list, tuple)):
        return type(obj)(_to_serializeable(v, dict_factory) for v in obj)
    elif isinstance(obj, dict):
        return type(obj)((_to_serializeable(k, dict_factory), _to_serializeable(v, dict_factory))
                         for k, v in obj.items())
    else:
        return copy.deepcopy(obj)


def datamodel(_cls=None, *, type_check=True, **dataclasskws):
    # TODO: implement type checker
    dataclasskws = {**{'frozen': True}, **dataclasskws}

    def wrapper(Cls):
        base = dataclass(**dataclasskws)(Cls)
        # never overwrite existing attribute
        _set_new_attribute(base, 'to_serializeable', _to_serializeable)
        _set_new_attribute(base, 'from_dict', classmethod(_structure_dataclass))
        _set_new_attribute(base, 'from_dict_new', classmethod(_build_from_dict(Cls)))
        _set_new_attribute(base, 'to_json', _json_dump)
        _set_new_attribute(base, 'from_json', classmethod(_json_load))
        return base

    # See if we're being called as @datamodel or @datamodel()
    if _cls is None:
        return wrapper
    else:
        return wrapper(_cls)
