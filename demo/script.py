import collections
import os
import readline
import shlex
import string

from demo import aliases


class PauseCommand(Exception):
    pass


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
        while args and ('=' in args[0] or self.type == 'export'):
            if '=' not in args[0]:
                args.pop(0)
                continue
            name, value = args.pop(0).split('=', 1)
            value = subst(value, subst_dict)
            subst_dict[name] = value
            self.vardict[name] = value

        # Was that all the arguments?
        if not args:
            self.type = 'export'

        # Save the arguments
        self.args = args

    def __str__(self):
        return self.raw

    def execute(self, ctx):
        # There are only a handful of types we can handle here...
        if self.type == 'comment':
            return
        elif self.type == 'pause':
            # Has to be handled at a level above us
            raise PauseCommand()
        elif self.type == 'export':
            # Just updating the environment
            os.environ.update(self.vardict)
            return

        # OK, let's suck in and execute the appropriate command
        alias = aliases.Alias(self.args[0])
        return alias.execute(ctx, self)


def scriptfile(fname):
    lno = 0
    # Ignore leading blank lines that would be treated as pauses
    inhibit_pause = True
    with open(fname, 'r') as f:
        for line in f:
            # Track the line number
            lno += 1

            # Parse the line
            sc_line = ScriptLine(fname, lno, line)

            # Process pauses
            if sc_line.type == 'pause':
                if inhibit_pause:
                    # Apply pause inhibition
                    continue

                # Inhibit future pausing
                inhibit_pause = True
            else:
                # Not inhibiting any more pauses
                inhibit_pause = False

            # Add the line to the history
            if sc_line.type in ('command', 'export'):
                readline.add_history(sc_line.raw)

            # Yield the line
            yield sc_line


class Script(object):
    def __init__(self, fname, outfile=None, prompt='[%(nextcmd)s]> '):
        self.exit_flag = False
        self.filestack = [iter(scriptfile(fname))]

        # Was outfile specified?
        self.outfile = None if outfile is None else open(outfile, 'w')

        # Save the prompt template
        self.prompt_tmpl = prompt

        # stdin line number
        self.in_lno = 1

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

    def read_input(self):
        # Helper to generate the prompt
        def get_input():
            lno = self.in_lno
            nextcmd = readline.get_current_history_length() + 1
            currdir = os.getcwd()

            return raw_input(self.prompt_tmpl % locals()).strip()

        line = get_input()
        while line:
            # Need the line number...
            tmp_lno = self.in_lno
            self.in_lno += 1

            # Parse the line
            yield ScriptLine('-', in_lno, line)

            # Get the next line
            line = get_input()
