#-*- coding: utf-8 -*-
import json
import flask
from flask import abort, request as req

from optparse import OptionParser
from remote_manager import RemoteControl, PrepareVMManager, GetAllSystemInfo
from system_control_cmd import *
from VMDash_cli import KEEP_STATISTICS

import time, threading

VMDash = flask.Flask(__name__)

ServerCurrentStatistics = {}

@VMDash.route('/messages', methods = ['POST'])
def get_messages():
    global ServerCurrentStatistics

    if flask.request.headers['Content-Type'] == 'application/json':
        jsonData = flask.request.json
        ServerIPAddr = jsonData['myipaddr']
        if not ServerCurrentStatistics.has_key(ServerIPAddr):
            ServerCurrentStatistics[ServerIPAddr] = []
        ServerCurrentStatistics[ServerIPAddr].append(jsonData)
        if len(ServerCurrentStatistics[ServerIPAddr]) > KEEP_STATISTICS:
            del ServerCurrentStatistics[ServerIPAddr][0]

        return ''

    return '415 Unsupport File'

def GetRangePanelType(value):
    if value < 50:
        return 'panel-primary'
    if value < 80:
        return 'panel-yellow'

    return 'panel-red'

def convertTimeFormat(curtime):
    return '%04d-%02d-%02d %02d:%02d' % (curtime.tm_year, curtime.tm_mon, curtime.tm_mday, curtime.tm_hour, curtime.tm_min)

@VMDash.route('/details/<ipaddr>')
@VMDash.route('/details/<ipaddr>/<listindex>')
def details(ipaddr, listindex = None):
    global ServerCurrentStatistics

    overall = {}
    summary = []
    cpu_usage_title = []
    cpu_usage = []
    last_usage_title = []
    last_usage = []
    last_usage_summary = []
    if ServerCurrentStatistics.has_key(ipaddr):
        if listindex is None:
            listindex = len(ServerCurrentStatistics[ipaddr]) - 1
        listindex = int(listindex)
        ServerInfo = ServerCurrentStatistics[ipaddr][listindex]
        hostname = ServerInfo['platform']['hostname']
        osname = ServerInfo['platform']['osname']
        kernel = ServerInfo['platform']['kernel']

        for diskinfo in ServerInfo['disks']:
            try:
                if diskinfo[5] == '/':
                    total_disk = diskinfo[1]
                    percent_disk = int(diskinfo[4][:-1])
                    break
            except:
                continue
        else:
            total_disk = 'Unknown'
            percent_disk = 0

        cur_url = '/details/%s' % ipaddr
        server_list = ServerCurrentStatistics.keys()
        server_list.sort()
        cur_index = server_list.index(ipaddr)
        next_url = '/details/%s' % server_list[(cur_index + 1) % len(server_list)]
        prev_url = '/details/%s' % server_list[cur_index - 1]

        try:
            listindex = int(listindex)
        except:
            listindex = len(ServerCurrentStatistics[ipaddr]) - 1

        prevIndex = max(0, listindex - 1)
        nextIndex = min(listindex + 1, len(ServerCurrentStatistics[ipaddr]) - 1)
        prevServerInfo = ServerCurrentStatistics[ipaddr][prevIndex]
        nextServerInfo = ServerCurrentStatistics[ipaddr][nextIndex]

        curtime = convertTimeFormat(time.localtime(ServerInfo['update_time']))
        prevtime =  convertTimeFormat(time.localtime(prevServerInfo['update_time']))
        nexttime =  convertTimeFormat(time.localtime(nextServerInfo['update_time']))
        curtimeurl = '/details/%s/%d' % (ipaddr, listindex)
        nexttimeurl = '/details/%s/%d' % (ipaddr, nextIndex)
        prevtimeurl = '/details/%s/%d' % (ipaddr, prevIndex)

        overall = {'ipaddr' : ipaddr, 'hostname':hostname, 'osname':osname, 'kernel':kernel,
                   'uptime':ServerInfo['uptime'], 'core':str(ServerInfo['cpus']['cpus']),
                   'mem':'%dMB' % ServerInfo['memory']['total'],
                   'disk':total_disk, 'admin':ServerInfo['admin_user'],
                   'cururl':cur_url, 'prevurl':prev_url, 'nexturl':next_url, 'homeurl':'/',
                   'curtimeurl':curtimeurl, 'prevtimeurl':prevtimeurl, 'nexttimeurl':nexttimeurl,
                   'curtime':curtime, 'prevtime': prevtime, 'nexttime' : nexttime}

        # CPU Load
        #import pprint
        #pprint.pprint(ServerInfo)
        item = {}
        #print ServerInfo['cpu_usage']
        cpu_usage = int(ServerInfo['cpu_usage']['used'])
        item['title'] = 'CPU'
        item['value'] = str(cpu_usage) + '%'
        item['level'] = GetRangePanelType(cpu_usage)
        summary.append(item)

        # User
        connected_user = 0
        userlist = []
        for userinfo in ServerInfo['users']:
            if ServerInfo['admin_user'] != userinfo[0]:
                if userinfo[0] not in userlist:
                    userlist.append(userinfo[0])
                connected_user += 1

        item = {}
        item['title'] = 'Users(connected/id)'
        item['value'] = '%d/%d' % (connected_user, len(userlist))
        item['level'] = 'panel-primary'
        if connected_user < 1:
            item['level'] = 'panel-red'
        summary.append(item)

        item = {}
        item['title'] = 'Disk'
        item['value'] = '%d%%' % percent_disk
        item['level'] = GetRangePanelType(percent_disk)
        summary.append(item)

        item = {}
        item['title'] = 'Memory'
        item['value'] = '%d%%' % ServerInfo['memory']['percent']
        item['level'] = GetRangePanelType(ServerInfo['memory']['percent'])
        summary.append(item)

        cpu_usage_title = ['User', 'CPU(%)', 'MEM(%)', 'VSZ', 'RSS', 'TTY', 'STAT', 'START', 'DUR', 'COMMAND']
        cpu_usage = []

        color_side = ['danger', 'warning', 'success', 'active']
        for index, usage in enumerate(ServerInfo['cpu_usage']['top_20']):
            item = {}
            item['level'] = color_side[(index / 5) % 4]
            item['list'] = [usage[0], usage[2], usage[3], usage[4], usage[5], usage[6], usage[7], usage[8], usage[9], usage[10]]
            cpu_usage.append(item)

        last_usage_title = ['User', 'TTY', 'IPAddress', 'Time']
        last_usage = []

        color_side = ['danger', 'warning', 'success', 'active']
        for index, usage in enumerate(ServerInfo['last']):
            item = {}
            if 'still' in usage[3]:
                item['level'] = 'danger'
            else:
                item['level'] = 'active'
            item['list'] = [usage[0], usage[1], usage[2], usage[3]]
            last_usage.append(item)

        skip_users = [ServerInfo['admin_user'], 'reboot', 'root', 'wtmp', ]
        user_summary = {}
        for usage in ServerInfo['last']:
            if usage[0] not in skip_users:
                if not user_summary.has_key(usage[0]):
                    user_summary[usage[0]] = {'flag':False, 'data':''}

                if not user_summary[usage[0]]['flag']:
                    user_summary[usage[0]]['flag'] = True
                    user_summary[usage[0]]['data'] = usage
                elif 'still' in usage[3]:
                    user_summary[usage[0]]['data'] = usage

        user_list = user_summary.keys()
        user_list.sort()
        for user in user_list:
            usage = user_summary[user]['data']
            item = {}
            if 'still' in usage[3]:
                item['level'] = 'success'
            else:
                item['level'] = 'danger'
            item['list'] = [usage[0], usage[1], usage[2], usage[3]]
            last_usage_summary.append(item)

    return flask.render_template('details.html', overall = overall, summary = summary,
                                 cpu_usage_title = cpu_usage_title, cpu_usage = cpu_usage,
                                 last_usage_title = last_usage_title, last_usage = last_usage, last_usage_summary = last_usage_summary)

