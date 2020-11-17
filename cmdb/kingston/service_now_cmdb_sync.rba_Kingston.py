#!/usr/local/bin/python2.7
# -*- coding: utf-8 -*-

###########################################################################
# service_now_cmdb_sync.rba_Kingston.py
#
# Copyright (C) 2018 Fidelus Technologies, LLC/Joe Baltes <jbaltes@fidelus.com>
# All rights reserved.
#
###########################################################################
#
# Executes from EM7 as an RBA, triggered by SNOW CMDB Trigger event
#
###########################################################################
# History:
#
#  02.26.2018 Joe Baltes <jbaltes@fidelus.com>
#   - Initial Version (v1.0)
#  01.24.2019 Joe Baltes <jbaltes@fidelus.com>
#   - Bug Fix Version (v1.1) - added company.sys_id to existing CI search
#                            - increased logging details note_list
###########################################################################

__version__ = "1.0"

from silo_common.snippets.misc import generate_alert
from silo_common.database import silo_cursor
from silo_common.database import local_db
from silo_common.database import central_db
from silo_common import database
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
import urllib
import json



# ------------------------------------------------------------------------------
# EM7 DB, API and misc. functions
# ------------------------------------------------------------------------------
def get_did_details(did):
    """ function to get EM7 device and asset details from the DB """
    sql = """select mdev.id, mdev.iid, mdev.device, mdev.ip, mdev.hostname, mdev.class_type, mbo.company, mbo.crm_id,
        mdev.roa_id, mdev.create_date, mddc.class, mddc.descript, mbla.make, mbla.model, mbla.serial, mbac.hostname fqdn,
        mbac.os, mbac.fw_ver, fscm.descript 'class descript', fscm.snow_class, fscm.snow_mfg
        from master_dev.legend_device mdev
        left join master_biz.legend_asset mbla on mdev.id = mbla.did
        left join master_biz.asset_configuration mbac on mbla.id = mbac.iid
        left join master_biz.organizations mbo on mdev.roa_id = mbo.roa_id
        left join master.definitions_dev_classes mddc on mdev.class_type = mddc.class_type
        left join fidelus.snow_class_map fscm on mdev.class_type = fscm.class_type
        where mdev.id = %s""" % did
    dbc.execute(sql)
    results = dbc.fetchall()
    return results

def check_navbar(did):
    """ function to query EM7 for navbar entry for device. This may need to be updated, and provides the stored
        sys_id for the CI """
    sql = """select mdte.tab_id, mdt.tab_url
                    from master.definitions_tabs_to_entities
                    mdte inner join master.definitions_tabs mdt on mdte.tab_id = mdt.tab_id
                    where mdte.entity_id = %s and mdt.tab_url like '%%ervice-now.com%%'  """ % did
    dbc.execute(sql)
    results = dbc.fetchall()
    return results

def make_display_notes(notes):
    if isinstance(notes, list):
        for note in notes:
            note = '<br>'.join(notes)
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(note))
    elif isinstance(notes, str):
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(notes))

# ------------------------------------------------------------------------------
# ServiceNow API functions
# ------------------------------------------------------------------------------
snow_user = "EM7 Service Account"
snow_passwd = "only4support"
snow_host = "fidelus.service-now.com"
snow_port = 443
snow_urls = "https://" + snow_host + "/"
snow_table = "cmdb_ci"

auth = HTTPBasicAuth(snow_user, snow_passwd)
headers = { "accept": "application/json;charset=utf-8",
            "Content-Type": "application/json",}


def snow_ci_query(company, _filter):
    """ generic function to query ServiceNow API for an input filter """
    snow_table = "cmdb_ci"
    fields = "sys_id,name,company.name,company.sys_id"
    # query = "companyIS%s^%s" % (company, _filter)
    company = urllib.quote_plus(company)
    company_sysid = device_dict["crm_id"]
    query = "company.sys_id=%s^%s" % (company_sysid, _filter)
    url = snow_urls + "api/now/v1/table/" + snow_table + "?sysparm_limit=1&sysparm_fields=" + fields + "&sysparm_query=" + query
    note_list.append("SNOW CI query: %s" % url)
    r = requests.get(url=url, auth = auth, verify = False, headers = headers)
    _content = r.json()
    try:
        if _content["result"]:
            return _content
    except:
        note_list.append("No CI found")

