import re
import sys

EXCLUDE_PATTERN='prv\d+|tap\d+'

def readfile(filename):
    try:
        f = open(filename)
    except IOError:
        print "Could not read %s" % filename
        sys.exit(1)
    lines = f.readlines()
    ret=list()
    for line in lines:
        if re.search(r'^\s+$', line):
            continue
        line = re.sub('\s+', ' ', line) # Replace all whitespace chars
        line = line.strip()
        ret.append(line)
    return ret

def get_configured_ifces(iterable):
    ifces = dict()

    for i in iterable:
        m = re.match('(auto|iface) ([\d\w-]+)', i)
        if m:
            ifce = m.groups()[1]
            if ifce not in ifces.keys():
                ifces[ifce] = dict()
            if m.groups()[0] == 'auto':
                ifces[ifce]['configured_status']='UP'
        slaves = re.match('slaves ((?:(?:[\d\w-]+) ?){1,4})', i)
        if slaves:
            ifces[ifce]['slaves'] = slaves.groups()[0].split(' ')
    return ifces

def get_all_system_ifces(iterable):
    ifces = dict()
    for i in iterable:
        m = re.match('([\d\w-]+):', i)
        if m:
            ifce = m.groups()[0]
            ifces[ifce]=dict()
    return ifces

def get_all_running_interfaces(iterable):
    import socket
    import fcntl
    import struct
    import array

    SIOCGIFFLAGS=0x8913
    null256 = '\0'*256 # TODO: 256 a magic number?

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    for iface in iterable.keys():
        result = fcntl.ioctl(s.fileno(), SIOCGIFFLAGS, iface + null256)
        flags, = struct.unpack('H', result[16:18])

        iterable[iface]['running_status']= ('DOWN', 'UP')[flags & 1]
        iterable[iface]['connected']= ('NO', 'YES')[(flags & 2**6) >> 6]
        iterable[iface]['loopback']= ('NO', 'YES')[(flags & 2**3) >> 3]
        iterable[iface]['slave']= ('NO', 'YES')[(flags & 2**11) >> 11]
        iterable[iface]['master']= ('NO', 'YES')[(flags & 2**10) >> 10]

def verify(ifces):
    value = 0
    for ifce in ifces.keys():
        if re.match(EXCLUDE_PATTERN, ifce):
            continue
        if 'configured_status' not in ifces[ifce]:
            print "Warning: UNCONFIGURED %s, running_status: %s" % (
                    ifce,
                    ifces[ifce]['running_status'])
            value = value | 1;
            continue
        if ifces[ifce]['running_status'] != ifces[ifce]['configured_status']:
            print "Warning: INCONSISTENT %s, running_status: %s, configured_status: %s" % (
                    ifce,
                    ifces[ifce]['running_status'],
                    ifces[ifce]['configured_status'],)
            value = value | 1;
        if ifces[ifce]['running_status'] == 'UP' and \
            ifces[ifce]['connected'] == 'NO':
            print "Warning: UNCONNECTED %s, running_status: %s, connected: %s" % (
                    ifce,
                    ifces[ifce]['running_status'],
                    ifces[ifce]['connected'],)
            value = value | 1;
        if 'slaves' in ifces[ifce]:
            for slave in ifces[ifce]['slaves']:
                if ifces[slave]['slave'] != 'YES':
                    print "Warning: INCONSISTENT BOND: %s, slave: %s configured but not active" % (
                                    ifce,
                                    slave,)
    return value

system_ifces = get_all_system_ifces(readfile('/proc/net/dev'))
configured_ifces = get_configured_ifces(readfile('/etc/network/interfaces'))
get_all_running_interfaces(system_ifces)
all_ifces=dict(system_ifces)

for iface in all_ifces.keys():
    if iface in configured_ifces.keys():
        all_ifces[iface].update(configured_ifces[iface])
    else:
        all_ifces[iface]['configured_status']='DOWN'

sys.exit(verify(all_ifces))

