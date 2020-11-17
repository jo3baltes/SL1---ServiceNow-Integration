#!/usr/bin/python2.7
# -*- coding: utf-8 -*-
"""Script for bulk, per-customer CMDB sync (create, update) operations.

Args:
    -o | -org : SL Organization ID to perform sync
    -a | -all : Forces re-sync for ALL devices (all customers)
    -d | -did : SL device ID to sync (singular)
    -g | -group : SL device group ID to sync, syncing all device group members
    -c | -created : Date, sync SL devices created on or after this date
    
"""

__version__ = "0.1"

import fidelus.silo
import fidelus.servicenow
from silo_common.database import local_db
from datetime import datetime
from time import time
import json
import getopt
import sys
import unicodedata
import logging
import urllib

def usage():
    """Usage information for this script."""
    print """
        Script to bulk sync SL1 devices to the CMDB
        
        Usage: ./cmdb_snyc.py {options}
        -o | -org : used to specify the SL Organization ID. 'All' argument: re-sync for ALL devices (all customers)
        -d | -did : SL device ID to sync (singular)
        -g | -group : SL device group ID to sync, syncing all device group members
        -c | -created : Date, sync SL devices created on or after this date
        -i | -instance : ServiceNow instance (PROD, DEV)
        """

def get_config_data(did, app_id):
    """For a device and application id, get the current data collected. This is going to be very
        ugly as we add new device and app types here."""
    dbc = local_db()
    
    if app_id == 1799:  # SilverPeak Orchestrator
        sql = """select 
                    max(case when object = 19752 then data end) hostname, 
                    max(case when object = 19755 then data end) ip, 
                    max(case when object = 19763 then data end) model, 
                    max(case when object = 19756 then data end) serial, 
                    max(case when object = 19753 then data end) version
                from dynamic_app_data_%s.dev_config_%s""" % (app_id, did)
    
    if app_id == 1793:  # SilverPeak EdgeConnect
        sql = """select 
                    max(case when object = 19696 then data end) hostname, 
                    max(case when object = 19698 then data end) ip, 
                    max(case when object = 19699 then data end) model, 
                    max(case when object = 19701 then data end) serial, 
                    max(case when object = 19711 then data end) version
                from dynamic_app_data_%s.dev_config_%s """ % (app_id, did)
    
    dbc.execute(sql)
    results = dbc.fetchall()
    return results



timestamp = int(time())
# logging.basicConfig(level=logging.INFO, filename="cmdb_sync_log.%s" % timestamp, filemode="w", format="%(asctime)s: %(name)s: %(levelname)s: %(message)s")
# logging.basicConfig(level=logging.INFO, filename="cmdb_sync_log.%s" % timestamp,\
#      filemode="w", format="%(asctime)s: %(name)s: %(levelname)s: %(message)s")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, filename="cmdb_sync.log", \
     filemode="a", format="%(asctime)s: %(name)s: %(levelname)s: %(message)s")


organization = None
did = None
device_group = None
created = None
ci_sys_id = None
note_list = []
cache_update_only = True

# options, remainder = getopt.getopt(sys.argv[1:], "o:", ["input=", ])

options, remainder = getopt.getopt(sys.argv[1:], "i:o:d:g:c:", ["input=",
                                                         "instance",
                                                         "org",
                                                         "did",
                                                         "group",
                                                         "created",])

for opt, arg in options:
    if opt in ("-o", "-org"):
        organization = arg
    if opt in ("-d", "-did"):
        did = arg
    if opt in ("-g", "-group"):
        device_group = arg
    if opt in ("-c", "-created"):
        created = arg
    if opt in ("-i", "-insance"):
        sn_instance = arg
        sn_instance = "prod"

if any([organization, did, device_group, created]):
    pass
else:
    print "No options selected, nothing to do."
    usage()
    sys.exit()


logging.info("Start CMDB Sync with these options:")
logging.info("\tServiceNow Instance: %s" % "prod")
logging.info("\tOrganization ID: %s" % organization)
logging.info("\tDevice ID: %s" % did)
logging.info("\tDevice Group ID: %s" % device_group)
logging.info("\tDevices Created After: %s" % created)


