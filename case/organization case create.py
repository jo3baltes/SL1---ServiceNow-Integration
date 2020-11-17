#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

# ----------------------------------------------------------------------------#
# non_device_case_create_update.py
#
# Copyright (C) 2020 Fidelus Technologies, LLC/Joe Baltes <jbaltes@fidelus.com>
# All rights reserved.
# ----------------------------------------------------------------------------#
# Executes from SL1 as an RBA to create ServiceNow cases and update
# the SL1 event console w/ case numbers, and update ServiceNow cases on 
# new SL1 event correlations
#
# RBA to align to non-device events (Org level, etc.)
# ----------------------------------------------------------------------------#


import fidelus.silo
import fidelus.servicenow
import time
from time import sleep
from random import randint


# ------------------------------------------------------------------------------
# misc. functions
# ------------------------------------------------------------------------------

def make_display_notes(notes):
    """Reformat the notes for SL notification log."""
    if isinstance(notes, list):
        for note in notes:
            note = '<br>'.join(notes)
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(note))
    elif isinstance(notes, str):
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(notes))


em7_host_url = "https://monitor.fidelus.com/em7/"
notes_list = []
event_id = EM7_VALUES["%e"]
xid = EM7_VALUES["%x"]  # entity ID creating this case
xtype = EM7_VALUES["%1"]
event_link = em7_host_url + "index.em7?exec=events&q_type=aid&q_arg=%s&q_sev=1&q_sort=0&q_oper=0" % event_id
start_data = fidelus.silo.get_org_event(event_id)

emessage = start_data["message"]
company = start_data["company"]
snow_company = start_data["billing_id"]
etype = start_data["etype"]
etype_yname = start_data["yname"]
case_category = "200"  # "System Malfunction or Alert" >> on London now an INT
case_assignment = "Fidelus TAC"  # default for all RBAs
existing_case_number = start_data["ext_ticket_ref"]
existing_case_link = start_data["force_ticket_uri"]
existing_case_sysid = start_data["case_sys_id"]
severity = start_data["severity"]
comment = ""
snow_descr = "%s" % emessage

notes_list.append("Event ID: %s" % event_id)
notes_list.append("Entity ID: %s" % xid)
notes_list.append("Entity Type: %s" % xtype)
notes_list.append("Using Event Link: %s" % event_link)
notes_list.append("ServiceNow Descr: %s" % snow_descr)
notes_list.append("Queried for initial RBA data")
notes_list.append("RBA Data: %s" % str(start_data))
notes_list.append("Company: %s" % company)
notes_list.append("SL1 Event Type: %s" % etype)

# change assignment group as needed if company is MSHS Network
if company == "Mount Sinai - Network":
    case_assignment = "ca64f8911b39c0102c2ca7d4bd4bcbda"

# set case priority based on mapping SL Event Sev to SN Priority
# SL Event Severity
# 0	Healthy
# 1	Notice
# 2	Minor
# 3	Major
# 4	Critical

if severity == 0:
    # healthy
    case_priority = 4
elif severity == 1:
    # notice
    case_priority = 4
elif severity == 2:
    # SL minor
    case_priority = 4
elif severity == 3:
    # SL major
    case_priority = 3
elif severity == 4:
    # SL critical
    case_priority = 1


case_short_descr = company + ": " + emessage


notes_list.append("case Template: short descr: %s" % case_short_descr)
notes_list.append("case Template: descr: %s" % case_descr)
notes_list.append("case Template: category: %s" % case_category)
notes_list.append("case Template: assignment group: %s" % case_assignment)
notes_list.append("case Template: priority: %s" % case_priority)

# Get the ServiceNow CI, location and contact based on device ID
filter = "display_name=%s^company=%s" % ("No Device(s) Affected", snow_company)
response_asset = fidelus.servicenow.snow_asset_query(filter)

# Nasty try/except block here
try:
    ci_sys_id = str(response_asset["result"][0]["sys_id"])
    notes_list.append("ServiceNow CI: %s" % ci_sys_id)
except (TypeError, KeyError), e:
    ci_sys_id = "None"
    notes_list.append("Error: No CI found, error is: %s" % e)

try:
    location = str(response_asset["result"][0]["location"]["value"])
    notes_list.append("ServiceNow Location: %s" % location)
except (TypeError, KeyError), e:
    location = ""
    notes_list.append("Error: No Location found, error is: %s" % e)

try:
    contact = str(response_asset["result"][0]["location.contact"]["value"])
    notes_list.append("ServiceNow Contact: %s" % contact)
except (TypeError, KeyError), e:
    contact = ""
    notes_list.append("Error: No Contact found, error is: %s" % e)


# build the json payload to post into ServiceNow API
snow_case_dict = {
    'active': 'true',
    'sys_class_name': 'case',
    'category': case_category,
    'contact_type': 'ScienceLogic',
    'correlation_id': '',
    'state': '1',  # decimal value for New case state
    'assignment_group': case_assignment,
    'asset': ci_sys_id,
    'contact': contact,
    'location': location,
    'account': snow_company,
    'description': unicode(snow_descr, errors = "replace"),
    'short_description': unicode(case_short_descr, errors = "replace"),
    'u_task_record_type': 'Case',
    'priority': case_priority,
    'u_sl_event_policy_id': etype,
    'u_sciencelogic_event_cleared': 'false',
    'u_sciencelogic_event': 'https://monitor.fidelus.com/em7/index.em7?exec=event_print_ajax&aid=%s' % event_id,
    }

notes_list.append("Using ServiceNow case dictionary:")
notes_list.append(str(snow_case_dict))

case = fidelus.servicenow.create_case(snow_case_dict)

if case["result"]:
    notes_list.append("ServiceNow API response: \n")
    notes_list.append(str(case["result"]))
    case_sys_id = str(case["result"]["sys_id"])
    case_number = str(case["result"]["number"])
    case_link = fidelus.servicenow.urls + "nav_to.do?uri=sn_customerservice_case.do?sys_id=%s" % case_sys_id
    notes_list.append("case created: %s" % case_number)
    notes_list.append("case sys_id: %s" % case_sys_id)
    notes_list.append("case URI: %s" % case_link)
    case_hist_dict["case_number"] = case_number
    case_hist_dict["case_uri"] = case_link
else:
    notes_list.append("An error occurred")
    notes_list.append(str(case))

fidelus.silo.update_ext_ref_and_uri(case_number, case_link, event_id, None)
notes_list.append("Acknowledging event as system user")
EM7_RESULT = make_display_notes(notes_list)