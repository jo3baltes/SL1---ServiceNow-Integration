#!/usr/local/bin/python2.7
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------#
# service_now_cmdb_sync.rba_London.py
#
# Copyright (C) 2019 Fidelus Technologies, LLC/Joe Baltes <jbaltes@fidelus.com>
# All rights reserved.
#
#-----------------------------------------------------------------------------#


__version__ = "1.1"

from silo_common.snippets.misc import generate_alert
from silo_common.database import silo_cursor
from silo_common.database import local_db
from silo_common.database import central_db
from silo_common import database
from datetime import datetime
import requests
from requests.auth import HTTPBasicAuth
# import urllib
import json


#-----------------------------------------------------------------------------#
# SL1 DB, API and misc. functions
#-----------------------------------------------------------------------------#
def get_did_details(did):
    """ function to get SL1 device and asset details from the DB """
    sql = """select mdev.id, mdev.device, mdev.ip, mdev.create_date, mdev.class_type,
        fslc.class, fslc.descript, fslc.snow_prod_model, fslc.sys_id product_sys_id,
        fslc.cmdb_table, mbo.crm_id, mbo.billing_id, mbla.model, mbla.serial, mbac.hostname
        from master_dev.legend_device mdev
        inner join master_biz.legend_asset mbla on mdev.id = mbla.did
        inner join master_biz.organizations mbo on mdev.roa_id = mbo.roa_id
        inner join master_biz.asset_configuration mbac on mbla.id = mbac.iid
        inner join fidelus.snow_london_cmdb fslc on mdev.class_type = fslc.class_type
        where mdev.id = %s""" % did
    dbc.execute(sql)
    results = dbc.fetchall()
    return results

# def check_navbar(did):
# TODO: use this to add navbar links from all device into SN London
#     """ function to query SL1 for navbar entry for device. This may need to be updated, and provides the stored
#         sys_id for the CI """
#     sql = """select mdte.tab_id, mdt.tab_url
#                     from master.definitions_tabs_to_entities
#                     mdte inner join master.definitions_tabs mdt on mdte.tab_id = mdt.tab_id
#                     where mdte.entity_id = %s and mdt.tab_url like '%%ervice-now.com%%'  """ % did
#     dbc.execute(sql)
#     results = dbc.fetchall()
#     return results

def make_display_notes(notes):
    if isinstance(notes, list):
        for note in notes:
            note = '<br>'.join(notes)
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(note))
    elif isinstance(notes, str):
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(notes))


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

if device is not None:
    device_dict["device_id"] = device[0][0]
    device_dict["device_name"] = device[0][1]
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
    device_dict["hostname"] = device[0][14]

company = device_dict["company"]
note_list.append("Using Company: %s" % company)
note_list.append("Creating device_dict and populating")

note_list.append("EM7 device details:")
note_list.append(str(device_dict))

note_list.append("Searching ServiceNow Company for CI")
note_list.append("Searching ServiceNow table: %s" % device_dict["cmdb_table"])


# company is passed input as a sys_id, in this version we send the CMDB table also
_filter = "u_sciencelogic_id=%s" % device_dict["device_id"]
snow_table = device_dict["cmdb_table"]
response_ci_did = snow_ci_query(company, _filter, snow_table)

note_list.append("ServiceNow Response:")
note_list.append(json.dumps(response_ci_did, indent=4, sort_keys=True))

if response_ci_did is not None:
    if response_ci_did["result"]:
        note_list.append("Found CI by EM7 Device ID, updating")
        note_list.append("Mapping EM7 Device ID: %s to ServiceNow CI sys_id: %s" % (did, str(response_ci_did["result"][0]["sys_id"])))
        ci_sys_id = manage_ci(device_dict, str(response_ci_did["result"][0]["sys_id"]), snow_table)
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
            response_ci_serial = snow_ci_query(company, _filter, snow_table)
            if response_ci_serial and response_ci_serial["result"]:
                note_list.append("Found CI by device Serial Number, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_serial["result"][0]["sys_id"], snow_table)
    # search CI based on IP address
    note_list.append("Searching for CI by IP address")
    if search == True:
        if device_dict["ip"] is not None and len(device_dict["ip"]) > 0:
            _filter = "ip_address=%s" % device_dict["ip"]
            response_ci_ip = snow_ci_query(company, _filter, snow_table)
            if response_ci_ip and response_ci_ip["result"]:
                note_list.append("Found CI by device IP Address, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_ip["result"][0]["sys_id"], snow_table)
    # search CI based on fqdn
    note_list.append("Searching for CI by FQDN")
    if search == True:
        if device_dict["hostname"] is not None and len(device_dict["hostname"]) > 0:
            _filter = "fqdn=%s" % device_dict["hostname"]
            response_ci_fqdn = snow_ci_query(company, _filter, snow_table)
            if response_ci_fqdn and response_ci_fqdn["result"]:
                note_list.append("Found CI by device FQDN, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_fqdn["result"][0]["sys_id"], snow_table)
    # search CI based on hostname
    note_list.append("Searching for CI by hostname")
    if search == True:
        if device_dict["hostname"] is not None and len(device_dict["hostname"]) > 0:
            _filter = "fqdn=%s" % device_dict["hostname"]
            response_ci_hostname = snow_ci_query(company, _filter, snow_table)
            if response_ci_hostname and response_ci_hostname["result"]:
                note_list.append("Found CI by device hostname, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_hostname["result"][0]["sys_id"], snow_table)
    # search based on name only
    note_list.append("Searching for CI by device name")
    if search == True:
        if device_dict["device_name"] is not None and len(device_dict["device_name"]) > 0:
            _filter = "name=%s" % device_dict["device_name"]
            # query EM7 for number of these device names in the Org
            response_ci_name = snow_ci_query(company, _filter, snow_table)
            if response_ci_name and response_ci_name["result"]:
                note_list.append("Found CI by device name, updating")
                search = False
                ci_sys_id = manage_ci(device_dict, response_ci_name["result"][0]["sys_id"], snow_table)


if ci_sys_id is None:
    # NO CI found, create a new one
    note_list.append("No match candidates for CI, inserting new CI")
    ci_sys_id = manage_ci(device_dict, None, snow_table)



note_list.append("CMDB management completed for sys_id: %s" % ci_sys_id)
EM7_RESULT = make_display_notes(note_list)
dbc.close()


