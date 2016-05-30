import os
import sys
import time
import multiprocessing
import platform

######################################################################
#  Gather System Informations....
def gather_uptime(cliShell):
    FileOp = cliShell.runCommand('cat /proc/uptime')

    try:
        uptime_seconds = float(FileOp.readline().split()[0])
        uptime_time = str(timedelta(seconds=uptime_seconds))
        data = uptime_time.split('.', 1)[0]
    except Exception as err:
        data = str(err)

    return data

def gather_ipaddress(cliShell):
    try:
        data = []
        FileOp = cliShell.runCommand("ip addr | grep LOWER_UP | awk '{print $2}'")
        iface = FileOp.read().strip().replace(':', '').split('\n')
        del iface[0]

        for i in iface:
            FileOp = cliShell.runCommand("ip addr show " + i + "| awk '{if ($2 == \"forever\"){!$2} else {print $2}}'")
            data1 = FileOp.read().strip().split('\n')
            if len(data1) == 2:
                data1.append('unavailable')
            if len(data1) == 3:
                data1.append('unavailable')
            data1[0] = i
            data.append(data1)

        ips = {'interface':iface, 'itfip':data}

        data = ips
    except Exception as err:
        data = str(err)

    return data

def gather_cpus(cliShell):
    try:
        FileOp = cliShell.runCommand('cat /proc/cpuinfo |' + "grep 'model name'")
        data = FileOp.read().strip().split(':')[-1]

        if not data:
            FileOp = cliShell.runCommand('cat /pro/cpuinfo |' + "grep 'Processor'")
            data = FileOp.read().strip().split(':')[-1]

        cpus = multiprocessing.cpu_count()

        data = {'cpus':cpus, 'type':data}

    except Exception as err:
        data = str(err)

    return data

def gather_users(cliShell):
    try:
        pipe = cliShell.runCommand("who |" + "awk '{print $1, $2, $6}'")
        data = pipe.read().strip().split('\n')

        if data == [""]:
            data = None
        else:
            data = [i.split(None, 3) for i in data]

    except Exception as err:
        data = str(err)

    return data

def gather_traffics(cliShell, request):
    try:
        pipe = cliShell.runCommand("cat /proc/net/dev |" + "grep " + request + "| awk '{print $1, $9}'")
        data = pipe.read().strip().split(':', 1)[-1]

        if not data[0].isdigit():
            pipe = cliShell.runCommand("cat /proc/net/dev |" + "grep " + request + "| awk '{print $2, $10}'")
            data = pipe.read().strip().split(':', 1)[-1]

        data = data.split()

        traffic_in = int(data[0])
        traffic_out = int(data[1])

        all_traffic = {'traffic_in': traffic_in, 'traffic_out': traffic_out}

        data = all_traffic

    except Exception as err:
        data = str(err)

    return data

def gather_platform(cliShell):
    try:
        osname = " ".join(platform.linux_distribution())
        uname = platform.uname()

        if osname == '  ':
            osname = uname[0]

        data = {'osname': osname, 'hostname': uname[1], 'kernel': uname[2]}

    except Exception as err:
        data = str(err)

    return data

def gather_disks(cliShell):
    try:
        pipe = cliShell.runCommand("df -Ph | " + "grep -v Filesystem | " + "awk '{print $1, $2, $3, $4, $5, $6}'")
        data = pipe.read().strip().split('\n')

        data = [i.split(None, 6) for i in data]

    except Exception as err:
        data = str(err)

    return data

def gather_disk_rw(cliShell):
    try:
        pipe = cliShell.runCommand("cat /proc/partitions | grep -v 'major' | awk '{print $4}'")
        data = pipe.read().strip().split('\n')

        rws = []
        for i in data:
            if i.isalpha():
                pipe = cliShell.runCommand("cat /proc/diskstats | grep -w '" + i + "'|awk '{print $4, $8}'")
                rw = pipe.read().strip().split()

                rws.append([i, rw[0], rw[1]])

        if not rws:
            pipe = cliShell.runCommand("cat /proc/diskstats | grep -w '" + data[0] + "'|awk '{print $4, $8}'")
            rw = pipe.read().strip().split()

            rws.append([data[0], rw[0], rw[1]])

        data = rws

    except Exception as err:
        data = str(err)

    return data

def gather_memory(cliShell):
    try:
        pipe = cliShell.runCommand("free -tmo | " + "grep 'Mem' | " + "awk '{print $2,$4,$6,$7}'")
        data = pipe.read().strip().split()

        allmem = int(data[0])
        freemem = int(data[1])
        buffers = int(data[2])
        cachedmem = int(data[3])

        # Memory in buffers + cached is actually available, so we count it
        # as free. See http://www.linuxatemyram.com/ for details
        freemem += buffers + cachedmem

        percent = (100 - ((freemem * 100) / allmem))
        usage = (allmem - freemem)

        mem_usage = {'usage': usage, 'buffers': buffers, 'cached': cachedmem, 'free': freemem, 'percent': percent}

        data = mem_usage

    except Exception as err:
        data = str(err)

    return data

def gather_cpu_usage(cliShell):
    try:
        pipe = cliShell.runCommand("ps aux --sort -%cpu,-rss")
        data = pipe.read().strip().split('\n')

        usage = [i.split(None, 10) for i in data]
        del usage[0]

        total_usage = []

        for element in usage:
            usage_cpu = element[2]
            total_usage.append(usage_cpu)

        total_usage = sum(float(i) for i in total_usage)

        total_free = ((100 * int(gather_cpus(cliShell)['cpus'])) - float(total_usage))

        cpu_used = {'free': total_free, 'used': float(total_usage), 'all': usage}

        data = cpu_used

    except Exception as err:
        data = str(err)

    return data

def gather_load(cliShell):
    try:
        data = os.getloadavg()[0]
    except Exception as err:
        data = str(err)

    return data

def gather_netstat(cliShell):
    try:
        pipe = cliShell.runCommand("ss -tnp | grep ESTAB | awk '{print $4, $5}'| sed 's/::ffff://g' | awk -F: '{print $1, $2}' | awk 'NF > 0' | sort -n | uniq -c", skip_line = 2)
        data = pipe.read().strip().split('\n')

        data = [i.split(None, 4) for i in data]

    except Exception as err:
        data = str(err)

    return data

#####################################################################
# Stop Client System Gatherer
def stopVMMonitorProc(cliShell, process_name):
    try:
        # find VMMonitor.py and get PID
        cliShell.sendline('ps -ef | grep "%s" | grep -v grep | awk \'{print $2}\'' % process_name)
        cliShell.prompt()
        pid = int(cliShell.before.splitlines()[1])
        cliShell.sendline('kill -9 %d' % pid)
        cliShell.prompt()
    except Exception as e:
        print 'Fail to Kill process named [%s] - %s' % (process_name, str(e))

#####################################################################
# Remove Scheduler in System
def removeScheduledJob(cliShell):
    try:
        # reset crontab shell script - /home/humax/admin/cronjob/run_control.sh, run_control_weekly.sh, run_control_monthly.sh
        cliShell.sendline('echo "# VM Client is controlled by remotely" > /home/humax/admin/cronjob/run_control.sh')
        cliShell.prompt()
        cliShell.sendline('echo "# VM Client is controlled by remotely" > /home/humax/admin/cronjob/run_control_weekly.sh')
        cliShell.prompt()
        cliShell.sendline('echo "# VM Client is controlled by remotely" > /home/humax/admin/cronjob/run_control_monthly.sh')
        cliShell.prompt()
        cliShell.before
    except Exception as e:
        print 'Fail to Prepare VMManager - %s' % str(e)

