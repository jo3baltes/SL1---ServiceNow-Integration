#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

# ----------------------------------------------------------------------------#
# ServiceNow Case Create 001.py
# ----------------------------------------------------------------------------#
# Executes from SL1 as an RBA to create ServiceNow cases and update
# the SL1 event console w/ case numbers
#
# Very simple case creation, correlation is active

# create case in "FTAC Monitoring" assignment group

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
active_events = None
create_new_case = True
update_case_notes = False
correlate_only = False
case_sys_id = None

notes_list = []
case_category = "200"  # "System Malfunction or Alert"
case_assignment = "FTAC Monitoring"
comment = ""

# SL1 built-in variables, don't need a DB query to retrieve
event_id = EM7_VALUES["%e"]
did = EM7_VALUES["%x"]


start_data = fidelus.silo.get_dev_event_data(event_id)

device_name = start_data["device"]
ip = start_data["device_ip"]
root_did = start_data["dcm_root_did"]
emessage = start_data["message"]
ci_sysid =  start_data["ci_sysid"]
company = start_data["company"]
snow_company = start_data["billing_id"]
etype = start_data["etype"]
etype_yname = start_data["yname"]
did = start_data["device_id"]
existing_case_number = start_data["ext_ticket_ref"]
existing_case_link = start_data["force_ticket_uri"]
existing_case_sysid = start_data["case_sys_id"]
# severity = start_data["severity"]  # hardcode sev 3 for P3 cases



# Get the ServiceNow CI, location and contact based on device ID
_filter = "u_sciencelogic_id=%s" % did
response_ci_did = fidelus.servicenow.snow_ci_query(snow_company, _filter)

# Nasty try/except block here
try:
    ci_sys_id = str(response_ci_did["result"][0]["asset.sys_id"])
    notes_list.append("ServiceNow CI: %s" % ci_sys_id)
except (TypeError, KeyError), e:
    ci_sys_id = "None"
    notes_list.append("Error: No CI found, error is: %s" % e)

try:
    location = str(response_ci_did["result"][0]["location"]["value"])
    notes_list.append("ServiceNow Location: %s" % location)
except (TypeError, KeyError), e:
    location = ""
    notes_list.append("Error: No Location found, error is: %s" % e)

try:
    contact = str(response_ci_did["result"][0]["location.contact"]["value"])
    notes_list.append("ServiceNow Contact: %s" % contact)
except (TypeError, KeyError), e:
    contact = ""
    notes_list.append("Error: No Contact found, error is: %s" % e)


# set case priority based on mapping SL Event Sev to SN Priority
# SL Event Severity
# 0	Healthy
# 1	Notice
# 2	Minor
# 3	Major
# 4	Critical

severity = 3
case_priority = 3

event_link = em7_host_url + "index.em7?exec=events&q_type=aid&q_arg=%s&q_sev=1&q_sort=0&q_oper=0" % event_id
snow_descr = "%s: %s" % (device_name, emessage)

notes_list.append("Event ID: %s" % event_id)
notes_list.append("Queried for initial RBA data")
notes_list.append("RBA Data: %s" % str(start_data))
notes_list.append("Using Event Link: %s" % event_link)
notes_list.append("ServiceNow Descr: %s" % snow_descr)
notes_list.append("Device ID: %s" % did)
notes_list.append("Company: %s" % company)
notes_list.append("EM7 Event Type: %s" % etype)



# ------------------------------------------------------------------------------
# case correlation logic
# ------------------------------------------------------------------------------

# Determine if there is an existing case for this device and event type in non-Closed state
# If there is, correlate to that case, and reset state to Pending
# Update the case with a note raising attention to the fact that the device issue is still occurring

# check for an open Case for this device and event policy based on the current event

# check SL for similar events
#     same etype
#     same device
#   if none, set new case eligible, check servicenow for related cases
#
# check ServiceNow for similar cases
#     same CI
#     same etype
#     state in non-closed value
#     u_record_type = case
#   if none, create new case
#   if one or more, check for parent case, create new case, link to parent

