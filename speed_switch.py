"""Gates filter"""
import socket
import time
import logging
import re
import sys
import sqlite3
from os import listdir, sep
from os.path import dirname, basename
import speedtest
from statistics import mean
from datetime import date, datetime, time, timedelta


# constants
APP_TMT = 60
LOG_START_TIME = re.sub(r"\W+", "_", str(time.ctime()))


if getattr(sys, 'frozen', False):
    app_path = dirname(sys.executable)
    app_name = basename(sys.executable)
    APP_RUNMODE = 'PROD'
    time.sleep(APP_TMT)
else:
    app_path = dirname(__file__)
    app_name = basename(__file__)
    APP_RUNMODE = 'TEST'


LOG_FMT_STRING = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILENAME = f'{app_path}{sep}{app_name}_{LOG_START_TIME}.log'

logger = logging.getLogger(APP_RUNMODE)
logging.basicConfig(format=LOG_FMT_STRING,
                    datefmt='%d.%m.%Y %H:%M:%S',
                    level=logging.INFO, # NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL
                    handlers=[logging.FileHandler(LOG_FILENAME),
                              logging.StreamHandler()])
sys.exit()

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
    except Exception as ex: # pylint: disable=broad-exception-caught
        result = {'result': False, 'content': str(ex)}
        return result
    result = {'result': True, 'content': ''}
    return result



DB_NAME = f'{app_path}{sep}db_online.sqlite'
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
        s = speedtest.Speedtest(secure=True)
        s.get_servers(servers)
        s.get_best_server()
        s.download(threads=threads)
        s.upload(threads=threads)
        s.results.share()
        cur_mesure = s.results.dict()['download']
        with conn:
            statement = f"insert into '{TB_NAME}' \
                        values('{str(time.ctime())}', \
                        '{str(1)}');"
            c.execute(statement)
        date_start = datetime.combine(date.toda(), time())
        date_end = datetime.combine(date.toda(), time()) + timedelta(days=5)
        with conn:
            cd_statement = (f'select measure from "{TB_NAME}" '
                         'where date between "{date_start}" and "{date_end}"')
            measures = c.execute(cd_statement).fetchall()
            m_measures = mean(measures)
        if cur_measure*10 < m_measures:
            BLOCK_ICMP_CMD = 'netsh advfirewall firewall add rule \
                              name="ICMP ALLOW" protocol=icmpv4:8,any \
                              dir=in acction=allow'
            os.system(BLOCK_ICMP_CMD)
        else:
            ALLOW_ICMP_CMD = 'netsh advfirewall firewall add rule \
                            name="ICMP ALLOW" protocol=icmpv4:8,any \
                            dir=in acction=allow'
            os.system(ALLOW_ICMP_CMD)
    except Exception as ex: # pylint: disable=broad-exception-caught
        logger.warning(str(ex))
        time.sleep(3)
        continue
    for gate_address in data_r:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((gate_address, 443))
        if result == 0:
            str_out = f'Gate address is {gate_address}'
            logger.info(str_out)
            servers.append(gate_address)
        else:
            STR_OUT = 'Gate address is FAILED'
            logger.info(STR_OUT)
            continue
        sock.close()
    with open(OUTPUT_FILE, 'w') as file: # pylint: disable=unspecified-encoding
        DATA_W = '\n'.join(servers)
        file.write(DATA_W)
    STR_OUT = 'State is OK'
    logger.info(STR_OUT)
    time.sleep(1800)

sys.exit()
