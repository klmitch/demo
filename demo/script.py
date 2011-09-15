import collections
import os
import readline
import shlex
import string
import sys
import traceback

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
        line = self.raw

        # Inhibit output?
        if line and line[0] == '!':
            self.output = False
            line = line[1:]
        else:
            self.output = True

        # Identify the line
        if lno == 1 and line[0:2] == '#!':
            self.type = 'comment'
            self.output = False
        elif line[0:2] == '##':
            self.type = 'comment'
            self.output = False
        elif line and line[0] == '#':
            self.type = 'comment'

            # Take out leading '!'
            if not self.output:
                self.raw = line

            self.output = True
        elif not line:
            self.type = 'pause'
            self.output = False
        else:
            self.type = 'command'

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


class Script(object):
    def __init__(self, opts):
        self.opts = opts
        self.exit_flag = False

        # Set up the filestack
        self.filestack = []
        self.empty = False
        for fname in reversed(opts.files):
            if fname == '-':
                self.filestack.append((False, iter(self._read_input())))
            else:
                self.filestack.append((True, iter(self._read_file(fname))))

        # Was outfile specified?
        self.outfile = None if opts.output is None else open(opts.output, 'w')

        # Save the prompt template
        self.prompt_tmpl = opts.prompt

        # stdin line number
        self.in_lno = 1

    def exit(self):
        # Exit the interpreter on the next statement
        self.exit_flag = True

    def push_file(self, fname):
        # Push another file to process
        self.filestack.append((True, iter(self._read_file(fname))))

    def _prompt(self, input_prompt=False):
        nextcmd = readline.get_current_history_length() + int(input_prompt)
        currdir = os.getcwd()

        return self.prompt_tmpl % locals()

    def _iter_lines(self):
        while self.filestack:
            try:
                # Yield the next line
                yield (self.filestack[-1][0], next(self.filestack[-1][1]))
            except StopIteration:
                self.filestack.pop(-1)

    def _read_file(self, fname):
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

    def _read_input(self):
        # Helper to generate the prompt
        def get_input():
            try:
                return raw_input(self._prompt(True)).strip()
            except EOFError:
                return ''

        line = get_input()
        while line:
            # Need the line number...
            tmp_lno = self.in_lno
            self.in_lno += 1

            # Parse the line--should never yield a pause
            yield ScriptLine('<stdin>', tmp_lno, line)

            # Get the next line
            line = get_input()

    def execute(self):
        recent_pause = False

        for output, sc_line in self._iter_lines():
            # Write the output script, but skip "source" instructions
            if (self.outfile is not None and
                (sc_line.type != 'command' or
                 sc_line.args[0] != '.')):
                print >>self.outfile, str(sc_line)
                self.outfile.flush()

            # Do we need to emit the line to stdout?
            if output and sc_line.output:
                print "%s%s" % (self._prompt(sc_line.type != 'command'),
                                sc_line)

            # Execute the line
            try:
                sc_line.execute(self)
            except PauseCommand:
                if not recent_pause:
                    recent_pause = True
                    self.filestack.append((False, iter(self._read_input())))
                continue
            except Exception, e:
                print >>sys.stderr, ("Got exception %s at %s:%s" %
                                     (e, sc_line.fname, sc_line.lno))
                if self.opts.debug:
                    traceback.print_exc()

            recent_pause = False

            # If we were instructed to exit, do so
            if self.exit_flag:
                return

        # If we hit the end of input normally, throw on a final
        if not recent_pause and not self.empty:
            self.empty = True
            self.filestack.append((False, iter(self._read_input())))
            return self.execute()
