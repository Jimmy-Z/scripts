#!/usr/bin/python
from subprocess import Popen, PIPE
from re import compile as re_compile
from os.path import exists

MDSTAT_PATH = "/proc/mdstat"

def call(*args, **kwargs):
    kwargs['stdout'] = PIPE
    kwargs['stderr'] = PIPE
    p = Popen(*args, **kwargs)
    out, err = p.communicate()
    return p.returncode, out, err

si_prefixes = ["", "K", "M", "G", "T"]
def format_size(d):
    i = 0
    while d >= 1000:
        d /= 1000.0
        i += 1
    return "%s%s" % (("%d" % d if ("%.1f" % d)[-1] == "0" else "%.1f" % d), si_prefixes[i])

mdstat_device_pattern = re_compile(r"([a-z]+)\d*\[\d+\]")

class HDD_Monitor(object):
    def __init__(self, **kwargs):
        self.smartctl = 'smartctl'
        self.__dict__.update(kwargs)
        self.hdds = {}
        self.count_by_size = {}
        self.get_hdd_list()
        self.formatting = '%-5s%5s %-6s%-25s%-20s%-10s%5s%5s%8s%5s%8s%5s%5s%5s\n'
        self.standby_formatting = "%-5s%5s %-6s%-25s-STANDBY-\n"
        self.header = self.formatting % ('', 'Size', 'mdadm', 'Model', 'Serial', 'Version', 'Temp', '0x05', '0x09', '0x0A', '0xC1', '0xC4', '0xC5', '0xC6') \
            + self.formatting % (("",) + ('===',) * 13)
        #for hdd in self.hdds:
        #    self.update_one(hdd)
        self.idx = 0

    # deprecated for completeness
    def get_hdd_list_smartctl(self):
        exit, out, _ = call([self.smartctl, '-n', 'standby', '--scan'])
        if exit == 0:
            hdd_list = filter(None, [l.partition(' ')[0] for l in out.split('\n')])
            self.hdds = dict(zip(hdd_list, [{'device': hdd} for hdd in hdd_list]))

    def get_hdd_list(self):
        exit, out, _ = call(["lsblk", "-abdlnr", "-o", "NAME,TYPE,SIZE,MODEL"])
        if exit == 0:
            hdd_list = filter(None, [(l[0], format_size(int(l[2])), l[3]) if len(l) == 4 and l[1] == "disk" else None for l in
                [filter(None, l.split(" ", 3)) for l in out.split("\n")]])
            self.hdds = dict([(d[0], {"device": "/dev/" + d[0], "size": d[1], "Device Model": d[2]}) for d in hdd_list])
            for d in hdd_list:
                s = d[1]
                self.count_by_size[s] = (self.count_by_size.get(s) or 0) + 1
        if exists(MDSTAT_PATH):
            mdstat = filter(None, [[c.strip() for c in l.split(" ")] if len(l) and l[0] != " " else None for l in
                open(MDSTAT_PATH).read().split('\n')[1:-2]]);
            # print mdstat
            for line in mdstat:
                if line[2] == "active":
                    md_devices = line[4:]
                elif line[2] == "inactive":
                    md_devices = line[3:]
                for cell in md_devices:
                    match = mdstat_device_pattern.match(cell)
                    if match is None:
                        print "no match for ", cell
                        continue
                    device = match.group(1)
                    hdd = self.hdds.get(device)
                    # if a disk drops, it will still present in /proc/mdstat, so we have to test
                    if hdd:
                        hdd["mdadm"] = line[0]

    def update_one(self, hdd):
        info = self.hdds[hdd]
        serial_ready = 'Serial Number' in info
        exit, out, err = call([self.smartctl, '-n', 'standby', serial_ready and '-A' or '-iA', info["device"]])
        if exit == 0:
            info['STANDBY'] = False
        elif exit == 2 and out.find('STANDBY') > -1:
            info['STANDBY'] = True
        else:
            print 'smartctl exit with %d:\n=== stderr ===\n%s\n=== stdout ===\n%s\n' % (
                    exit, err, out)
            return
        # 0 for waiting for info sec or smart sec
        # 1 in info sec and waiting for smart sec
        # 2 in smart sec
        mode = 0
        ret = {}
        for l in [l.strip() for l in out.split('\n')]:
            if mode == 0:
                if not serial_ready:
                    if l == '=== START OF INFORMATION SECTION ===':
                        mode = 1
                        continue
                else:
                    if l == '=== START OF READ SMART DATA SECTION ===':
                        mode = 2
                        continue
            elif mode == 1:
                if l == '=== START OF READ SMART DATA SECTION ===':
                    mode = 2
                    continue
                l = [c.strip() for c in l.partition(':')]
                if l[1] == ':':
                    info[l[0]] = l[2]
            elif mode == 2:
                l = filter(None, [c.strip() for c in l.split(' ')])
                if len(l) >= 10 and l[0].isdigit() and l[9].isdigit():
                    info["%02x" % int(l[0])] = int(l[9])

    def report_one(self, hdd):
        r = self.hdds[hdd]
        if r.get("STANDBY"):
            return self.standby_formatting % (
                hdd,
                r.get("size"),
                r.get("mdadm", "-"),
                r.get("Device Model", "-")
            )
        else:
            return self.formatting % (
                hdd,
                r.get("size"),
                r.get("mdadm", "-"),
                r.get("Device Model", "-"),
                r.get("Serial Number", "-"),
                r.get("Firmware Version", "-"),
                r.get("c2", "-"), # Temperature Celsius
                r.get("05", "-"), # Reallocated Sector Ct
                r.get("09", "-"), # Power On Hours
                r.get("0a", "-"), # Spin Retry Count
                r.get("c1", "-"), # Load Cycle Count
                r.get("c4", "-"), # Reallocated Event Count
                r.get("c5", "-"), # Current Pending Sector
                r.get("c6", "-")  # Offline Uncorrectable
            )

    def report(self):
        standby = 0
        for hdd in sorted(self.hdds.keys(), lambda a, b: cmp(len(a), len(b)) or cmp(a, b)):
            self.update_one(hdd)
            if self.hdds[hdd].get("STANDBY"):
                standby += 1
            yield self.report_one(hdd)
        yield  "===\nActive/Total: %d/%d, By Size: %s\n" % \
            (len(self.hdds) - standby, len(self.hdds),
                ", ".join("%s*%d" % d for d in self.count_by_size.items()))

    def report_by_model(self):
        models = {}
        for hdd in self.hdds.values():
            model_name = hdd.get('Device Model', '-N/A-')
            model = models.get(model_name)
            if model is None:
                models[model_name] = [hdd]
            else:
                model.append(hdd)
        report = []
        for model_name in models:
            report.append('%s: %s' % (model_name, self.report_on_list(models[model_name])))
        report.append('===')
        report.append('Total: ' + self.report_on_list(self.hdds.values()))
        return '\n'.join(report)

    def next(self):
        self.update_one(self.hdds.keys()[self.idx])
        self.idx = (self.idx + 1) % len(self.hdds)

    def report_on_list(self, hdds):
        standby = 0
        temp_sum = 0.
        temp_count = 0
        temp_max = 0
        for d in hdds:
            if d['STANDBY']:
                standby += 1
            else:
                temp = d.get('Temperature_Celsius')
                if temp is not None:
                    temp_sum += temp
                    temp_count += 1
                    if temp > temp_max:
                        temp_max = temp
        return 'Active/Total: %d/%d, Temp: %s' % (
            len(hdds) - standby, len(hdds),
            (temp_count > 0) and ('Avg: %.1f, Max: %.1f' % (temp_sum / temp_count, temp_max)) or '-N/A-')


if __name__ == '__main__':
    hddm = HDD_Monitor()
    from time import sleep
    from datetime import datetime
    import os
    print hddm.header,
    for s in hddm.report():
	    print s,
"""
    while True:
        os.system(os.name == 'nt' and 'cls' or 'clear')
        print hddm.report_by_model()
        print datetime.now()
        sleep(.5)
        hddm.next()
"""

