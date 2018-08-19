import copy
import json
import datetime
import typing
from functools import partial
from typing import Callable, Dict, Any, TypeVar, Type, Union
from dataclasses import (_is_dataclass_instance, fields, dataclass, is_dataclass, _set_new_attribute, _create_fn,
                         _MISSING_TYPE)
from datamodel import utils


T = TypeVar('T')
V = TypeVar('V')

JSONstr = str
ISO8601str = str

# admin
_json_encoder = json.JSONEncoder
_structure_hooks = {}
_unstructure_hooks = {}
_dataclass_kwargs_extensions = []


def is_datamodel(obj):
    return is_dataclass(obj) and hasattr(obj, 'to_serializeable') and hasattr(obj, 'from_dict')


def set_json_encoder(json_encoder):
    global _json_encoder
    _json_encoder = json_encoder


def _register_structure_hook(type_name_str, decoder):
    global _structure_hooks
    _structure_hooks[type_name_str] = decoder


def _register_unstructure_hook(type_name_str, decoder):
    global _unstructure_hooks
    _unstructure_hooks[type_name_str] = decoder


def register_dataclass_kwargs_fn(fn):
    global _dataclass_kwargs_extensions
    _dataclass_kwargs_extensions.append(fn)


def structure_hook(type_name_str: str):
    def wrapper(fn: Callable[[V], T]) -> Callable[[V], T]:
        _register_structure_hook(type_name_str, fn)
        return fn
    return wrapper


def unstructure_hook(type_name_str: str):
    def wrapper(fn: Callable[[T], V]) -> Callable[[T], V]:
        _register_unstructure_hook(type_name_str, fn)
        return fn
    return wrapper


def dataclass_kwargs_extension(fn):
    register_dataclass_kwargs_fn(fn)
    return fn


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
def _structure_date(v: Union[datetime.datetime, str]) -> datetime.datetime:
    if type(v) == datetime.datetime:
        return v
    elif type(v) == str:
        return utils.datetime_from_string(v)
    else:
        raise ValueError(f'Cannot parse {v} as datetime')


@structure_hook('date')
def _structure_datetime(v: Union[datetime.datetime, datetime.date, str]) -> datetime.date:
    if type(v) == datetime.datetime:
        return v.date()
    elif type(v) == datetime.date:
        return v
    elif type(v) == str and v[4] == v[7] == '-':
        return datetime.date(int(v[:4]), int(v[5:7]), int(v[8:10]))
    else:
        raise ValueError(f'Cannot parse {v} as date')


@structure_hook('bytes')
def _structure_bytes(v):
    if type(v) == str:
        return bytes(v, 'utf8')
    else:
        return bytes(v)


# strcutring
def _structure_value(t: Type[T], v: Any) -> T:
    type_str = utils.type_to_str(t)
    hook = _structure_hooks.get(type_str)
    if hook:
        return hook(v)
    elif _is_direct_through_structure_type(type_str):
        return v
    elif _is_convert_with_type_str_structure_type(type_str):
        return eval(type_str)(v)
    elif is_dataclass(t):
        return _structure_dataclass(t, v)
    else:
        origin_type = getattr(t, '__origin__', None)
        if origin_type:
            if origin_type in {list, tuple, set, frozenset}:
                return origin_type(_structure_value(t.__args__[0], iv) for iv in v)
            elif origin_type == dict:
                return {_structure_value(t.__args__[0], ik): _structure_value(t.__args__[1], iv)
                        for ik, iv in v.items()}
            elif origin_type == typing.Union:
                if len(t.__args__) == 2 and t.__args__[1] == type(None):  # noqa: E721: this is Optional[T]:
                    return _structure_value(t.__args__[0], v)
                else:
                    return _structure_union(t, v)
            else:
                raise ValueError(f'No origin_type handler for type: {type_str}')
        else:
            raise ValueError(f'No structure hook for type: {type_str}')


def _structure_dataclass(t: Type[T], v: Dict[str, Any]) -> T:
    initkw = {}
    field_and_types = typing.get_type_hints(t)
    field_names = set(f.name for f in fields(t))  # just in case
    for field_name, field_type in field_and_types.items():
        if field_name in field_names and field_name in v:
            initkw[field_name] = _structure_value(field_type, v[field_name])

    return t(**initkw)


