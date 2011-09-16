import argparse
import sys

from demo.aliases import *
from demo.script import *

__all__ = ['register', 'Script', 'get_argparser', 'main']


def get_argparser(argparser=None):
    # Build the initial argument parser
    if argparser is None:
        argparser = argparse.ArgumentParser(description="Run demo scripts")

    # Add the arguments we need to see
    argparser.add_argument('files', nargs='+',
                           help="Demo script filenames")
    argparser.add_argument('-o', '--output', dest='output', action='store',
                           help="Output commands to new demo file")
    argparser.add_argument('-p', '--prompt', dest='prompt', action='store',
                           default='[%(nextcmd)s]> ',
                           help="Prompt to use in interactive usage")
    argparser.add_argument('-d', '--debug', dest='debug', action='store_true',
                           default=False, help="Enable debugging output")

    return argparser


def main(argparser=None, args=None):
    # Get an argument parser
    if argparser is None:
        argparser = get_argparser()

    # What arguments are we parsing?
    if args is None:
        args = sys.argv[1:]

    # Get our options
    opts = argparser.parse_args(args)

    # Initialize the Script object...
    sc = Script(opts)

    # And execute the script
    sc.execute()
