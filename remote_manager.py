# run command and get result from remote server
import os
import sys
import time
import multiprocessing
import platform
from datetime import timedelta
from optparse import OptionParser
from pexpect import pxssh
from system_control_cmd import *
import urllib2

def internet_on(ipaddr):
    try:
        response=urllib2.urlopen('http://74.125.228.100',timeout=1)
        return True
    except urllib2.URLError as err: pass
    return False
###################################################
# File Operation Emulator
class EmulateFileData():
    def __init__(self, full_string, skip_line = 1):
        self.full_string = full_string
        self.lines = self.full_string.splitlines()
        self.curindex = skip_line

    def readline(self):
        if self.curindex < len(self.lines):
            result = self.lines[self.curindex]
            self.curindex += 1
        else:
            result = None

        return result

    def read(self):
        return '\n'.join(self.lines[self.curindex:])

####################################################
# Remote Control Class
class RemoteControl():
    def __init__(self, ipaddr, id, pw):
        self.ipaddr = ipaddr
        self.userid = id
        self.userpw = pw
        self.client = self.connectSSH()

    def __del__(self):
        self.disconnectSSH()

    def IsServerAlive(self):
        if self.client is not None:
            return True

        return False

    def connectSSH(self):
        res = os.system('ping -c 1 ' + self.ipaddr)
        if res != 0:
            print 'Host is not reachable'
            return None

        cli = pxssh.pxssh()
        try:
            res = cli.login(self.ipaddr, self.userid, self.userpw, login_timeout = 30)
        except pxssh.ExceptionPxssh, e:
            print "LogIn Failed - [%s]" % str(e)

            return None

        return cli

    def disconnectSSH(self):
        if self.client is not None:
            self.client.logout()

    def sendline(self, commandline):
        if self.client is None:
            return

        if not self.client.isalive():
            self.connectSSH()

        self.client.sendline(commandline)

    def prompt(self):
        if self.client is None:
            return

        self.client.prompt()

    def runCommand(self, commandLine, skip_line = 1):
        if self.client is None:
            return None

        self.sendline(commandLine)
        self.prompt()

        return EmulateFileData(self.before, skip_line)

    @property
    def AdminUser(self):
        return self.userid

    @property
    def IPAddr(self):
        return self.ipaddr

    @property
    def before(self):
        if self.client is None:
            return ""

        return self.client.before

def PrepareVMManager(cliShell):
    stopVMMonitorProc(cliShell, 'VMMonitor.py')
    stopVMMonitorProc(cliShell, 'system_monitor.py')
    removeScheduledJob(cliShell)

def GetAllSystemInfo(cliShell):
    result_dict = {}
    result_dict['uptime'] = gather_uptime(cliShell)
    result_dict['ipaddr'] = gather_ipaddress(cliShell)
    result_dict['cpus'] = gather_cpus(cliShell)
    result_dict['users'] = gather_users(cliShell)
    result_dict['traffic'] = gather_traffics(cliShell, 'eth0')
    result_dict['platform'] = gather_platform(cliShell)
    result_dict['disks'] = gather_disks(cliShell)
    result_dict['disk_rw'] = gather_disk_rw(cliShell)
    result_dict['memory'] = gather_memory(cliShell)
    result_dict['cpu_usage'] = gather_cpu_usage(cliShell)
    result_dict['load'] = gather_load(cliShell)
    result_dict['netstat'] = gather_netstat(cliShell)

    return result_dict

usage = """ usage: %prog [options]
  ex> %prog -s 10.0.218.158 -e 10.0.218.189
"""
if __name__ == '__main__':
    print "#####################################"
    print "  Gathering System Information"
    print "#####################################"
    parser = OptionParser(usage = usage)
    parser.add_option("-i", "--admin-id", dest="admin_id", action="store", default="admin", help="Set Administrator(Root) id")
    parser.add_option("-p", "--admin-pw", dest="admin_pw", action="store", default="admin", help="Set Administrator(Root) password")
    parser.add_option("-s", "--start-addr", dest="start_addr", action="store", default="10.0.218.158", help="Set start address for systems")
    parser.add_option("-e", "--end-addr", dest="end_addr", action="store", default="10.0.218.189", help="Set end address for systems")

    (options, args) = parser.parse_args()

    address = options.start_addr.split('.')
    base_addr = '.'.join(address[:3])

    start_addr_index = int(address[3])
    address = options.end_addr.split('.')
    end_addr_index = int(address[3])

    print "Scanning - from [%s.%d] to [%s.%d]" % (base_addr, start_addr_index, base_addr, end_addr_index)
    print "######################################"

    for dest_index in range(start_addr_index, end_addr_index + 1):
        dest_addr = "%s.%d" % (base_addr, dest_index)
        print "Start to Gather Server Information - [%s]" % dest_addr
        CliClass = RemoteControl(dest_addr, options.admin_id, options.admin_pw)
        if CliClass is None:
            continue

        PrepareVMManager(CliClass)
        print GetAllSystemInfo(CliClass)

        del CliClass
