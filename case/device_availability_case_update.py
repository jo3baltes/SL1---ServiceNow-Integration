#!/bin/python2.7
# -*- coding: utf-8 -*-

# RunBook Automation

# Trigger automation after ServiceNow Case is created
# This RBA updates cases with availability failure validation result
# 
# Expectation: 
# - RBA triggers
# - result of device availability validation is brought in via EM7_LAST_RESULT variable
# - ServiceNow Case sys_id is looked up for this device event
# - Case is updated with the validation script output

import json
import requests
from requests.auth import HTTPBasicAuth
requests.packages.urllib3.disable_warnings()
from silo_common.database import local_db

# ------------------------------------------------------------------------------
# SL1 functions
# ------------------------------------------------------------------------------

def get_active_event_case(event_id):
    # get active events for this device where a case exists
    # this list of events will be correlated together to prevent additional cases
    dbc = local_db()
    sql = """select ext_ticket_ref, force_ticket_uri from master_events.events_active 
                where id = %s and (ext_ticket_ref like 'CS%%') limit 1 """ % event_id
    dbc.execute(sql)
    results = dbc.fetchone()
    if results:
        result_dict = {}
        result_dict["case_number"] = results[0]
        result_dict["case_uri"] = results[1]
        return result_dict
    else:
        return None


# ------------------------------------------------------------------------------
# ServiceNow API functions
# ------------------------------------------------------------------------------

def update_case(snow_case_dict, case_sys_id):
    """ for input case dict and sys_id, update the case """
    url = snow_urls + "api/now/v1/table/sn_customerservice_case/%s" % case_sys_id
    json_data = json.dumps(snow_case_dict)
    
    r = requests.patch(url=url, auth = auth, verify = False, headers = headers, data = json_data)
    _content = r.json()
    return _content

snow_user = "EM7 Service Account"
snow_passwd = "nzPHSMrkMUQcb6QGrCJY"
snow_host = "fidelus.service-now.com"
snow_port = 443
snow_urls = "https://" + snow_host + "/"


auth = HTTPBasicAuth(snow_user, snow_passwd)
headers = { "accept": "application/json;charset=utf-8",
            "Content-Type": "application/json",}


# prepare the text for ServiceNow update
work_notes = EM7_LAST_RESULT.result[0]
comments = EM7_LAST_RESULT.result[1]

event_id = EM7_VALUES["%e"]

# get the case # for this event
event_case = get_active_event_case(event_id)
event_case_uri = event_case["case_uri"]
event_case_number = event_case["case_number"]
event_case_sys_id = event_case_uri.split("?")[2].replace("sys_id=", "")


snow_case_dict = {"comments": comments, 
                   "work_notes": work_notes,}

# update case with the validation result
case = update_case(snow_case_dict, event_case_sys_id)