#!/bin/python2.7
"""Script to update SN CIs with Location data.

This script runs an update for customer CIs in ServiceNow, and sets the location
field value based on membership to an SL device group. Locations are set based
on the sys_id of the location, permitting variance between device group and 
location names. 
"""

import fidelus.servicenow
import fidelus.silo
from silo_common.database import local_db
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
import json
import unicodedata



def get_device_grp_devs(dgid):
    """Get the devices that belong to a device group."""
    sql = """SELECT did FROM master_dev.device_groups_to_devices
            where dgid = %s and did not in (select id from master_dev.legend_device 
            where roa_id = 1827)""" % dgid
    dbc = local_db()
    dbc.execute(sql)
    results = dbc.fetchall()
    return results

def get_org_devices(org):
    """Function to get the device ID list for an SL Org."""
    sql = """select id from master_dev.legend_device 
        where roa_id = %s and length(ip) > 1 """ % org
    dbc = local_db()
    dbc.execute(sql)
    results = dbc.fetchall()
    return results

# get device details
def get_did_details(did):
    """ function to get SL1 device and asset details from the DB """
    sql = """select mdev.id, mdev.device, mdev.ip, mdev.create_date, mdev.class_type,
        fslc.class, fslc.descript, fslc.snow_prod_model, fslc.sys_id product_sys_id,
        fslc.cmdb_table, mbo.crm_id, mbo.billing_id, mbla.model, mbla.serial, mbac.hostname,
        mc.servicenow_sysid
        from master_dev.legend_device mdev
        inner join master_biz.legend_asset mbla on mdev.id = mbla.did
        inner join master_biz.organizations mbo on mdev.roa_id = mbo.roa_id
        inner join master_biz.asset_configuration mbac on mbla.id = mbac.iid
        inner join fidelus.snow_london_cmdb fslc on mdev.class_type = fslc.class_type
        inner join master_custom.ent_device_custom mc on mdev.id = mc.ent_id
        where mdev.id = %s""" % did
    dbc = local_db()
    dbc.execute(sql)
    results = dbc.fetchall()
    return results


# get the CIs - by Org for Mt. Sinai. Set the SL org ID here
org_id = 1825
locations_list = []

with open("cmdb_locations_list") as file:
    # locations_list = [line.rstrip("\n") for line in open(file)]
    for line in file:
        line = line.rstrip("\n")
        # locations_list.append("(%s)" % line.strip("\n"))
        locations_list.append(tuple(line.split(",")))



note_list = []

#-----------------------------------------------------------------------------#
# ServiceNow API functions
#-----------------------------------------------------------------------------#
snow_user = "EM7 Service Account"
snow_passwd = "nzPHSMrkMUQcb6QGrCJY"
snow_host = "fidelus.service-now.com"
snow_port = 443
snow_urls = "https://" + snow_host + "/"
snow_table = "cmdb_ci"

auth = HTTPBasicAuth(snow_user, snow_passwd)
headers = { "accept": "application/json;charset=utf-8",
            "Content-Type": "application/json",}

session = requests.Session()


def snow_ci_query(company, _filter, table):
    """ generic function to query ServiceNow API for an input filter """
    snow_table = table
    fields = "sys_id,name,company.name,company.sys_id"
    # query = "companyIS%s^%s" % (company, _filter)
    # company = urllib.quote_plus(company) no longer using company name string, using sys_id
    company_sysid = company
    query = "company.sys_id=%s^%s" % (company_sysid, _filter)
    url = snow_urls + "api/now/v1/table/" + snow_table + "?sysparm_limit=1&sysparm_fields=" + fields + "&sysparm_query=" + query
    note_list.append("SNOW CI query: %s" % url)
    r = session.get(url=url, auth = auth, verify = False, headers = headers)
    _content = r.json()
    try:
        if _content["result"]:
            return _content
    except:
        note_list.append("No CI found")

def snow_ci_update(json_dict, ci):
    """ generic function to update ServiceNow API for an input CI data structure """
    url = snow_urls + "api/now/v1/table/" + snow_table + "/%s" % ci
    r = session.patch(url=url, auth = auth, verify = False, headers = headers, data = json_dict)
    _content = r.json()
    
    try:
        if _content["result"]:
            return _content
    except:
        pass



