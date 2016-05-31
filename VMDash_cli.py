#-*- coding: utf-8 -*-
import json
import subprocess
from optparse import OptionParser
from remote_manager import RemoteControl, PrepareVMManager, GetAllSystemInfo
from system_control_cmd import *

import time, threading

ServerFactory = None

#################################################################################
class ServerListFactory():
    def __init__(self):
        self.ServerList = []

    def GetServerList(self):
        return self.ServerList

    def AppendServerInfo(self, RemoteServerObject):
        print "Remote Server [%s] is added" % (RemoteServerObject.IPAddr)
        serverInfo = ServerInfo(RemoteServerObject)
        serverInfo.PrepareVMManager()

        self.ServerList.append(serverInfo)

    def RefreshServerInfo(self):
        for server in self.ServerList:
            print "Gather Server Info - [%s]" % server.IPAddr
            server.RefreshSystemInfo(stacked = True, pid_loads = True)
        pass

    def IsServerAlive(self, ipaddr):
        for server in self.ServerList:
            if server.IPAddr == ipaddr:
                return True

        return False

KEEP_STATISTICS = 6 * 24 * 7        # 7Days (10 Minutes)
DURA_STATISTICS = 10                # 10Minutes
DURA_FULLSCAN = 6                   # 1 hour

class ServerInfo():
    def __init__(self, remoteObject, http_send = True):
        self.remoteObject = remoteObject
        self.data_list = []
        self.current = {}
        self.http_send = http_send
        self.datafile = '__statistics_%s.json' % self.IPAddr
        try:
            with open(self.datafile, 'r') as f:
                self.data_list = json.load(f)
            self.setCurrentStatistics(self.data_list[-1])
        except:
            self.data_list = []

    def AddStatistics(self, result):
        self.data_list.append(result)
        if len(self.data_list) > KEEP_STATISTICS:
            del self.data_list[0]

        with open(self.datafile, 'w') as f:
            f.write(json.dumps(self.data_list))

    def GetCurrentStatistics(self):
        return self.current

    def setCurrentStatistics(self, result):
        self.current = result
        if self.http_send:
            jsondata = json.dumps(result)
            subprocess.call(['curl', '-H', 'Content-type: application/json', '-X', 'POST', 'localhost:5000/messages', '-d', jsondata])

    def PrepareVMManager(self):
        stopVMMonitorProc(self.remoteObject, 'VMMonitor.py')
        stopVMMonitorProc(self.remoteObject, 'system_monitor.py')
        removeScheduledJob(self.remoteObject)

    def RefreshSystemInfo(self, stacked = False, pid_loads = True):
        result_dict = {}
        result_dict['update_time'] = int(time.time())
        result_dict['admin_user'] = self.remoteObject.AdminUser
        result_dict['statistic_file'] = self.datafile
        result_dict['myipaddr'] = self.IPAddr
        result_dict['uptime'] = gather_uptime(self.remoteObject)
        result_dict['ipaddr'] = gather_ipaddress(self.remoteObject)
        result_dict['cpus'] = gather_cpus(self.remoteObject)
        result_dict['users'] = gather_users(self.remoteObject)
        result_dict['traffic'] = gather_traffics(self.remoteObject, 'eth0')
        result_dict['platform'] = gather_platform(self.remoteObject)
        result_dict['disks'] = gather_disks(self.remoteObject)
        result_dict['disk_rw'] = gather_disk_rw(self.remoteObject)
        result_dict['memory'] = gather_memory(self.remoteObject)
        if pid_loads:
            result_dict['cpu_usage'] = gather_cpu_usage(self.remoteObject)
        result_dict['load'] = gather_load(self.remoteObject)
        result_dict['netstat'] = gather_netstat(self.remoteObject)
        result_dict['last'] = gather_last_used(self.remoteObject)

        if stacked == True:
            self.AddStatistics(result_dict)

        self.setCurrentStatistics(result_dict)

    @property
    def RemoteServer(self):
        return self.remoteObject

    @property
    def IPAddr(self):
        return self.remoteObject.IPAddr

usage = """ usage: %prog [options]
  ex> %prog -s 10.0.218.158 -e 10.0.218.189
"""
if __name__ == '__main__':
    print "#####################################"
    print "  Private Cloud Dashboard"
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

    ServerFactory = ServerListFactory()
    print "Scanning - from [%s.%d] to [%s.%d]" % (base_addr, start_addr_index, base_addr, end_addr_index)
    print "######################################"
    for dest_index in range(start_addr_index, end_addr_index + 1):
        dest_addr = "%s.%d" % (base_addr, dest_index)
        print "Trying to connect server [%s]" % dest_addr
        RemoteServer = RemoteControl(dest_addr, options.admin_id, options.admin_pw)
        if RemoteServer.IsServerAlive():
            ServerFactory.AppendServerInfo(RemoteServer)

    scanning_added = 0
    while True:
        ServerFactory.RefreshServerInfo()
        time.sleep(60 * DURA_STATISTICS)     # 10 minute sleep
        scanning_added += 1
        if (scanning_added % DURA_FULLSCAN) == 0:
            for dest_index in range(start_addr_index, end_addr_index + 1):
                dest_addr = "%s.%d" % (base_addr, dest_index)
                if not ServerFactory.IsServerAlive(dest_addr):
                    print "Trying to connect server [%s]" % dest_addr
                    RemoteServer = RemoteControl(dest_addr, options.admin_id, options.admin_pw)
                    if RemoteServer.IsServerAlive():
                        ServerFactory.AppendServerInfo(RemoteServer)
