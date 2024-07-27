#!/usr/bin/python
# vim: set fileencoding=utf-8
from os import listdir, mkdir, rename
from os.path import isdir, isfile, join, exists
from sys import stderr, platform
from re import compile, UNICODE

if platform == 'win32':
    from ctypes import windll
    CODEC = 'cp%d' % windll.kernel32.GetACP()
else:
    CODEC = 'utf-8'

prefix_match = lambda s, fix: len(s) > len(fix) and s[:len(fix)] == fix
safe_lower = lambda s: s.decode(CODEC).lower().encode(CODEC)

def dedup_rules(rules, prompt):
    # TODO: since the auto_rule_pattern has been changed, we should improve
    # dedup to handle prefix match too
    dupe = {}
    ret = {}
    for k, v in rules:
        d = dupe.get(k)
        if d is not None:
            d.append(v)
        else:
            d = ret.get(k)
            if d is not None:
                dupe[k] = [d, v]
                del ret[k]
            else:
                ret[k] = v
    if len(dupe) > 0:
        print >> stderr, prompt % len(dupe),
        for k in dupe:
            print >> stderr, '\t%s\n' % k,
            for d in dupe[k]:
                print >> stderr, '\t\t%s\n' % d,
    return ret

def dedup_rules_alt(primary, secondary, prompt):
    dupes = []
    for k in secondary.keys(): # we will modify secondary, so a copy of keys is needed
        for kp in primary:
            if prefix_match(kp, k) or prefix_match(k, kp):
                dupes.append((k, secondary[k]))
                del secondary[k]
    if len(dupes) > 0:
        print prompt % len(dupes),
        for k, v in dupes:
            print '\t%s -> %s\n' % (k, v),

# auto_rule_pattern = compile(r'^\[[^\]]+\]\[[^\]]+\]')
# auto_rule_pattern = compile(ur'^([\[\]\(\)\-【】]+(?!(\s|第)?[0-9]{2,3}[^0-9])[^\[\]\(\)\-【】]+){2,}', UNICODE)
auto_rule_pattern = compile(ur'^([\[\]\(\)\-【】]+[^\[\]\(\)\-【】]+){2}'
    ur'([\[\]\(\)\-【】]+(?!(\s|第)?[0-9]{2,3}[^0-9])[^\[\]\(\)\-【】]+)*[\]\)\-】]*', UNICODE)
def get_prefix(e):
    e = e.decode(CODEC)
    match = auto_rule_pattern.match(e)
    if match is None:
        return None
    match = match.group(0)
    if match == e:
        return None
    return match.lower().encode(CODEC)

def auto_catalog(src_dir, dst_dir, overwrite_existing = False, dry_run = True):
    manual_rule_re = compile(r'^prefix=(.+)$')
    # scan dst_dir for rules
    print 'generating rules:\n',
    # rules are simply prefix -> path mappings
    auto_rules = []
    manual_rules = []
    for bangumi in listdir(dst_dir):
        bangumi_full = join(dst_dir, bangumi)
        # listdir list files and sub-dirs, we only need dirs
        if not isdir(bangumi_full):
            continue
        auto_rules_dedup = set()
        for e in listdir(bangumi_full): # e for entry
            if isdir(join(bangumi_full, e)):
                # find manual rules from dirs with a specified pattern
                match = manual_rule_re.match(e)
                if match is None:
                    continue
                rule = match.group(1)
                print '\tmanual prefix rule: %s -> %s\n' % (rule, bangumi),
                manual_rules.append((safe_lower(rule), bangumi_full))
            else:
                # generate auto rules from existing files
                prefix = get_prefix(e)
                if prefix is None:
                    continue
                auto_rules_dedup.add(prefix)
        for rule in auto_rules_dedup:
            print '\tauto prefix rule: %s -> %s\n' % (rule, bangumi),
            auto_rules.append((rule, bangumi_full))

    # dedup rules
    manual_rules = dedup_rules(manual_rules,
        '!!! CAUTION !!! the following %d manual rule(s) are considered ambiguous' \
        ' for appearing in several different locations thus will be ignored:\n')
    auto_rules = dedup_rules(auto_rules,
        '!!! CAUTION !!! the following %d auto rule(s) are considered ambiguous' \
        ' for appearing in several different locations thus will be ignored:\n')
    dedup_rules_alt(manual_rules, auto_rules,
        'the following %d auto rule(s) are deprecated' \
        ' for a manual rule thus will be ignored:\n')

    if len(manual_rules) + len(auto_rules) == 0:
        print 'no rules, abort\n',
        return

    print '%d auto rule(s), and %d manual rule(s), start moving:\n' \
        % (len(auto_rules), len(manual_rules)),

    manual_rules = zip(manual_rules.keys(), manual_rules.values())
    manual_rules.sort(lambda a, b: cmp(len(b[0]), len(a[0])))
    auto_rules_list = zip(auto_rules.keys(), auto_rules.values())
    auto_rules_list.sort(lambda a, b: cmp(len(b[0]), len(a[0])))

    # scan src_dir
    homeless = []
    existed = []
    for filename in listdir(src_dir):
        fullname = join(src_dir, filename)
        lowered = safe_lower(filename)
        if not isfile(fullname):
            continue
        target = None
        # manual rules above all
        for prefix, bangumi_full in manual_rules:
            if prefix_match(lowered, prefix):
                target = bangumi_full
                break
        # then auto rules by hashing prefix
        if target is None:
            prefix = get_prefix(lowered)
            if prefix is not None:
                target = auto_rules.get(prefix)
        # some files might not match by hashing prefix, for example:
        # get_prefix('[foo][bar][01][720p].mp4') = '[foo][bar'
        # this auto-rule will work for [foo][bar][01][1080p].mp4 / [foo][bar][02][720p].mp4
        # but get_prefix('[foo][bar][NCOP][720p].mp4') = '[foo][bar][NCOP' won't work
        if target is None:
            for prefix, bangumi_full in auto_rules_list:
                if prefix_match(lowered, prefix):
                    target = bangumi_full
                    break
        # move the file
        if target is not None:
            print '\t%s -> %s\n' % (filename, target),
            if not dry_run:
                target_file = join(target, filename)
                if not exists(target_file) or overwrite_existing:
                    rename(fullname, target_file)
                else:
                    existed.append(filename)
        else:
            homeless.append(filename)

    if len(existed):
        print 'the following %d file(s) are not moved, we won\'t overwrite files\n' % len(existed),
        for e in existed:
            print '\t%s\n' % e,
    if len(homeless):
        print 'no matching rule for the following %d file(s):\n' % len(homeless),
        for e in homeless:
            print '\t%s\n' % e,

if __name__ == '__main__':
    from sys import argv
    overwrite_existing = True
    dry_run = False
    for arg in argv[3:]:
        arg = arg.lower()
        if arg == 'no_overwrite':
            overwrite_existing = False
        elif arg == 'dry_run':
            dry_run = True
    print 'using CODEC: %s\n' % CODEC,
    print 'overwrite existing: %s\n' % overwrite_existing,
    print 'dry run: %s\n' % dry_run,
    auto_catalog(argv[1], argv[2], overwrite_existing, dry_run)

