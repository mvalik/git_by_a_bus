"""
Common and other crappy code used throughout git by a bus.
"""


def safe_author_name(author):
    if author:
        return author.replace(',', '_').replace(':', '_')
    else:
        return author


def safe_int(i: str | None) -> int | None:
    if i is None or i == '':
        return None
    else:
        return int(i)


def safe_str(s) -> str:
    if s is None:
        return ''
    else:
        return str(s)


def parse_dev_shared(s, num_func):
    dev_shared = []
    if not s:
        return dev_shared
    return [(ddv.split(':')[:-1], float(ddv.split(':')[-1])) for ddv in s.split(',')]


def dev_shared_to_str(dev_shared):
    return ','.join([':'.join([':'.join(devs), str(shared)]) for devs, shared in dev_shared])


def parse_dev_exp_str(s: str, num_func) -> list[tuple[str, str, str]]:
    if not s:
        return []
    return [
        (dd[0], num_func(dd[1]), num_func(dd[2]))
        for dd in [d.split(':') for d in s.split(',')]
    ]


def dev_exp_to_str(devs):
    return ','.join([':'.join([str(x) for x in d]) for d in devs])


def project_name(fname):
    if not fname:
        return None
    return fname.split(':')[0]


class FileData(object):
    """
    Represents a single line of data about a single file, can encode / parse to / from tsv.

    fname: the name of the file the data is about

    cnt_lines: the number of lines in the file

    tot_knowledge: total knowledge in the file

    dev_experience: [(dev, lines_added, lines_removed), ...]

    dev_uniq: [([dev1], uniq_knowledge), ([dev1, dev2], uniq_knowledge), ...]

    dev_risk: [([dev1], risk), ([dev1, dev2], risk), ...]

    project: name of the project
    """
    
    num_fields = 6

    def __init__(self, line):
        if line is None:
            line = ''
        line = line.strip('\n\r')
        fields: list[str | None] = line.split('\t')
        n_missing_fields = FileData.num_fields - len(fields)
        fields.extend(n_missing_fields * [None])
        
        self.fname, cnt_lines, dev_experience, tot_knowledge, dev_uniq, dev_risk = fields

        self.cnt_lines = safe_int(cnt_lines)
        self.tot_knowledge = safe_int(tot_knowledge)
        
        self.dev_experience = parse_dev_exp_str(dev_experience, int)
        self.dev_uniq = parse_dev_shared(dev_uniq, float)
        self.dev_risk = parse_dev_shared(dev_risk, float)

        self.project = project_name(self.fname)

    def as_line(self):
        return '\t'.join(
            [
                safe_str(s)
                for s in [
                    self.fname, self.cnt_lines, dev_exp_to_str(self.dev_experience),
                    self.tot_knowledge, dev_shared_to_str(self.dev_uniq),
                    dev_shared_to_str(self.dev_risk)
                ]
            ]
        )

    def __str__(self):
        s = (
            f"fname: {self.fname}, cnt_lines: {self.cnt_lines}, "
            f"dev_experience: {dev_exp_to_str(self.dev_experience)}, "
            f"tot_knowledge: {self.tot_knowledge}, dev_uniq: {dev_shared_to_str(self.dev_uniq)}, "
            f"risk: {dev_shared_to_str(self.dev_risk)}"
        )
        return s


def is_interesting(f, interesting, not_interesting):
    if f.strip() == '':
        return False
    has_my_interest = any([i.search(f) for i in interesting])
    if has_my_interest:
        has_my_interest = not any([n.search(f) for n in not_interesting])
    return has_my_interest


def parse_departed_devs(dd_file, departed_devs):
    fil = open(dd_file, 'r')
    for line in fil:
        line = line.strip()
        line = safe_author_name(line)
        if not line:
            continue
        departed_devs.append(line)
    fil.close()
