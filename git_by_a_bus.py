#!/usr/bin/python
"""
Driver for git by a bus.

Calls gen_file_stats.py, estimate_unique_knowledge.py,
estimate_file_risk.py, summarize.py in a chain, storing output from
each in output_dir/(basename).tsv.

To re-run only a portion of the calculations, you can remove all tsv
downstream and run again with the -c option (this is useful if you
want to manually remove some files from gen_file_stats.tsv, for
instance, rather than run the gen_file_stats.py step, which is slowest
by orders of magnitude).

Writes a summary found at output_dir/index.html.

Run as python git_by_a_bus.py -h for options.
"""

import os
import sys
import textwrap

from argparse import ArgumentParser
from subprocess import Popen
from string import Template


SCRIPT_PATH=os.path.dirname(os.path.realpath(__file__))
sys.path.append(SCRIPT_PATH)


def exit_with_error(err: str):
    print("Error: ", err, file=sys.stderr)
    exit(1)


def read_projects_file(fname, paths_projects):
    try:
        with open(fname, 'r') as fil:
            paths_projects.extend([line.strip() for line in fil if line.strip()])
        return True
    except IOError:
        return False


def output_fname_for(pyfile, output_dir):
    if not pyfile:
        return None
    return os.path.join(output_dir, os.path.splitext(os.path.basename(pyfile))[0] + '.tsv')


def run_chained(cmd_ts, python_cmd, output_dir, verbose):
    for cmd_t in cmd_ts:
        input_pyfile = cmd_t[0]
        output_pyfile = cmd_t[1]
        
        opts_args = ['']
        if len(cmd_t) > 2:
            opts_args = cmd_t[2]

        input_fname = output_fname_for(input_pyfile, output_dir)
        output_fname = output_fname_for(output_pyfile, output_dir)

        # don't re-run if the results exist
        if output_fname is not None and os.path.isfile(output_fname):
            if verbose:
                print(f"{output_fname} EXISTS, SKIPPING", file=sys.stderr)
            continue

        input_f = open(input_fname, 'r') if input_fname else None
        output_f = open(output_fname, 'w') if output_fname else None

        for opt_args in opts_args:
            cmd = [x for x in ' '.join([python_cmd, output_pyfile, opt_args]).split(' ') if x]
            if verbose:
                print("Input file is: %s" % input_fname, file=sys.stderr)
                print("Output file is: %s" % output_fname, file=sys.stderr)
                print(cmd, file=sys.stderr)
            cmd_p = Popen(cmd, stdin=input_f, stdout=output_f)
            cmd_p.communicate()
            
        if input_f:
            input_f.close()
        if output_f:
            output_f.close()


def main(python_cmd, paths_projects, options):
    output_dir = os.path.abspath(options.output or 'output')
    try:
        os.mkdir(output_dir)
    except OSError:
        if not options.continue_last:
            exit_with_error("Output directory exists and you have not specified -c")

    risk_file_option = ''
    if options.risk_file:
        risk_file_option = '-r %s' % options.risk_file

    departed_dev_option = ''
    if options.departed_dev_file:
        departed_dev_option = '-d %s' % options.departed_dev_file

    interesting_file_option = ' '.join(["-i %s" % i for i in options.interesting])
    not_interesting_file_option = ' '.join(["-n %s" % n for n in options.not_interesting])
    case_sensitive_option = ''
    if options.case_sensitive:
        case_sensitive_option = '--case-sensitive'

    svn_option = ''
    if options.use_svn:
        svn_option = '--svn'

    git_exe_option = ''
    if options.git_exe:
        git_exe_option = "--git-exe %s" % options.git_exe

    model_option = "--model %s" % options.model

    # commands to chain together--the stdout of the first becomes the
    # stdin of the next.  You can find the output of gen_file_stats.py
    # in output_dir/gen_file_stats.tsv, and so on.
    cmd_ts = [
        [
            None,
            os.path.join(SCRIPT_PATH, 'gen_file_stats.py'),
            [
                f"${{interesting_file_option}} ${{not_interesting_file_option}} "
                f"${{case_sensitive_option}} ${{git_exe_option}} ${{svn_option}} {path_project}"
                for path_project in paths_projects
            ],
        ],
        [
            os.path.join(SCRIPT_PATH, 'gen_file_stats.py'),
            os.path.join(SCRIPT_PATH, 'estimate_unique_knowledge.py'),
            '${model_option}',
        ],
        [
            os.path.join(SCRIPT_PATH, 'estimate_unique_knowledge.py'),
            os.path.join(SCRIPT_PATH, 'estimate_file_risk.py'),
            '-b ${bus_risk} ${risk_file_option}',
        ],
        [
            os.path.join(SCRIPT_PATH, 'estimate_file_risk.py'),
            os.path.join(SCRIPT_PATH, 'summarize.py'), '${departed_dev_option} ${output_dir}',
        ],
    ]

    for cmd_t in cmd_ts:
        if len(cmd_t) > 2:
            opts_args = cmd_t[2]
            if not isinstance(opts_args, list):
                opts_args = [opts_args]
            opts_args = [
                Template(s).substitute(
                    python_cmd=python_cmd,
                    risk_file_option=risk_file_option,
                    bus_risk=options.bus_risk,
                    departed_dev_option=departed_dev_option,
                    interesting_file_option=interesting_file_option,
                    not_interesting_file_option=not_interesting_file_option,
                    case_sensitive_option=case_sensitive_option,
                    git_exe_option=git_exe_option,
                    svn_option=svn_option,
                    model_option=model_option,
                    output_dir=output_dir
                )
                for s in opts_args
            ]
            cmd_t[2] = opts_args

    run_chained(cmd_ts, python_cmd, output_dir, options.verbose)


