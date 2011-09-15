import os
import pwd
import sys


class Alias(object):
    _aliases = {}

    def __new__(cls, alias, func=None):
        # See if the alias already exists
        if alias in cls._aliases:
            # Replace the function
            obj = cls._aliases[alias]
            if func is not None:
                obj.func = func
            return obj

        # If func is not given, we were doing a lookup
        if func is None:
            # Return the default alias
            return cls._aliases[None]

        # OK, gotta allocate a new one
        obj = super(Alias, cls).__new__(cls)
        obj.alias = alias
        obj.func = func

        # Cache it
        cls._aliases[alias] = obj

        return obj

    def execute(self, ctx, sc_line):
        # Call the implementing function
        return self.func(ctx, sc_line)


def register(alias, func=None):
    # The actual decorator
    def decorator(the_func):
        Alias(alias, the_func)
        return the_func

    if callable(alias):
        # If alias is callable, we're used as "@register"
        func = alias
        alias = func.__name__
        if alias.startswith('do_'):
            alias = alias[3:]
        return decorator(func)
    elif func is not None:
        # If func is provided, we're used as "register(alias, func)"
        return decorator(func)

    # OK, we're used as "@register(alias)"
    return decorator


@register(None)
def default(ctx, sc_line):
    # Build the environment
    env = os.environ.copy()
    env.update(sc_line.vardict)
    subprocess.call(sc_line.args, env=env)


@register
def do_import(ctx, sc_line):
    # Sanity-check syntax
    if len(sc_line.args) != 2:
        raise SyntaxError('Invalid "import" statement; use as '
                          '"import <module>"')

    # Import the requested module; assume it uses @register
    __import__(sc_line.args[1])


@register
def do_from(ctx, sc_line):
    # Sanity-check syntax
    if (len(sc_line.args) not in (4, 6) or
        sc_line.args[2] != 'import' or
        (len(sc_line.args) == 6 and sc_line.args[4] != 'as')):
        raise SyntaxError('Invalid "from" statement; use as '
                          '"from <module> import <func> [as <alias>]"')

    # Alias the arguments for ease of usage
    module, func = sc_line.args[1], sc_line.args[3]
    alias = sc_line.args[5] if len(sc_line.args) == 6 else None

    # OK, let's pull in the module
    __import__(module)
    tmp = sys.modules[module]

    # Now, find the function
    for elem in func.split('.'):
        tmp = getattr(tmp, elem)

    # The final one must be a callable
    if not callable(tmp):
        raise ImportError("No such callable %s in module %s" %
                          (func, module))

    # Do we have an alias name?
    if alias is None:
        register(tmp)
    else:
        register(alias, tmp)


@register
def do_cd(ctx, sc_line):
    # Do we have a directory argument?
    directory = sc_line.args[1] if len(sc_line.args) > 1 else None

    # Default it as appropriate
    if directory is None:
        directory = os.environ.get('HOME')
    if directory is None:
        directory = pwd.getpwuid(os.getuid())[5]

    # Change to the indicated directory
    os.chdir(directory)


@register
def do_unset(ctx, sc_line):
    for varname in sc_line.args[1:]:
        # Safely unset variables from the environment
        if varname in os.environ:
            del os.environ[varname]


@register
def do_exit(ctx, sc_line):
    ctx.exit()


@register('.')
def do_source(ctx, sc_line):
    # Sanity-check syntax
    if len(sc_line.args) != 2:
        raise SyntaxError('Invalid "." statement; use as ". <file>"')

    ctx.push_file(sc_line.args[1])