def snow_ci_update(json_dict, ci):
    """ generic function to update ServiceNow API for an input CI data structure """
    url = snow_urls + "api/now/v1/table/" + snow_table + "/%s" % ci
    r = requests.patch(url=url, auth = auth, verify = False, headers = headers, data = json_dict)
    _content = r.json()
    
    try:
        if _content["result"]:
            return _content
    except:
        pass

def manage_ci(device_dict, ci):
    """ function to either update or create a ServiceNow CI. If a CI value is passed, "update" mode is used """
    ci_temp = {}
    ci_temp["short_description"] = device_dict["dev_class"] + " " + device_dict["model"]
    ci_temp["u_sciencelogic_update"] = str(datetime.now())
    ci_temp["u_sciencelogic_region"] = "Region 2"
    ci_temp["u_sciencelogic_status"] = "1"
    ci_temp["discovery_source"] = "ScienceLogic"
    ci_temp["install_status"] = "1"
    ci_temp["operational_status"] = "1"
    ci_temp["u_active_ci"] = "true"
    ci_temp["u_monitoring_active"] = "true"
    ci_temp["u_support_level"] = "Fully Supported"
    for k,v in device_dict.items():
        if k == "device_id":
            ci_temp["u_sciencelogic_id"] = str(v)
            ci_temp["u_sciencelogic_correlation"] = "LAB1+DEV+%s" % str(v)
            ci_temp["u_sciencelogic_url"] = "https://portal.fidelus.com/em7/index.em7?exec=device_summary&did=%s" % str(v)
        elif k == "asset_id":
            ci_temp["asset"] = str(v)
        elif k == "device_name":
            ci_temp["name"] = str(v)
        elif k == "ip":
            ci_temp["ip_address"] = str(v)
        elif k == "hostname":
            ci_temp["fqdn"] = str(v)
        elif k == "company":
            ci_temp["company"] = str(v)
        elif k == "create_date":
            ci_temp["first_discovered"] = str(v)
        elif k == "model":
            ci_temp["model_id"] = str(v)
        elif k == "serial":
            ci_temp["serial_number"] = str(v)
        elif k == "fqdn":
            ci_temp["fqdn"] = str(v)
        elif k == "snow_class":
            ci_temp["sys_class_name"] = str(v)
        elif k == "snow_mfg":
            ci_temp["manufacturer"] = str(v)
    
    if ci is not None:
        # update the known CI
        note_list.append("Updating the existing CI with this json:")
        ci_temp["sys_id"] = str(ci)
        # convert dict to json
        json_data = json.dumps(ci_temp)
        note_list.append(json.dumps(ci_temp, indent=4, sort_keys=True))
        # update ServiceNow CMDB - ALWAYS USE PATCH!
        url = snow_urls + "api/now/v1/table/" + snow_table + "/%s" % ci
        r = requests.patch(url=url, auth = auth, verify = False, headers = headers, data = json_data)
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
        r = requests.post(url=url, auth = auth, verify = False, headers = headers, data = json_data)
        _content = r.json()
        note_list.append("ServiceNow response:")
        note_list.append(json.dumps(_content, indent=4, sort_keys=True))
    ci_sys_id = str(_content["result"]["sys_id"])
    return ci_sys_id


# ------------------------------------------------------------------------------
# main runtime
# ------------------------------------------------------------------------------
EM7_RESULT = ""

did = EM7_VALUES["%x"]

note_list = []

# connect to EM7 DB
dbc = local_db()

# prepare a dict to hold the device and asset data for the CI
device_dict = {}

device = get_did_details(did)
note_list.append("Got details for device: %s" % did)

company = str(device[0][6])
note_list.append("Using Company: %s" % company)
note_list.append("Creating device_dict and populating")


if device is not None:
    device_dict["device_id"] = device[0][0]
    device_dict["asset_id"] = device[0][1]
    device_dict["device_name"] = device[0][2]
    device_dict["ip"] = device[0][3]
    device_dict["hostname"] = device[0][4]
    device_dict["class_type"] = device[0][5]
    device_dict["company"] = device[0][7] # changed 01/25 to reference company.sys_id
    device_dict["crm_id"] = device[0][7]
    device_dict["org_id"] = device[0][8]
    device_dict["create_date"] = device[0][9]
    device_dict["dev_class"] = device[0][10]
    device_dict["descript"] = device[0][11]
    device_dict["make"] = device[0][12]
    device_dict["model"] = device[0][13]
    device_dict["serial"] = device[0][14]
    device_dict["fqdn"] = device[0][15]
    device_dict["os"] = device[0][16]
    device_dict["fw_ver"] = device[0][17]
    device_dict["snow_class"] = device[0][19]
    device_dict["snow_mfg"] = device[0][20]

