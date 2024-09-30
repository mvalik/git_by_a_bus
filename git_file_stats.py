"""
Module to generate file stats using git.

The only function here intended for external consumption is gen_stats.

Output of gen_stats should be exactly the same as the output of
git_file_stats.gen_stats, but in practice they may differ by a line or
two (appears to be whitespace handling, perhaps line endings?)
"""
import os
import re
import subprocess
import sys

from common import is_interesting, FileData, safe_author_name


def gen_stats(root, project, interesting, not_interesting, options):
    """
    root: the path a local, git controlled-directory that is the root
    of this project

    project: the name of the project

    interesting: regular expressions that indicate an interesting path
    if they match

    not_interesting: regular expressions that trump interesting and
    indicate a path is not interesting.

    options: from gen_file_stats.py's main, currently only uses
    git_exe.

    Yields FileData objects encoded as tsv lines.  Only the fname,
    dev_experience and cnt_lines fields are filled in.
    """
    git_exe = options.git_exe

    # since git only works once you're in a git controlled path, we
    # need to get into one of those...
    prepare(root, git_exe)

    files = git_ls(root, git_exe)

    for f in files:
        if is_interesting(f, interesting, not_interesting):
            dev_experience = parse_dev_experience(f, git_exe)
            if dev_experience:
                fd = FileData(':'.join([project, f]))
                fd.dev_experience = dev_experience
                fd.cnt_lines = count_lines(f)
                fd_line = fd.as_line()
                if fd_line.strip():
                    yield fd_line


def count_lines(f: str) -> int:
    with open(f, 'r') as fil:
        count = 0
        for _ in fil:
            count += 1
    return count


def parse_experience(log):
    """
    Parse the dev experience from the git log.
    """
    # list of tuple of shape [(dev, lines_add, lines_removed), ...]
    exp = []

    # entry lines were zero separated with -z
    entry_lines = log.split('\0')

    for entry_line in entry_lines:
        if not entry_line.strip():
            continue
        current_entry = entry_line.split('\n')
        if len(current_entry) < 2:
            continue
        author, changes = current_entry[:2]
        # only spaces has been changed - ignoring
        if not changes.strip():
            continue
        author = safe_author_name(author)
        m = re.match(r"^(\d+)\s+(\d+)\s+.*$", changes)
        if not m:
            continue
        lines_added, lines_removed = m.groups()
        if lines_added or lines_removed:
            exp.append((author, lines_added, lines_removed))

    # we need the oldest log entries first.
    exp.reverse()
    return exp


def parse_dev_experience(f: str, git_exe: str):
    """
    Run git log and parse the dev experience out of it.
    """
    # -z = null byte separate logs
    # -w = ignore all whitespace when calculating changed lines
    # --follow = follow file history through renames
    # --numstat = print a final ws separated line of the form
    #             'num_added_lines num_deleted_lines file_name'
    # --format=format:%an = use only the author name for the log msg format
    git_cmd = [git_exe, "log", "-z", "-w", "--follow", "--numstat", "--format=format:%an", f]
    git_p = subprocess.run(git_cmd, capture_output=True, text=True)
    return parse_experience(git_p.stdout)


def git_ls(root: str, git_exe: str):
    """
    List the entire tree that git is aware of in this directory.
    """
    # --full-tree = allow absolute path for final argument (pathname)
    # --name-only = don't show the git id for the object, just the file name
    # -r = recurse
    git_cmd = [git_exe, "ls-tree", "--full-tree", "--name-only", "-r", "HEAD", root]
    git_p = subprocess.run(git_cmd, capture_output=True, text=True)
    files = git_p.stdout.split('\n')
    return files


def git_root(git_exe):
    """
    Given that we have chdir'd into a Git controlled dir, get the git
    root for purposes of adjusting paths.
    """
    git_cmd = [git_exe, "rev-parse", "--show-toplevel"]
    git_p = subprocess.run(git_cmd, capture_output=True, text=True)
    return git_p.stdout.strip()


def prepare(root: str, git_exe: str):
    # first we have to get into the git repo to make the git_root work...
    os.chdir(root)
    # then we can change to the git root
    os.chdir(git_root(git_exe))
