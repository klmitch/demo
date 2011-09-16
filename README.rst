==================
Demo Script Driver
==================

The Demo package provides a simple driver for demo scripts.  A demo
script is simply a shell script of commands to be run to demonstrate
some sort of functionality of a system.  Each command is printed
before being run, and each blank line results in a pause.  During
pauses, additional commands may be executed as required for the
demonstration, and all executed commands are available through the
readline history, whether typed at the prompt or not.

More advanced functionality is also available.  Although demo scripts
cannot contain conditionals or loops, the "source" mechanism is
available, and the environment may be manipulated both permanently and
per-command.  Additional non-shell commands can be created by
importing Python modules that use the @register decorator; from the
demo script, use "import <module>", "from <module> import <callable>",
or "from <module> import <callable> as <name>".  Finally, a leading
"#!" line is ignored, as are comments introduced by "##", and command
printing can be inhibited by prepending "!" to the command line.

Exceptions encountered (including failure to execute shell commands)
are printed to standard error, but without a stack trace; to enable
stack traces, pass the "--debug" flag to the "demo" command.
Additionally, a synthesis of all commands executed can be output using
the "--output" flag; this may be useful when creating a demo script.
Finally, the command prompt can be altered with the "--prompt" flag;
the "%(nextcmd)s" and "%(currdir)s" strings will be expanded to the
position in the history list and the current working directory,
respectively.  (Note that this expansion mechanism is fragile, in the
sense that mistyped expansions may result in a crash.)