# base SQL where clause. Add to it as needed
sql_where = ["""(mdev.ip like '%%.%%' or mdev.class_type in 
                    # need to add where clauses for the component devices that we care about here
                    # Silver Peak devices...
                    	(select class_type from master.definitions_dev_classes 
                    		where class like 'Silver Peak' and descript not like 'Group'))"""]

# if organization is "all," set the roa_id to a not list to eliminate Orgs that we *don't* want
if organization:
    if organization == "all":
        sql_where.append("roa_id not in (0, 1829, 1823, 1826, 1827)")
    else:
        sql_where.append("roa_id = %s" % organization)


if did: sql_where.append("id = %s" % did)

# if device_group: sql_where.append("dg_id = %s" % did)  # this may need it's own query

if created: sql_where.append("create_date >= '%s'" % created)

sql = " and ".join(sql_where)

logging.debug("SQL where clause: %s" % sql)

# query SL for the physical devices for sync to CMDB
devices = fidelus.silo.get_physical_devs_cmdb(sql)

logging.info("Devices for Org: %s retrieved" % organization)


for dev in devices:
    did = dev[0]
    logging.info("Device ID: %s, fetching details" % did)
    
    # check if physical or component device - IP address or not?
    device = fidelus.silo.get_device_details(did)
    data = None
    if device[0][5] == "Silver Peak":
        # these are all components and not supported as normal
        # determine if EdgeConnect or Orchestrator
        # get the "configuration" app ID, and it's data, that will provide CMDB data needed
        if device[0][7] == "Orchestrator":
            config_app_id = 1799
            data = get_config_data(did, config_app_id)
        elif device[0][7] == "EdgeConnect":
            config_app_id = 1793
            data = get_config_data(did, config_app_id)
    
    if device is not None:
        device_dict = {}
        device_dict["device_id"] = device[0][0]
        device_dict["device_name"] = unicodedata.normalize("NFKD", device[0][1].decode("ascii", "ignore"))
        device_dict["ip"] = device[0][2] if device[0][2] else data[0][1]
        device_dict["create_date"] = device[0][3]
        device_dict["class_type"] = device[0][4]
        device_dict["dev_class"] = device[0][5]
        device_dict["descript"] = device[0][6]
        device_dict["snow_prod_model"] = device[0][7]
        device_dict["product_sys_id"] = device[0][8]
        device_dict["cmdb_table"] = device[0][9]
        device_dict["company"] = device[0][10]
        device_dict["company"] = device[0][11]
        device_dict["model"] = device[0][12]
        device_dict["serial"] = device[0][13] if device[0][13] else data[0][3] if data else ""
        device_dict["hostname"] = unicodedata.normalize("NFKD", device[0][14].decode("ascii", "ignore"))
        device_dict["ci_sys_id"] = device[0][15]
        
        snow_table = device_dict["cmdb_table"]
        
        logging.info("Device details:")
        for k, v in device_dict.items():
            logging.info("\t%s %s", k, v)
        
        company = device_dict["company"]
        
        if device_dict["ci_sys_id"] and device_dict["ci_sys_id"] != 'None':
            logging.info("SL1 Cached sysid found, using sysid: %s" % device_dict["ci_sys_id"])
            logging.info(" ---> Sending update to ServiceNow")
            
            ci_sys_id = device_dict["ci_sys_id"]
            try:
                update_cached_ci = fidelus.servicenow.manage_ci(device_dict, ci_sys_id, snow_table)
                logging.info(" <--- ServiceNow Response")
                logging.info(json.dumps(update_cached_ci, indent=4, sort_keys=True))
            except (TypeError, KeyError), e:
                logging.error("CMDB Update error - confirm valid product mapping in SL1")
                logging.error("Raising SL Event")
                event = {"xname": device_dict["device_name"], 
                         "xtype": 1,  # 1 for device 
                         "xid": device_dict["device_id"],
                         "roa_id": organization,
                         "esource": 6,
                         "emessage": "CMDB Sync Error on update for device: %s %s %s" % (device_dict["device_name"], \
                            update_cached_ci, str(json.dumps(update_cached_ci, indent=4, sort_keys=True))),
                         "etype": 6299,
                         "estate": 0,
                         "suppress_group": 0,
                         "eseverity": 2,
                         }
                fidelus.silo.create_event(event)
            
        elif device_dict["ci_sys_id"] == None or len(device_dict["ci_sys_id"]) == 0:
            logging.info("SL1 Cached sysid NOT FOUND, query to SNOW required")
            
            _filter = "u_sciencelogic_id=%s^" % device_dict["device_id"]
            
            # Serial #s with some Cisco stuff are NOT unique, removing this
            _filter = _filter + "ip_address=%s^" % device_dict["ip"]
            
            # special characters in name are messing up the search, removing for now
            # TODO: work with George on this
            # _filter = _filter + "name=%s" % device_dict["device_name"]
            
            # _filter = urllib.quote_plus(filter)
            logging.info("Searching SN table %s for existing CI" % snow_table)
            logging.info("Search Parameter: %s" % _filter)
            
            search_ci_result = fidelus.servicenow.snow_cmdb_query(company, _filter, snow_table)
            
            if not search_ci_result:
                logging.info("No match candidates for CI, inserting new CI")
                try:
                    insert_ci_response = fidelus.servicenow.manage_ci(device_dict, None, snow_table)
                    
                    logging.info(" <--- ServiceNow Response")
                    logging.info(json.dumps(insert_ci_response, indent=4, sort_keys=True))
                    
                    logging.info("Mapping EM7 Device ID: %s to ServiceNow CI sys_id: %s" % (did, insert_ci_response))
                    logging.info("Adding sys_id to cache")
                    fidelus.silo.device_sysid_cache(did, insert_ci_response, "add")
                except (TypeError, KeyError), e:
                    logging.error("CMDB Update error - confirm valid product mapping in SL1")
                    logging.error("Raising SL Event")
                    event = {"xname": device_dict["device_name"], 
                             "xtype": 1,  # 1 for device 
                             "xid": device_dict["device_id"],
                             "roa_id": organization,
                             "esource": 6,
                         "emessage": "CMDB Sync Error on update for device: %s %s %s" % (device_dict["device_name"], \
                            update_cached_ci, str(json.dumps(update_cached_ci, indent=4, sort_keys=True))),
                             "etype": 6299,
                             "estate": 0,
                             "suppress_group": 0,
                             "eseverity": 2,
                             }
                    fidelus.silo.create_event(event)
                
            elif search_ci_result:
                existing_ci_sysid = str(search_ci_result["result"][0]["sys_id"])
                logging.info("Match was found for existing CI %s, updating and caching" % existing_ci_sysid)
                
                logging.info(" <--- ServiceNow Response")
                logging.info(json.dumps(search_ci_result, indent=4, sort_keys=True))
                logging.info("Sending update to the CI")
                
                try:
                    update_ci_response = fidelus.servicenow.manage_ci(device_dict, existing_ci_sysid, snow_table)
                    
                    logging.info(" <--- ServiceNow Response")
                    logging.info(json.dumps(update_ci_response, indent=4, sort_keys=True))
                    
                    logging.info("Mapping EM7 Device ID: %s to ServiceNow CI sys_id: %s" % (did, update_ci_response))
                    logging.info("Adding sys_id to SL1 cache")
                    fidelus.silo.device_sysid_cache(did, update_ci_response, "add")
                except (TypeError, KeyError), e:
                    logging.error("CMDB Insert error - confirm valid product mapping in SL1")
                    logging.error("Raising SL Event")
                    event = {"xname": device_dict["device_name"], 
                             "xtype": 1,  # 1 for device 
                             "xid": device_dict["device_id"],
                             "roa_id": organization,
                             "esource": 6,
                             "emessage": "CMDB Sync Error on insert for device: %s %s" % (device_dict["device_name"], \
                                update_cached_ci),
                             "etype": 6299,
                             "estate": 0,
                             "suppress_group": 0,
                             "eseverity": 2,
                             }
                    fidelus.silo.create_event(event)
