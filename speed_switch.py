"""Gates filter"""
import pathlib
import time
import logging
import re
import sys
import sqlite3
import pdb
from os import sep, mkdir
from os.path import dirname, exists
from statistics import mean
import datetime as dt
from datetime import timedelta
import speedtest


# constants kate test
APP_TMT = 60
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
        date_start_db = dt.datetime.now().date() - timedelta(days=1)
        date_end_db = dt.datetime.now().date() - timedelta(days=5)
        with conn:
            cd_statement = f'select speed from "{TB_NAME}" where date between date("{date_start_db}") and date("{date_end_db}")'
            print(cd_statement)
            measures = c.execute(cd_statement).fetchall()
            print(measures)
        if len(measures):
            m_measures = mean([el[0] for el in measures])
        else:
            m_measures = cur_measure
        if cur_measure*10 < m_measures:
            print("301")
            continue
        else:
            print("200")
            time.sleep(600)
    except Exception as ex: # pylint: disable=broad-exception-caught
        logger.warning(str(ex))
        time.sleep(10)
        print("500")
        continue