def _structure_union(t: Type[T], v: Any) -> T:
    for t_arg in t.__args__:
        try:
            return _structure_value(t_arg, v)
        except Exception:
            pass

    raise ValueError(f'Could not structure type: {utils.type_to_str(t)} from value: {v}')


def _is_direct_through_structure_type(type_str):
    return type_str in {'None', 'Any'}


def _is_convert_with_type_str_structure_type(type_str):
    return type_str in {'str', 'int', 'float', 'complex', 'bool'}


def _gen_structure_fn(t: Type[T], globs) -> Callable[[V], T]:
    type_str = utils.type_to_str(t)
    if _structure_hooks.get(type_str):
        globs[f'structure_{type_str}'] = _structure_hooks.get(type_str)  # nasty mutation, shame on me
        return f'structure_{type_str}'
    elif _is_direct_through_structure_type(type_str):
        return ''
    elif _is_convert_with_type_str_structure_type(type_str):
        return f'{type_str}'
    elif is_datamodel(t):
        globs[t.__name__] = t  # nasty mutation, shame on me
        return f'{t.__name__}.from_dict'
    elif is_dataclass(t):
        return f'(lambda v: _structure_dataclass({t.__name__}, v))'
    else:
        origin_type = getattr(t, '__origin__', None)
        if origin_type:
            if origin_type in {list, set, frozenset}:
                value_fn = _gen_structure_fn(t.__args__[0], globs)
                return f'(lambda v: {utils.type_to_str(origin_type)}({value_fn}(iv) for iv in v))'
            elif origin_type == dict:
                key_fn = _gen_structure_fn(t.__args__[0], globs)
                value_fn = _gen_structure_fn(t.__args__[1], globs)
                return f'(lambda v: {{{key_fn}(k): {value_fn}(iv) for k, iv in v.items()}})'
            elif origin_type == tuple:
                if len(t.__args__) > 1 and t.__args__[1] == ...:  # tuple of any length Tuple[Any, ...]
                    return f'(lambda v: tuple({_gen_structure_fn(t.__args__[0], globs)}(iv) for iv in v))'
                else:  # fixed length tuple, e.g.: Tuple[str, int, str]
                    builder = ','.join([f'{_gen_structure_fn(it, globs)}(v[{i}])' for i, it in enumerate(t.__args__)])
                    return f'(lambda v: ({builder},))'
            elif origin_type == typing.Union:
                if len(t.__args__) == 2 and t.__args__[1] == type(None):  # noqa: E721: this is Optional[T]:
                    return f'(lambda v: None if v is None else {_gen_structure_fn(t.__args__[0], globs)}(v))'
                else:
                    # this is bit slower, but well, that's what you get for using Union
                    fname = f'stucture_{type_str}'.replace(' ', '').replace(']', '').replace('[', '_').replace(',', '')
                    globs[fname] = partial(_structure_union, t)
                    return f'{fname}'
            else:
                raise ValueError(f'No origin_type handler for type: {origin_type}')
        else:
            raise ValueError(f'No structure hook function for type: {type_str}')


def _build_from_dict(cls: Type[T]) -> Callable[[Type[T], Dict[str, Any]], T]:
    field_and_types = typing.get_type_hints(cls)

    body_lines = []
    globs = {
        'cls': cls,
        # no code building for these
        '_structure_dataclass': _structure_dataclass,
        '_structure_value': _structure_value,
        '_structure_union': _structure_union,
    }

    for f in fields(cls):
        if f.init:
            t = field_and_types[(f.name)]
            if is_dataclass(t):
                globs[t.__name__] = t
            if not isinstance(f.default, _MISSING_TYPE):
                globs[f'{f.name}_default'] = f.default
                value_getter = f'd.get("{f.name}", {f.name}_default)'
            elif not isinstance(f.default_factory, _MISSING_TYPE):
                globs[f'{f.name}_default_factory'] = f.default_factory
                value_getter = f'd.get("{f.name}", {f.name}_default_factory())'
            else:
                value_getter = f'd["{f.name}"]'
            body_lines.append(f' {f.name}={_gen_structure_fn(t, globs)}({value_getter}),\n')

    return _create_fn('from_dict',
                      ['cls', 'd'],
                      ['return cls(\n'] + body_lines + [')'],
                      globals=globs)


