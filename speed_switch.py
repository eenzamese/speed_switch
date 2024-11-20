"""Gates filter"""
import pathlib
import time
import logging
import re
import sys
import sqlite3
import pdb
import ipaddress
from os import sep, mkdir
from os.path import dirname, exists
from statistics import mean
import datetime as dt
from datetime import timedelta
import traceback
import speedtest
from netifaces import interfaces, ifaddresses, AF_INET
from pyroute2 import IPRoute



# constants kate test
APP_TMT = 60
SUCCESS_TMT = 600
FAIL_TMT = 60
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
    log_handlers = log_handlers.append(logging.FileHandler(LOG_FILENAME))

logger = logging.getLogger(APP_RUNMODE)
logging.basicConfig(format=LOG_FMT_STRING,
                    datefmt='%d.%m.%Y %H:%M:%S',
                    level=logging.INFO, # NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL
                    handlers=[logging.FileHandler(LOG_FILENAME),
                              logging.StreamHandler()])


def ip4_addresses():
    ip_list = []
    for interface in interfaces():
        if interface == 'lo':
            continue
        for link in ifaddresses(interface)[AF_INET]:
            print(link)
            ip_list.append((link['addr'], interface))
    return ip_list


def tb_init(in_table_name, in_conn=None, in_c=None):
    """Get table initialization"""
    result = {'result': False, 'content': ''}
    table_name = in_table_name
    try:
        with in_conn:
            ti_statement = (f'create table if not exists "{table_name}" '
                            '(date text, '
                            'speed float);')
            in_c.execute(ti_statement)
        logger.debug(f'Tables "measures" created successfully')
        with in_conn:
            ti_statement = (f'create table if not exists "{table_name}_attempts" '
                            '(date text, '
                            'fails interger);')
            in_c.execute(ti_statement)
        with in_conn:
            ti_statement = f"insert into '{TB_NAME}_attempts' \
                        values('{time.ctime()}', 0);"
            in_c.execute(ti_statement)
    except Exception as ex: # pylint: disable=broad-exception-caught
        result = {'result': False, 'content': str(ex)}
        return result
    result = {'result': True, 'content': ''}
    return result


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
    threads = None
    try:
        ip_addrs = ip4_addresses()
        ipr=IPRoute()
        gw = [el[1] for el in ipr.route("get",dst="8.8.8.8")[0]["attrs"] if "RTA_GATEWAY" in el[0]]
        if gw:
            gw=gw[0]
        nic_arr = [el for el in ip_addrs if ipaddress.ip_address(gw) in ipaddress.ip_network(f'{el[0]}/24', False)])
        if nic_arr:
            nic_arr = nic_arr[0]
        s = speedtest.Speedtest(secure=True)
        s.get_servers(servers)
        s.get_best_server()
        s.download(threads=threads)
        s.upload(threads=threads)
        s.results.share()
        cur_measure = s.results.dict()['download']
        with conn:
            statement = f"insert into '{TB_NAME}' \
                        values('{dt.datetime.now().date()}', \
                        '{cur_measure}');"
            c.execute(statement)
        date_start_db = dt.datetime.now().date() - timedelta(days=5)
        date_end_db = dt.datetime.now().date() - timedelta(days=1)
        with conn:
            cd_statement = f"select speed from '{TB_NAME}' where date between date('{date_start_db}') and date('{date_end_db}');"
            logger.debug(cd_statement)
            measures = c.execute(cd_statement).fetchall()
        if measures:
            m_measures = mean([el[0] for el in measures])
        else:
            m_measures = cur_measure
        if cur_measure*10 < m_measures:
            with conn:
                statement = f"select fails from '{TB_NAME}_attempts where rowid=1;"
                fails = c.execute(cd_statement).fetchone()
                logger.info(statement)
            if not fails:
                logger.critical('DB corrupted')
                sys.exit()
            fails = int(fails[0])
            if fails>5:
                print('301')
                with conn:
                    statement = f"update '{TB_NAME}_attempts' set fails=0;"
                    c.execute(statement)
            else:
                with conn:
                    statement = f"update '{TB_NAME}_attempts' set fails={fails+1};"
                    c.execute(statement)
            time.sleep(FAIL_TMT)
            continue
        else:
            with conn:
                statement = f"update '{TB_NAME}_attempts' set fails=0;"
                c.execute(statement)   
            print("200")
            time.sleep(SUCCESS_TMT)
    except Exception as ex: # pylint: disable=broad-exception-caught
        logger.warning(str(ex))
        logger.warning(traceback.format_exc())
        time.sleep(10)
        print("500")
        continue
