import collections
import os
import pwd
import readline
import shlex
import string
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

    def __call__(self, ctx, sc_line):
        # Call the implementing function
        self.func(ctx, sc_line)


class ScriptLine(object):
    @staticmethod
    def _subst(text, substs):
        # Start off with $ substitutions
        tmp = string.Template(text).substitute(substs)

        # Perform tilde expansion
        if tmp and tmp[0] == '~':
            tmp = os.path.expanduser(tmp)

        return tmp

    def __init__(self, fname, lno, line):
        self.fname = fname
        self.lno = lno
        self.raw = line.strip()

        # Start from the raw input
        line = self.raw()

        # Inhibit output?
        if line[0] == '!':
            self.output = False
            line = line[1:]
        else:
            self.output = True

        # Identify the line
        if lno == 1 and line[0:2] == '#!':
            self.type = 'comment'
            self.subtype = 'script'
        elif line[0:2] == '##':
            self.type = 'comment'
            self.subtype = 'invisible'
        elif line[0] == '#':
            self.type = 'comment'
            self.subtype = 'comment'
        elif not line:
            self.type = 'pause'
            self.subtype = None
        else:
            self.type = 'command'
            self.subtype = None

        # OK, if it's not a command, let's stop here
        if self.type != 'command':
            self.vardict = None
            self.args = None
            return

        # OK, break down and process the command
        args = shlex.split(line)

        # Get substitutions dictionary
        subst_dict = collections.defaultdict(lambda: '')
        subst_dict.update(os.environ)

        # Handle export command specially
        if args[0] == 'export':
            self.type = 'export'
            args.pop(0)

        # Process the variable dictionary
        self.vardict = {}
        while args and '=' in args[0]:
            name, value = args.pop(0).split('=', 1)
            value = subst(value, subst_dict)
            subst_dict[name] = value
            self.vardict[name] = value

        # Was that all the arguments?
        if not args:
            self.type = 'export'

        # Save the arguments
        self.args = args


def scriptfile(fname):
    lno = 0
    with open(fname, 'r') as f:
        for line in f:
            # Track the line number
            lno += 1

            # Parse the line
            sc_line = ScriptLine(fname, lno, line)

            # Add the line to the history
            if sc_line.type in ('command', 'export'):
                readline.add_history(sc_line.raw)

            # Yield the line
            yield sc_line


class Script(object):
    def __init__(self, fname, outfile=None):
        self.exit_flag = False
        self.filestack = [iter(scriptfile(fname))]

        # Was outfile specified?
        self.outfile = None if outfile is None else open(outfile, 'w')

    def exit(self):
        # Exit the interpreter on the next statement
        self.exit_flag = True

    def push_file(self, fname):
        # Push another file to process
        self.filestack.append(iter(scriptfile(fname)))

    def iter_lines(self):
        while self.filestack:
            try:
                # Yield the next line
                yield next(self.filestack[-1])
            except StopIteration:
                self.filestack.pop(-1)


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