# un structuring
def _to_serializeable(obj):
    hook = _unstructure_hooks.get(utils.type_to_str(type(obj)))
    if hook:
        return copy.deepcopy(hook(obj))
    elif _is_direct_through_unstructure_type(utils.type_to_str(type(obj))):
        return copy.deepcopy(obj)
    elif _is_dataclass_instance(obj):
        return {f.name: _to_serializeable(getattr(obj, f.name)) for f in fields(obj)}
    elif isinstance(obj, dict):
        return {_to_serializeable(k): _to_serializeable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set, frozenset)):
        return [_to_serializeable(v) for v in obj]
    else:
        raise ValueError(f'No unstructure hook for type: {type(obj)}')


def _is_direct_through_unstructure_type(type_str):
    return type_str in {'str', 'int', 'float', 'bool', 'None', 'Any'}


def _gen_unstructure_expression(t, globs):
    # retrurns str with '{}' so that callers can call
    # return_str.format(<value expression>)
    type_str = utils.type_to_str(t)
    if _unstructure_hooks.get(type_str):
        globs[f'unstructure_{type_str}'] = _unstructure_hooks.get(type_str)  # nasty mutation, shame on me
        return f'unstructure_{type_str}({{}})'
    elif _is_direct_through_unstructure_type(type_str):
        return '{}'
    elif is_datamodel(t):
        globs[t.__name__] = t  # nasty mutation, shame on me
        return '{}.to_serializeable()'
    elif is_dataclass(t):
        return '_to_serializeable({})'
    else:
        origin_type = getattr(t, '__origin__', None)
        if origin_type:
            if origin_type == dict:
                key_expr = _gen_unstructure_expression(t.__args__[0], globs).format("k")
                value_expr = _gen_unstructure_expression(t.__args__[1], globs).format("iv")
                return f'dict(({key_expr}, {value_expr}) for k, iv in {{}}.items())'
            elif origin_type in {list, tuple, set, frozenset}:
                value_expr = _gen_unstructure_expression(t.__args__[0], globs).format("iv")
                return f'[{value_expr} for iv in {{}}]'
            elif origin_type == typing.Union:
                if len(t.__args__) == 2 and t.__args__[1] == type(None):  # noqa: E721: this is Optional[T]:
                    value_expr = _gen_unstructure_expression(t.__args__[0], globs).replace('{}', '{0}')
                    return f'(None if {{0}} is None else {value_expr})'
                else:
                    return '_to_serializeable({})'
        else:
            raise ValueError(f'No unstructure hook function for type: {type_str}')


def _build_to_serializeable(cls: Type[T]) -> Callable[[T], Dict[str, Any]]:
    field_and_types = typing.get_type_hints(cls)
    body_lines = []
    globs = {
        '_to_serializeable': _to_serializeable
    }

    for f in fields(cls):
        # perhaps could have some mechanism for optionally filtering fields out
        t = field_and_types[(f.name)]
        get_attribute_str = f'self.{f.name}'
        body_lines.append(f' "{f.name}": {_gen_unstructure_expression(t, globs).format(get_attribute_str)},\n')

    return _create_fn('to_serializeable',
                      ['self'],
                      ['return {'] + body_lines + ['}'],
                      globals=globs)


def _json_load(cls: Type[T], json_str: JSONstr) -> T:
    return cls.from_dict(json.loads(json_str))


def _json_dump(obj: T) -> JSONstr:
    return json.dumps(obj.to_serializeable(), cls=_json_encoder)


_allowed_dataclasskws = ['init', 'repr', 'eq', 'order', 'unsafe_hash', 'frozen']


def datamodel(_cls=None, **kwargs):
    for fn in _dataclass_kwargs_extensions:
        kwargs = fn(kwargs)

    def wrapper(Cls):
        base = dataclass(**{k: v for k, v in kwargs.items() if k in _allowed_dataclasskws})(Cls)
        # never overwrite existing attribute
        _set_new_attribute(base, 'to_serializeable', _build_to_serializeable(Cls))
        _set_new_attribute(base, 'from_dict', classmethod(_build_from_dict(Cls)))
        _set_new_attribute(base, 'to_json', _json_dump)
        _set_new_attribute(base, 'from_json', classmethod(_json_load))
        return base

    # See if we're being called as @datamodel or @datamodel()
    if _cls is None:
        return wrapper
    else:
        return wrapper(_cls)