def manage_ci(device_dict, ci, table):
    """ function to either update or create a ServiceNow CI. If a CI value is passed, "update" mode is used """
    snow_table = table
    ci_temp = {}
    ci_temp["short_description"] = device_dict["dev_class"] + " " + device_dict["descript"]
    ci_temp["u_sciencelogic_update"] = str(datetime.now())
    ci_temp["discovery_source"] = "ScienceLogic"
    ci_temp["install_status"] = "1"
    ci_temp["u_active"] = "true"
    
    for k,v in device_dict.items():
        if k == "device_id":
            ci_temp["u_sciencelogic_id"] = str(v)
            ci_temp["u_sciencelogic_url"] = "https://portal.fidelus.com/em7/index.em7?exec=device_summary&did=%s" % str(v)
        elif k == "device_name":
            ci_temp["name"] = str(v)
        elif k == "ip":
            ci_temp["ip_address"] = str(v)
        elif k == "hostname":
            ci_temp["hostname"] = str(v)
        elif k == "company":
            ci_temp["u_account"] = str(v)
        elif k == "create_date":
            ci_temp["first_discovered"] = str(v)
        elif k == "serial":
            ci_temp["serial_number"] = str(v)
        elif k == "dev_class":
            ci_temp["manufacturer"] = str(v)
        elif k == "cmdb_table":
            ci_temp["sys_class_name"] = str(v)
        # elif k == "snow_product_model":
        #     ci_temp["model_id"] = str(v)
        elif k == "product_sys_id": # or descript???
            ci_temp["model_id"] = str(v)
        # elif k == "product_sys_id": # or descript???
        #     ci_temp["model_id"] = str(v)
        ci_temp["location"] = device_dict["location"]
    
    if ci is not None:
        # update the known CI
        note_list.append("Updating the existing CI with this json:")
        ci_temp["sys_id"] = str(ci)
        # convert dict to json
        json_data = json.dumps(ci_temp)
        note_list.append(json.dumps(ci_temp, indent=4, sort_keys=True))
        # update ServiceNow CMDB - ALWAYS USE PATCH!
        url = snow_urls + "api/now/v1/table/" + snow_table + "/%s" % ci
        r = session.patch(url=url, auth = auth, verify = False, headers = headers, data = json_data)
        _content = r.json()
        note_list.append("ServiceNow response:")
        note_list.append(json.dumps(_content, indent=4, sort_keys=True))
    else:
        # create the new CI
        note_list.append("Inserting new CI:")
        # convert dict to json
        json_data = json.dumps(ci_temp)
        note_list.append(json.dumps(ci_temp, indent=4, sort_keys=True))
        # insert into ServiceNow CMDB - HTTP POSTe
        url = snow_urls + "api/now/v1/table/" + snow_table
        r = session.post(url=url, auth = auth, verify = False, headers = headers, data = json_data)
        _content = r.json()
        note_list.append("ServiceNow response:")
        note_list.append(json.dumps(_content, indent=4, sort_keys=True))
    ci_sys_id = str(_content["result"]["sys_id"])
    return ci_sys_id

invalid_cache_list = []

for group in locations_list:
    print "-------------------------------------------------------------------"
    dgid = group[0]
    location_sysid = group[2]
    print "Device Group: %s" % group[1]
    print dgid, location_sysid
    print "-------------------------------------------------------------------"
    # get device group members
    dids = get_device_grp_devs(dgid)
    for dev in dids: 
        device = get_did_details(dev[0])
        print device
        if device is not None:
            device_dict = {}
            device_dict["device_id"] = device[0][0]
            device_dict["device_name"] = unicodedata.normalize("NFKD", device[0][1].decode("ascii", "ignore"))
            device_dict["ip"] = device[0][2]
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
            device_dict["serial"] = device[0][13]
            device_dict["hostname"] = unicodedata.normalize("NFKD", device[0][14].decode("ascii", "ignore"))
            device_dict["ci_sysid"] = device[0][15]
            device_dict["location"] = location_sysid
        
        # search for CI based on company and device id
        company = device_dict["company"]
        _filter = "u_sciencelogic_id=%s" % device_dict["device_id"]
        snow_table = device_dict["cmdb_table"]
        
        if device_dict["ci_sysid"]:
            # SL has sysid, no lookup required
            cache_ci_sysid = device_dict["ci_sysid"]
            print "updating CI for %s" % device_dict["device_name"]
            try:
                ci_sys_id = manage_ci(device_dict, cache_ci_sysid, snow_table)
            except (IndexError, KeyError), e:
                # sysid doesn't appear to exist, call this invalid cache
                item = "%s, %s: %s" % (str(device_dict["device_id"]), \
                    str(device_dict["device_name"]), e)
                print "invalid cached sysid for: %s" % item
                invalid_cache_list.append(item)
        # else:
        #     response_ci_did = snow_ci_query(company, _filter, snow_table)
        #     if response_ci_did is not None:
        #         print "Found CI, updating"
        #         if response_ci_did["result"]:
        #             ci_sys_id = manage_ci(device_dict, str(response_ci_did["result"][0]["sys_id"]), snow_table)
        #     else: 
        #         print "New CI, creating"
        #         ci_sys_id = manage_ci(device_dict, None, snow_table)
        
