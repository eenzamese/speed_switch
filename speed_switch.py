"""Speed switch"""
import pathlib
import time
import logging
import re
import sys
import sqlite3
import pdb
import ipaddress
from subprocess import Popen, PIPE
from os import sep, mkdir
from os.path import dirname, exists
from statistics import mean
import datetime as dt
from datetime import timedelta
import traceback
import speedtest
from netifaces import interfaces, ifaddresses, AF_INET
from pyroute2 import IPRoute


# inputs
APP_TMT = 60
SUCCESS_TMT = 600
FAIL_TMT = 60
ERR_TMT = 10
INET_HOST = '8.8.8.8'


# logging params
LOG_START_TIME = re.sub(r"\W+", "_", str(time.ctime()))
LOG_FMT_STRING = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

if getattr(sys, 'frozen', False):
    app_path = dirname(sys.executable)
    app_name = pathlib.Path(sys.executable).stem
    APP_RUNMODE = 'PROD'
    time.sleep(APP_TMT)
else:
    app_path = dirname(__file__)
    app_name = pathlib.Path(__file__).stem
    APP_RUNMODE = 'TEST'
LOG_DIR = f'{app_path}{sep}logs'
if not exists(LOG_DIR):
    mkdir(LOG_DIR)

LOG_FILENAME = f'{LOG_DIR}{sep}{app_name}_{LOG_START_TIME}.log'
log_handlers = [logging.StreamHandler()]

if APP_RUNMODE == 'PROD':
    log_handlers.append(logging.FileHandler(LOG_FILENAME))

logger = logging.getLogger(APP_RUNMODE)
logging.basicConfig(format=LOG_FMT_STRING,
                    datefmt='%d.%m.%Y %H:%M:%S',
                    level=logging.INFO, # NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL
                    handlers=log_handlers)


def ip4_addresses():
    """Get interface IP addresses"""
    ip_list = []
    for interface in interfaces():
        if interface == 'lo':
            continue
        for link in ifaddresses(interface)[AF_INET]:
            ip_list.append((link['addr'], interface))
    return ip_list


def gw4_address():
    """Get current gateway"""
    ipr = IPRoute()
    gw = [el[1] for el in ipr.route("get",dst=INET_HOST)[0]["attrs"] if "RTA_GATEWAY" in el[0]]
    if gw:
        gw = gw[0]
    else:
        logger.critical('Traceroute failed')
        sys.exit()
    nic_arr = [el for el in ip_addrs if ipaddress.ip_address(gw) in ipaddress.ip_network(f'{el[0]}/24', False)]
    if nic_arr:
        nic = nic_arr[0]
    else:
        logger.critical('List ifaces failed')
        sys.exit()
    return (gw,nic)


def conn_name(in_nic):
    """Get connection with Network Manager"""
    cmd = "nmcli -f name,device -t conn show"
    sp = Popen([cmd],stderr=PIPE, stdout=PIPE, shell=True)
    (out, err) = sp.communicate()
    if err:
        logger.critical('NMCLI error %s', err)
        sys.exit()
    if out:
        out = out.decode('UTF-8').splitlines()
    conn_name = [el for el in out if in_nic in el]
    logger.debug('Connection name %s', conn_name)
    if conn_name:
        logger.debug('Connection name unparsed %s', conn_name)
        conn_name = conn_name[0]
        logger.debug('Connection name parsed %s', conn_name)
        conn_name = conn_name.split(':')
        logger.debug('Connection name final %s', conn_name)
        conn_name = conn_name[0]
    else:
        logger.critical('There are no available connections')
        sys.exit()
    return conn_name


def tb_init(in_table_name, in_conn=None, in_c=None):
    """Table initialization"""
    result = {'result': False, 'content': ''}
    table_name = in_table_name
    try:
        with in_conn:
            ti_statement = (f'create table if not exists "{table_name}" '
                            '(date text, '
                            'speed float);')
            in_c.execute(ti_statement)
        logger.debug('Tables "measures" created successfully')
        with in_conn:
            ti_statement = (f'create table if not exists {table_name}_attempts '
                            '(date text, '
                            'fails interger);')
            in_c.execute(ti_statement)
        with conn:
            cd_statement = f"select fails from {TB_NAME}_attempts where rowid=1;"
            fails = c.execute(cd_statement).fetchone()
            logger.debug(cd_statement)
            if not fails:
                with in_conn:
                    ti_statement = f"insert into {TB_NAME}_attempts \
                                values('{time.ctime()}', 0);"
                    in_c.execute(ti_statement)
    except Exception as ex: # pylint: disable=broad-exception-caught
        result = {'result': False, 'content': str(ex)}
        return result
    result = {'result': True, 'content': ''}
    return result


