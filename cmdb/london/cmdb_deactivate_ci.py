#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""Script for bulk, per device class update of the CMDB.
    Operation:
        Gets list of active CMDB product tables mapped from SL. 
        Iterate the list of tables.
        For each table - query the list of CIs from Servicenow where:
            CI has an associated SL device ID
            CI is installed state of active
            
            Cache a list of SL devices IDs for that product table
            For each returned CI, lookup the CI SL device ID in the cached device ID list
            If the device ID no longer exists in SL:
                update the ServiceNow asset for that CI to "retired" state
"""

from silo_common.database import local_db
import fidelus.silo
import fidelus.servicenow
from datetime import datetime
from datetime import timedelta
from time import time
import logging


def cmdb_tables():
    """Return list of CMDB CI tables in use."""
    dbc = local_db()
    sql = """select cmdb_table from fidelus.snow_london_cmdb where sys_id is not null group by cmdb_table"""
    dbc.execute(sql)
    results = dbc.fetchall()
    dbc.close()
    out = []
    for i in results: out.append(i[0])
    return out

def devices_by_table(table):
    """Return SL device ids based on a cmdb table."""
    dbc = local_db()
    sql = """select mdev.id
                from master_dev.legend_device mdev
                inner join fidelus.snow_london_cmdb snow on mdev.class_type = snow.class_type
                inner join master_custom.ent_device_custom mcustom on mdev.id = mcustom.ent_id
                where snow.cmdb_table = '%s'""" % table
    dbc.execute(sql)
    results = dbc.fetchall()
    dbc.close()
    logging.info("SL query: %s\n" % sql)
    out = []
    for i in results: out.append(i[0])
    return out


timestamp_start = int(time())
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, filename="cmdb_deactivate_ci.log", \
     filemode="a", format="%(asctime)s: %(name)s: %(levelname)s: %(message)s")

logging.info("Start CMDB Asset / CI Deactivation\n\n")

snow_ci_dict = {"install_status": 7}


# get the cmdb table names in use
logging.info("Getting the list of CMDB tables from SL")
tables = cmdb_tables()
asset_table = "alm_asset"

for table in tables:
    logging.info(" ")
    logging.info("Processing CIs from table: %s" % table)
    
    # get the table entries for active CIs
    logging.info("ServiceNow query for CIs in: %s" % table)
    cmdb = fidelus.servicenow.cmdb_active_by_table(table)
    
    try:
        if cmdb["result"]:
            logging.info("Active CIs: %s" % len(cmdb["result"]))
            
            # get SL devices for this cmdb table
            logging.info("Build SL device id cache for devices mapped to this CI class")
            devices_cache = devices_by_table(table)
            # devices_cache = []
            # for dev in devices: devices_cache.append(dev[0])
            logging.info("Active SL devices for this class: %s" % len(devices_cache))
            logging.info("Device ID cache: %s" % devices_cache)
            
            for ci in cmdb["result"]:
                logging.info("Processing CI: %s, %s, SL Device: %s" % (ci["name"], ci["u_account.name"], ci["u_sciencelogic_id"]))
                
                if int(ci["u_sciencelogic_id"]) not in devices_cache:
                    
                    # update Asset to retired state
                    logging.info("\tCI: %s is not actively monitored, updating Asset to retired state" % ci["name"])
                    
                    # get the asset syid
                    ci_sys_id = str(ci["sys_id"])
                    response_ci_did = fidelus.servicenow.snow_ci_query(None, 'sys_id=%s' % ci_sys_id)
                    asset_sysid = str(response_ci_did["result"][0]["asset.sys_id"])
                    
                    logging.info("\tCI: %s, Asset: %s" % (ci_sys_id, asset_sysid))
                    logging.info(" ")
                    fidelus.servicenow.snow_ci_update(asset_table, snow_ci_dict, asset_sysid)
    except (NameError, TypeError) as e:
        logging.error("CMDB error: %s, %s" % (table, e))


timestamp_end = int(time())
duration = timedelta(seconds = (timestamp_end - timestamp_start))
logging.info("Process completed in: %s" % duration)