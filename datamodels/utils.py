import typing
from string import Template


_type_map = {
    str: 'str',
    int: 'int',
    float: 'float',
    complex: 'complex',
    bool: 'bool',
    bytes: 'bytes',
    None: 'None',
    type(None): 'None',
    ...: '...',
    typing.Any: 'Any',
}


def type_to_str(type_or_class: typing.Any) -> str:
    n = _type_map.get(type_or_class)
    if n:
        return n

    # case named class
    n = getattr(type_or_class, '__name__', None)
    if n:
        return n

    # case typing modules objects
    n = getattr(type_or_class, '_name', None)
    if n:
        if n == 'Callable' and type_or_class.__args__[0] != ...:
            # well, not relevant for this, but what the heck...
            # ofc someone might have some unstructure hook that then calculates the value
            return f'{n}[[{", ".join(type_to_str(i) for i in type_or_class.__args__[:-1])}], ' + \
                   f'{type_to_str(type_or_class.__args__[-1])}]'
        else:
            return f'{n}[{", ".join(type_to_str(i) for i in type_or_class.__args__)}]'

    origin_type = getattr(type_or_class, '__origin__', None)
    if origin_type == typing.Union:
        if len(type_or_class.__args__) == 2 and type_or_class.__args__[1] == type(None):  # noqa: E721
            return f'Optional[{type_to_str(type_or_class.__args__[0])}]'
        else:
            return f'Union[{", ".join(type_to_str(i) for i in type_or_class.__args__)}]'

    raise ValueError(f'Could not parse type representation for {type_or_class} of type: {type(type_or_class)}')


class MyValTemplate(Template):
    '''
    Related to code construction
    to construct dict comprehension strings with capability to call .format doesn't work
    so one cannot do:
    '{ k: iv for k, iv in {0}.items() }'.format('v')

    but instead one needs to do:
    'dict( (k, iv) for k, iv in {0}.items() )'.format('v')

    which is bad as dict() is way slower than dict comprehension

    So let's subclass string.Template and add format method to replce single value.
    That's enough as we always give only one arg to .format in expression builders.

    So we can use this insead:
    MyValTemplate('{ k: iv for k, iv in $MyVal.items() }').format('v')
    '''
    def format(self, myval):
        return self.substitute(MyVal=myval)
