import collections
import os
import readline
import shlex
import string
import sys
import traceback

from demo import aliases

__all__ = ['Script']


class PauseCommand(Exception):
    """
    Helper exception raised when a pause line is executed.
    """

    pass


class ScriptLine(object):
    """
    Represents a single line from a script.
    """

    @staticmethod
    def _subst(text, substs):
        """
        Helper method to perform string substitution on `text`.  The
        `substs` argument provides a dictionary-like object which will
        be used for computing substitutions.  Uses string.Template to
        perform $ substitutions, followed by tilde expansion if the
        result begins with '~'.  Returns the fully substituted string.
        """

        # Start off with $ substitutions
        tmp = string.Template(text).substitute(substs)

        # Perform tilde expansion
        if tmp and tmp[0] == '~':
            tmp = os.path.expanduser(tmp)

        return tmp

    def __init__(self, fname, lno, line):
        """
        Initialize a script line.  The `fname` and `lno` arguments
        indicate the origin of `line`, which is parsed and
        substituted.  The resulting object contains `fname` and `lno`
        attributes, the `raw` text, a `type` (can be "comment",
        "pause", "command", or "export"), an `output` boolean
        indicating whether the line should be displayed to the user
        prior to execution, a `vardict` containing variables that
        should be set specifically for this command, and an `args`
        list containing the command arguments (the first element will
        contain the command name).
        """

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

            # Take out leading '!'
            if not self.output:
                self.raw = line

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

        # Handle pause and export commands specially
        if args[0] == 'pause':
            self.raw = ''
            self.type = 'pause'
            self.output = False
            self.vardict = None
            self.args = None
            return
        elif args[0] == 'export':
            self.type = 'export'
            args.pop(0)

        # Process the variable dictionary
        self.vardict = {}
        while args and ('=' in args[0] or self.type == 'export'):
            if '=' not in args[0]:
                args.pop(0)
                continue
            name, value = args.pop(0).split('=', 1)
            value = self._subst(value, subst_dict)
            subst_dict[name] = value
            self.vardict[name] = value

        # Was that all the arguments?
        if not args:
            self.type = 'export'

        # Save the arguments
        self.args = [self._subst(arg, subst_dict) for arg in args]

    def __str__(self):
        """
        Returns the raw text of the script line.
        """

        return self.raw

    def execute(self, ctx):
        """
        Executes the script line within the given context `ctx`.  If
        the script line is a "pause", raises a PauseCommand exception
        as a signal to the caller.
        """

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
    """
    Represents a script context.  Performs all the actions for
    reading, outputting, and executing script lines from a variety of
    input sources.
    """

    def __init__(self, opts):
        """
        Initializes a script context.  The `opts` parameter is an
        object defining the following keys:

            * files - A list of file names from which to read; '-' is
              interpreted as a read from standard input.

            * output - If not None, identifies the name of a file to
              which to write the script lines.

            * prompt - A prompt to use for interactive input.

            * debug - A boolean indicating whether to enable debugging
              output.
        """

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
        """
        Signals the context that it should exit instead of reading the
        next command.
        """

        # Exit the interpreter on the next statement
        self.exit_flag = True

    def push_file(self, fname):
        """
        Causes a new file to be placed on the file stack.  The new
        file will be read completely, then execution of the current
        file will be resumed.
        """

        # Push another file to process
        self.filestack.append((True, iter(self._read_file(fname))))

    def _prompt(self):
        """
        Helper routine to generate a prompt.
        """

        nextcmd = readline.get_current_history_length()
        currdir = os.getcwd()

        return self.prompt_tmpl % locals()

    def _iter_lines(self):
        """
        Generator to read a sequence of lines from the file stack.
        Once reading of one file is complete, it is popped off the
        stack and reading of the next file on the stack is resumed.
        """

        while self.filestack:
            try:
                # Yield the next line
                yield (self.filestack[-1][0], next(self.filestack[-1][1]))
            except StopIteration:
                self.filestack.pop(-1)

    def _read_file(self, fname):
        """
        Generator to read ScriptLine objects from the file named
        `fname`.
        """

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
                readline.add_history(sc_line.raw)

                # Yield the line
                yield sc_line

    def _read_input(self):
        """
        Generator to read ScriptLine objects from standard input.
        Ends when a blank line is entered.
        """

        # Helper to generate the prompt
        def get_input():
            try:
                return raw_input(self._prompt()).strip()
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
        """
        Executes the script context.  Reads lines from the files on
        the file stack and executes them in turn.  Pause commands are
        handled by pushing the _read_input() generator onto the file
        stack.  Processing ends with a final pushing of _read_input()
        onto the file stack.  This is the main loop.
        """

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
                print "%s%s" % (self._prompt(), sc_line)

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