@VMDash.route('/')
@VMDash.route('/index')
def index():
    global ServerCurrentStatistics

    headers = ['IP', 'Name', 'CPU', 'MEM', 'DISK', 'Dist', 'User', 'Updated']

    ServerIPList = ServerCurrentStatistics.keys()
    ServerIPList.sort()

    data = []
    for serverIP in ServerIPList:
        serverInfo = ServerCurrentStatistics[serverIP][-1]
        all_data = serverInfo

        level = 'active'
        ipaddr = serverIP
        hostname = all_data['platform']['hostname']
        cpu = str(all_data['cpu_usage']['used']) + '% - ' + str(all_data['cpus']['cpus']) + ' cores'
        mem = '%dMB(%d%%)' % (all_data['memory']['total'], all_data['memory']['percent'])
        for diskinfo in all_data['disks']:
            if len(diskinfo) < 6:
                disk = 'Undefined'
                continue
            if diskinfo[5] == '/':
                disk = "%s/%s(%s)" % (diskinfo[2], diskinfo[1], diskinfo[4])

                percent = int(diskinfo[4][:-1])
                if percent > 85:
                    level = 'danger'
                break
        else:
            disk = 'Undefined'

        userlist = []
        for userinfo in all_data['users']:
            if userinfo[0] not in userlist:
                if all_data['admin_user'] != userinfo[0]:
                    userlist.append(userinfo[0])

        if len(userlist) <= 1:
            level = 'info'
        if len(userlist) > 3:
            users = ';'.join(userlist[:3]) + '...(%d)' % len(userlist)
        else:
            users = ';'.join(userlist)

        dist = all_data['platform']['osname']

        updated_time = convertTimeFormat(time.localtime(all_data['update_time']))
        item = {'list':[ipaddr, hostname, cpu, mem, disk, dist, users, updated_time]}
        item['level'] = level
        item['url'] = '/details/%s/%d' % (ipaddr, len(ServerCurrentStatistics[serverIP]) - 1)
        data.append(item)

    return flask.render_template('index.html', table_headers = headers, table_data = data)

if __name__ == '__main__':
    print "#####################################"
    print "  Private Cloud Dashboard"
    print "#####################################"

    # Load Analytic Statistics '__statistics_IPADDR.json'
    statistic_files = []
    path = './'
    for file in os.listdir(path):
        full_name = os.path.join(path, file)
        if os.path.isfile(full_name) and ('__statistics' in full_name):
            statistic_files.append(full_name)

    for filename in statistic_files:
        new_name = filename.replace('./__statistics_', '')
        if not filename.endswith('.json'):
            continue

        ipaddr = new_name[:-5]
        with open(filename, 'r') as f:
            newstatis = json.load(f)

        ServerCurrentStatistics[ipaddr] = newstatis

    VMDash.run(debug = True, host="0.0.0.0", port=5000)