# avoid a race condition, make sure that there are no other RBA actions competing here
# check SL and if no events, wait a random amount of time from 10 - 30 seconds and re-test
# if there's no device id, set default options
if did:
    device_active_events = fidelus.silo.get_active_events_device(did, etype)
    if device_active_events is None:
        # possible that other RBA executions are happening, wait some time
        sleep(randint(10,30))
        # re-query for active events to correlate
        device_active_events = fidelus.silo.get_active_events_device(did)
    
    if device_active_events:
        # there are other active events for this device and event policy, correlate if cases are still open
        create_new_case = True
        update_case_notes = False
        correlate_only = False
else:
    create_new_case = True
    update_case_notes = False
    correlate_only = False

if "Failed Availability" in emessage:
    # check to see if critical ping event active on device then prevent case
    # creation, so no one complains about redundant cases
    
    crit_ping_dev = fidelus.silo.check_critical_ping(did)
    if crit_ping_dev is True:
        notes_list.append("This is Event will not create a case, since Critial Ping is enabled.")
        create_new_case = False
        update_case_notes = False
        correlate_only = True
        device_active_cases = fidelus.servicenow.check_ci_cases_open(ci_sys_id, 3292, None)
        EM7_RESULT = make_display_notes(notes_list)

if correlate_only is True:
    # There are active cases for this Device and Event
    # TODO do things
    
    # user most recently opened case
    case_update_number = device_active_cases[-1]["number"]
    case_update_sysid = device_active_cases[-1]["sys_id"]
    
    # update case to add a work note
    work_notes = """
    Monitoring has detected the following additional device event:
    %s """ % (start_data["message"])
    
    snow_case_dict = {"work_notes": work_notes,
                      "state": "18",
                      "priority": case_priority,
                      "u_sciencelogic_event": "https://monitor.fidelus.com/em7/index.em7?exec=event_print_ajax&aid=%s" % event_id,
                      "u_sciencelogic_event_cleared": "false",
                      }
    
    case = fidelus.servicenow.update_case(snow_case_dict, case_update_sysid)
    
    # update SL to include the case # and link
    case_update_link = fidelus.servicenow.urls + "nav_to.do?uri=sn_customerservice_case.do?sys_id=%s" % case_update_sysid
    fidelus.silo.update_ext_ref_and_uri(case_update_number, case_update_link, event_id, None)
    
    notes_list.append("This is Event will update an existing Case")
    notes_list.append("Open Case selected (newest): %s" % case_update_number)
    notes_list.append("Added work note to this case and updated SL1 Event Console, process completed.")
    EM7_RESULT = make_display_notes(notes_list)
    # we're all done here

if create_new_case is True:
    if ip:
        case_short_descr = device_name + " IP: " + ip + " / " + emessage
    else:
        case_short_descr = company + ": " + emessage
    case_descr = "Fidelus Monitoring has detected the following Event:\n %s" % case_short_descr
    
    notes_list.append("Case: short descr: %s" % case_short_descr)
    notes_list.append("Case: descr: %s" % case_descr)
    notes_list.append("Case: category: %s" % case_category)
    notes_list.append("Case: assignment group: %s" % case_assignment)
    notes_list.append("Case: priority: %s" % case_priority)
    
    # build the json payload to post into ServiceNow API
    snow_case_dict = {
        "active": "true",
        "sys_class_name": "case",
        "category": case_category,
        "contact_type": "ScienceLogic",
        "correlation_id": "",
        "state": "1",  # decimal value for New case state
        "assignment_group": case_assignment,
        "asset": ci_sys_id,
        "contact": contact,
        "location": location,
        "account": snow_company,
        "description": comment + case_descr,
        "short_description": case_short_descr,
        "u_task_record_type": "Case",
        "priority": case_priority,
        "u_sl_event_policy_id": etype,
        "u_sciencelogic_event_cleared": "false",
        "u_toggle_notifications": "internal",
        "u_sciencelogic_event": "https://monitor.fidelus.com/em7/index.em7?exec=event_print_ajax&aid=%s" % event_id,
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
    # case_hist_dict["case_number"] = case_number
    # case_hist_dict["case_uri"] = case_link
else:
    notes_list.append("An error occurred")
    notes_list.append(str(case))

fidelus.silo.update_ext_ref_and_uri(case_number, case_link, event_id, None)
notes_list.append("Acknowledging event as system user")
EM7_RESULT = make_display_notes(notes_list)
