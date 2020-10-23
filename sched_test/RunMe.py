import sys
import time
from socket import SOCK_STREAM, socket, AF_INET, SOL_SOCKET, SO_REUSEADDR
import time
import random
import json
import collections

IP_ADDR = {}
IP_ADDR["ath1"]     = "1.2.8.4"
IP_ADDR["ath2"]     = "1.2.8.5"
IP_ADDR["ath3"]     = "1.2.8.6"
IP_ADDR["ath4"]     = "1.2.8.7"
IP_ADDR["ath5"]     = "1.2.8.8"
IP_ADDR["ath8"]     = "1.2.8.9"

HIGHEST_FREQ = {}       # MHz
LOWEST_FREQ  = {}
FREQ_RESO    = {}
for serv in IP_ADDR:
    if serv != "ath8":
        HIGHEST_FREQ[serv] = 2600
        LOWEST_FREQ[serv]  = 1200
        FREQ_RESO[serv]  = 200
    else:
        HIGHEST_FREQ[serv] = 2200
        LOWEST_FREQ[serv]  = 1200
        FREQ_RESO[serv]  = 100

CUR_ROUND           = 0     # hand shaking with simulator
CONFIG              = './sched_config.txt'
STATS_FILE          = './simulated_stats.txt'
DEC_FILE            = './sched_decision.txt'
RUN_TIME            = 60    # seconds
TOTAL_ROUND         = 60    # tototal rounds to run (RUN_TIME/INTERVAL)
INTERVAL            = 1     # seconds
TRACE_LIMIT         = 200
PORTS               = {}    # indexed by server
SOCKS               = {}
APP_SERVER          = {}
APP_CORE_NUM        = {}
SERVER_APP          = {}
APP_FREQ_VEC        = {}

CUR_QPS              = 0
QPS_EXPERIENCE       = []           # load ranges we have seen after choosing a target point or start observing 
QPS_RANGE_STEP       = 5000

# application specific
def get_stats():
    # end2end
    global STATS_FILE
    global APP_SERVER
    global APP_FREQ_VEC
    global CUR_QPS
    global CUR_ROUND

    lat_vec = {}
    round_match = False
    with open('%s' %STATS_FILE, 'r') as f:
        lines = f.readlines()
        if len(lines) == 0:
            return None
        for line in lines:
            data = line.split(';')
            # print data
            # latency, nginx, memc_get, memc_set, memc_find, pure_nginx
            lat_vec['end2end']      = int(data[0].split(':')[1])
            lat_vec['nginx']        = int(data[1].split(':')[1])
            lat_vec['memcached']    = int(data[2].split(':')[1])
            sim_round               = int(data[4].split(':')[1])
            if sim_round == CUR_ROUND:
                CUR_QPS             = int(data[3].split(':')[1])
                print 'CUR_QPS = ', CUR_QPS
                print data
                # CUR_ROUND += 1
                round_match = True
                break

    if not round_match:
        return None
    # show lat_vec
    for key in lat_vec:
        print key, ':', float(lat_vec[key]), ';',
    print ''
    return lat_vec

def pars_config():
    global CONFIG
    global HIGHEST_FREQ
    global APP_SERVER
    global SERVER_APP
    global APP_CORE_NUM
    global PORTS

    with open('%s' %CONFIG, 'r') as f:
        lines = f.readlines()
        for line in lines:
            (spec, words) = line.split(':')
            words = words.split()
            if spec == 'app':
                app              = words[0]
                server           = words[1]
                core_num         = int(words[2])
                APP_SERVER[app]  = server
                if app != 'jaeger':
                    if server not in SERVER_APP:
                        SERVER_APP[server] = []
                    SERVER_APP[server].append(app)
                    APP_FREQ_VEC[app] =  HIGHEST_FREQ[server]
                    APP_CORE_NUM[app] = core_num

            elif spec == 'server':
                server  = words[0]
                assert server in IP_ADDR    
                PORTS[server] = int(words[1])

    print APP_SERVER
    print SERVER_APP
    print PORTS

def set_freq_vec(memcached_freq, nginx_freq):
    global APP_FREQ_VEC

    """
        TODO: Fill in the code!

        This function would set the frequency
        of the memcached and nginx application
        in the microservice.

        Note, the microservice frequency
        range is [1200, 2600]. If you try
        to configure the frequency out of 
        this range, the uqSim will throw
        an Exception.
    """

    return


def send_cmd():
    global APP_FREQ_VEC
    global DEC_FILE
    global CUR_ROUND

    with open(DEC_FILE, 'w+') as f:
        cmd = "nginx: %u; memcached: %u; cur_round: %d" %(APP_FREQ_VEC['nginx'], APP_FREQ_VEC['memcached'], CUR_ROUND)
        CUR_ROUND += 1
        f.write(cmd)

def send_terminate():
    global SOCKS
    for serv in SOCKS:
        SOCKS[serv].sendall('terminate\n')

def show_freq_vec():
    global APP_FREQ_VEC
    string = ''
    for app in APP_FREQ_VEC:
        if app == 'jaeger':
            continue
        string += app + ':' + str(APP_FREQ_VEC[app]) + '\t'
    if string != '':
        string = string[:-1]
    return string

def help():
    print '1st: RUN_TIME (s)'
    print '2nd: INTERVAL (s)'
    print '3rd: target (ms)'
    print '4th: config file path (optional)'

# interval: monitor interval (s)
# target: target tail lat (ms)
def main():
    global HIGHEST_FREQ 
    global LOWEST_FREQ  
    global FREQ_RESO     
    global RUN_TIME
    global INTERVAL
    global APP_FREQ_VEC
    global FREQ_CHECKPOINT
    global CONFIG

    global CUR_QPS
    global TOTAL_ROUND
    global CUR_ROUND
    global QPS_EXPERIENCE

    if sys.argv[1] == '-h':
        help()
        return

    RUN_TIME = int(sys.argv[1])
    INTERVAL = float(sys.argv[2])
    TOTAL_ROUND = int(RUN_TIME/INTERVAL)
    print 'TOTAL_ROUND = ', TOTAL_ROUND
    # target in millisecond, change into ns
    target = int(sys.argv[3]) * 1000000.0

    if len(sys.argv) >= 5:
        CONFIG = sys.argv[4]

    pars_config()
    # connect()
    start_time          = time.time()
    prev_monitor_time   = time.time()

    while True:
        if CUR_ROUND >= TOTAL_ROUND:
            break   # terminate

        print "\nAt time: %f" %((CUR_ROUND + 1) * INTERVAL)
        print 'CUR_ROUND = ', CUR_ROUND
        stats = None
        while True:
            stats = get_stats()
            if stats != None:
                break
            else:
                time.sleep(INTERVAL)

        # simulator output stats in ns
        end2end_lat = stats['end2end']
        print 'end2end_lat = ', float(end2end_lat)/1000000.0, ' ms'
        del stats['end2end']


        ## TODO: Add your implementation to the set_freq_vec function.
        set_freq_vec(0, 0)
        send_cmd()
        print 'new freq_vec'
        print show_freq_vec()


if __name__ == '__main__':
    main()