def change_nic_metric(in_conn_name, in_iface_name):
    logger.debug('Change nic metric conn name %s', in_conn_name)
    cmd = f"nmcli conn modify '{in_conn_name}' ipv4.route-metric {int(time.time())}"
    logger.info('Change NIC metric command - %s', cmd)
    sp = Popen([cmd],stderr=PIPE, stdout=PIPE, shell=True)
    (out, err) = sp.communicate()
    if err:
        logger.critical('NMCLI error %s', err)
        sys.exit()
    time.sleep(1)
    cmd = f"nmcli device reapply {in_iface_name}"
    logger.info('Reapply to device - %s', cmd)
    sp = Popen([cmd],stderr=PIPE, stdout=PIPE, shell=True)
    (out, err) = sp.communicate()
    time.sleep(1)
    # if err:
    #     logger.critical('NMCLI error %s', err)
    #     sys.exit()
    # time.sleep(1)
    # sys.exit()
    # cmd = f"nmcli connection down '{in_conn_name}'"
    # logger.info('Switch off connection - %s', cmd)
    # sp = Popen([cmd],stderr=PIPE, stdout=PIPE, shell=True)
    # (out, err) = sp.communicate()
    # time.sleep(1)
    # if err:
    #     logger.critical('NMCLI error %s', err)
    #     sys.exit()
    # cmd = f"nmcli connection up '{in_conn_name}'"
    # logger.info('Switch on connection - %s', cmd)
    # sp = Popen([cmd],stderr=PIPE, stdout=PIPE, shell=True)
    # (out, err) = sp.communicate()
    # time.sleep(1)
    # if err:
    #     logger.critical('NMCLI error %s', err)
    #     sys.exit()
    return out

DB_NAME = f'{app_path}{sep}{app_name}_db.sqlite'
TB_NAME = 'measures'


# DB connection check
try:
    conn = sqlite3.connect(DB_NAME,  check_same_thread=False)
    c = conn.cursor()
    str_out = 'DB connection is OK' # pylint: disable=invalid-name
    logger.info(str_out)
except Exception as ex: # pylint: disable=broad-exception-caught
    str_out = 'DB connection is FAIL'# pylint: disable=invalid-name
    logger.critical(str_out)
    sys.exit()


tb_init_result = tb_init(TB_NAME, in_conn = conn, in_c = c)
if not tb_init_result['result']:
    logger.critical(tb_init_result['content'])
    sys.exit()


while True:
    servers = []
    THREADS = None
    try:
        ip_addrs = ip4_addresses()
        logger.info('Get IP addresses')
        gw_addr = gw4_address()
        logger.info('Get GW address')
        s = speedtest.Speedtest(secure=True)
        s.get_servers(servers)
        s.get_best_server()
        s.download(threads=THREADS)
        s.upload(threads=THREADS)
        s.results.share()
        cur_measure = s.results.dict()['download']
        if not cur_measure:
            logger.critical('Speed service not working')
            sys.exit()
        logger.info('Measure Internet speed')
        with conn:
            statement = f"insert into '{TB_NAME}' \
                        values('{dt.datetime.now().date()}', \
                        '{cur_measure}');"
            c.execute(statement)
        logger.info('Save measure')
        date_start_db = dt.datetime.now().date() - timedelta(days=5)
        date_end_db = dt.datetime.now().date() - timedelta(days=1)
        logger.info('Get past measures from %s till %s', date_start_db, date_end_db)
        with conn:
            cd_statement = f"select speed from '{TB_NAME}' where date between date('{date_start_db}') and date('{date_end_db}');"
            logger.debug(cd_statement)
            measures = c.execute(cd_statement).fetchall()
        logger.info('Past measures are - %s', measures)
        if measures:
            m_measures = mean([el[0] for el in measures])
            logger.info('Measures mean value - %s', m_measures)
        else:
            logger.info('Past measures not available. Get last measures')
            with conn:
                cd_statement = f"select speed from {TB_NAME} where rowid in ((select max(rowid)from {TB_NAME}), (select max(rowid)from {TB_NAME})-1);"
                logger.info(cd_statement)
                measures = c.execute(cd_statement).fetchall()
            logger.info('Last measures are - %s', measures)
            m_measures = mean([el[0] for el in measures])
            logger.info('Last measures mean is - %s', m_measures)
        if cur_measure*10 < m_measures:
            logger.info('Connection speed downgraded')
            with conn:
                # pdb.set_trace()
                statement = f"select fails from {TB_NAME}_attempts where rowid=1;"
                fails = c.execute(statement).fetchone()
            logger.debug('SQL statement - %s', statement)
            logger.debug('Fails value - %s', fails)
            logger.info('Try couple times')
            if not fails:
                logger.critical('DB corrupted while statement is %s', statement)
                sys.exit()
            fails = int(fails[0])
            logger.info('Amout of fails is %s', fails)
            if fails > 5:
                logger.info('Switch NIC decision')
                with conn:
                    statement = f"update {TB_NAME}_attempts set fails=0;"
                    c.execute(statement)
                c_name = conn_name(gw_addr[1][1])
                change_nic_metric(c_name, gw_addr[1][1])
                with conn:
                    statement = f"delete from {TB_NAME};"
                    c.execute(statement)
                logger.info('Switch NIC copleted')
            else:
                logger.info('Trying...')
                with conn:
                    statement = f"update {TB_NAME}_attempts set fails={fails+1};"
                    c.execute(statement)
            logger.info('Time to sleep %s', FAIL_TMT)
            time.sleep(FAIL_TMT)
            continue
        else:
            logger.info('Speed is OK. Reset fails count')
            with conn:
                statement = f"update {TB_NAME}_attempts set fails=0;"
                c.execute(statement)
            logger.info('Address: %s', gw_addr[0])
            logger.info('Iface: %s', gw_addr[1][1])
            logger.info('Time to sleep %s', SUCCESS_TMT)
            time.sleep(SUCCESS_TMT)
    except Exception as ex: # pylint: disable=broad-exception-caught
        logger.warning(str(ex))
        logger.warning(traceback.format_exc())
        logger.info('Time to sleep %s', SUCCESS_TMT)
        time.sleep(ERR_TMT)
        continue