if __name__ == '__main__':
    descr = textwrap.dedent("""
        Analyze each git controlled path and create an html summary of orphaned / at-risk code knowledge.

        Paths must be absolute paths to local git-controlled directories (they may be subdirs in the git repo).

        Project names are optional and default to the last directory in the path.

        You may alternatively/additionally specify the list of paths/projects in a file with -p.

        Experimental svn support with --svn and an svn url for project path.""")

    parser = ArgumentParser(description=descr)
    parser.add_argument(
        '-b', '--bus-risk', dest='bus_risk', metavar='FLOAT', default=0.1,
        help="The default estimated probability that a dev will be hit by a bus "
             "in your analysis timeframe (defaults to 0.1)"
    )
    parser.add_argument(
        '-r', '--risk-file', dest='risk_file', metavar='FILE',
        help='File of dev=float lines (e.g. ejorgensen=0.4) with custom bus risks for devs'
    )
    parser.add_argument(
        '-d', '--departed-dev-file', dest='departed_dev_file', metavar='FILE',
        help="File listing departed devs, one per line"
    )
    parser.add_argument(
        '-i', '--interesting', metavar="REGEXP", dest='interesting', action='append',
        help="Regular expression to determine which files should be included in calculations. "
             "May be repeated, any match is sufficient to indicate interest. "
             "Defaults are \\.java$ \\.cs$ \\.py$ \\.c$ \\.cpp$ \\.h$ \\.hpp$ \\.pl$ \\.rb$",
        default=[]
    )
    parser.add_argument(
        '-n', '--not-interesting', metavar="REGEXP", dest="not_interesting",
        action='append', default=[],
        help="Regular expression to override interesting files. "
             "May be repeated, any match is enough to squelch interest."
    )
    parser.add_argument(
        '--case-sensitive', dest='case_sensitive', action='store_true', default=False,
        help="Use case-sensitive regepxs when finding interesting / uninteresting files "
             "(defaults to case-insensitive)"
    )
    parser.add_argument(
        '-o', '--output', dest='output', metavar='DIRNAME', default='output',
        help="Output directory for data files and html summary (defaults to \"output\"), "
             "error if already exists without -c"
    )
    parser.add_argument(
        '-p', '--projects-file', dest='projects_file', metavar='FILE',
        help='File of path[=project_name] lines, where path is an absoluate path '
             'to the git-controlled directory or svn url to analyze and project_name is '
             'the name to use in the output summary (project_name defaults '
             'to the last directory name in the path)'
    )
    parser.add_argument(
        '-c', '--continue-last', dest='continue_last',
        default=False, action="store_true",
        help="Continue last run, using existing output files and recreating missing. "
             "You can remove tsv files in the output dir and modify others to clean up bad runs."
    )
    parser.add_argument(
        '-v', '--verbose', dest='verbose', default=False, action="store_true",
        help="Print debugging info"
    )
    parser.add_argument(
        '--python-exe', dest='python_exe', default='/usr/bin/python',
        help='Path to the python interpreter (defaults to "/usr/bin/python")'
    )
    parser.add_argument(
        '--git-exe', dest='git_exe',
        help='Path to the git exe (defaults to "/usr/bin/git")'
    )
    parser.add_argument(
        '--svn', dest='use_svn', default=False, action='store_true',
        help='Use svn intead of git to generate file statistics. '
             'This requires you to install pysvn in your PYTHONPATH.'
    )
    parser.add_argument(
        '--model', dest='model', metavar='MODEL[:MARG1[:MARG2]...]',
        default='sequential:0.1',
        help='Knowledge model to use, with arguments.  Right now only sequential is supported.'
    )
    parser.add_argument("paths", nargs="+")

    args = parser.parse_args()

    if args.projects_file:
        if not read_projects_file(args.projects_file, args.paths):
            exit_with_error("Could not read projects file %s" % args.projects_file)

    if not args.paths:
        parser.error(
            "No paths/projects! You must either specify paths/projects on the command line "
            "and/or in a file with the -p option."
        )
    
    main(args.python_exe, args.paths, args)