note_list.append("EM7 device details:")
note_list.append(str(device_dict))

# check EM7 for an existing CI
# this isn't really conclusive, since many CIs were linked previously, and in some cases to wrong company
# still good info to have for later
navbar = check_navbar(did)
note_list.append("Determining if navigation link to ServiceNow exists")

if len(navbar) == 0:
    # device link to CI not stored
    # CI may still exist
    navbar_mode = "create"
    note_list.append("No Device Properties Navigation link to ServiceNow")
    note_list.append("Navbar will be created")
else:
    navbar_mode = "existing"
    navbar_valid = "unknown"
    note_list.append("Found Device Properties Navigation link to ServiceNow")
    note_list.append("Navbar will be updated")


# connect to ServiceNow

# Find the CI if it exists for this company
note_list.append("Searching ServiceNow Company for CI")

# Device ID will always be known, no IF statement here
# search CI based on device ID
# this is first preference since it should be a definite
# company is passed input as a sys_id
_filter = "u_sciencelogic_id=%s" % device_dict["device_id"]
response_ci_did = snow_ci_query(company, _filter)

note_list.append("ServiceNow Response:")
note_list.append(json.dumps(response_ci_did, indent=4, sort_keys=True))

if response_ci_did is not None:
    if response_ci_did["result"]:
        note_list.append("Found CI by EM7 Device ID, updating")
        note_list.append("Mapping EM7 Device ID: %s to ServiceNow CI sys_id: %s" % (did, str(response_ci_did["result"][0]["sys_id"])))
        ci_sys_id = manage_ci(device_dict, str(response_ci_did["result"][0]["sys_id"]))
else:
    ci_sys_id = None
    search = True
    # No CI found for device ID, check all other options for an existing CI,
    # then if none found, default action to create a new CI
    note_list.append("No CI match by DeviceID, searching for update candidate")
    # search CI based on device serial number
    note_list.append("Searching for CI by serial number")
    if search == True:
        if device_dict["serial"] is not None and len(device_dict["serial"]) > 0:
            _filter = "serial_number=%s" % device_dict["serial"]
            response_ci_serial = snow_ci_query(company, _filter)
            if response_ci_serial and response_ci_serial["result"]:
                note_list.append("Found CI by device Serial Number, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_serial["result"][0]["sys_id"])
    # search CI based on IP address
    note_list.append("Searching for CI by IP address")
    if search == True:
        if device_dict["ip"] is not None and len(device_dict["ip"]) > 0:
            _filter = "ip_address=%s" % device_dict["ip"]
            response_ci_ip = snow_ci_query(company, _filter)
            if response_ci_ip and response_ci_ip["result"]:
                note_list.append("Found CI by device IP Address, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_ip["result"][0]["sys_id"])
    # search CI based on fqdn
    note_list.append("Searching for CI by FQDN")
    if search == True:
        if device_dict["fqdn"] is not None and len(device_dict["fqdn"]) > 0:
            _filter = "fqdn=%s" % device_dict["fqdn"]
            response_ci_fqdn = snow_ci_query(company, _filter)
            if response_ci_fqdn and response_ci_fqdn["result"]:
                note_list.append("Found CI by device FQDN, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_fqdn["result"][0]["sys_id"])
            
    # search CI based on hostname
    note_list.append("Searching for CI by hostname")
    if search == True:
        if device_dict["hostname"] is not None and len(device_dict["hostname"]) > 0:
            _filter = "fqdn=%s" % device_dict["hostname"]
            response_ci_hostname = snow_ci_query(company, _filter)
            if response_ci_hostname and response_ci_hostname["result"]:
                note_list.append("Found CI by device hostname, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_hostname["result"][0]["sys_id"])
    # search based on name only
    note_list.append("Searching for CI by device name")
    if search == True:
        if device_dict["device_name"] is not None and len(device_dict["device_name"]) > 0:
            _filter = "name=%s" % device_dict["device_name"]
            # query EM7 for number of these device names in the Org
            response_ci_name = snow_ci_query(company, _filter)
            if response_ci_name and response_ci_name["result"]:
                note_list.append("Found CI by device name, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_name["result"][0]["sys_id"])

if ci_sys_id is None:
    # NO CI found, create a new one
    note_list.append("No match candidates for CI, inserting new CI")
    ci_sys_id = manage_ci(device_dict, None)
        
note_list.append("CMDB management completed for sys_id: %s" % ci_sys_id)
EM7_RESULT = make_display_notes(note_list)
dbc.close()
