#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

# ----------------------------------------------------------------------------#
# case_create_update.RBA_London.py
#
# Copyright (C) 2019 Fidelus Technologies, LLC/Joe Baltes <jbaltes@fidelus.com>
# All rights reserved.
# ----------------------------------------------------------------------------#
# Executes from SL1 as an RBA to create ServiceNow cases and update
# the SL1 event console w/ case numbers, and update ServiceNow cases on 
# new SL1 event correlations
#
# Generic RBA, no corellations. This will be used for the LifeRing Case Create
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

# ------------------------------------------------------------------------------
# Globals
# ------------------------------------------------------------------------------


em7_host_url = "https://monitor.fidelus.com/em7/"
active_events = None
create_new_case = True
update_case_notes = False
correlate_only = False
case_sys_id = None
case_hist_dict = {}
notes_list = []
event_id = EM7_VALUES["%e"]
did = EM7_VALUES["%x"]  # Device ID creating this case
_filter = "u_sciencelogic_id=%s" % did
start_data = fidelus.silo.get_dev_event_data(event_id)
device_name = start_data["device"]
emessage = start_data["message"]
ip = start_data["device_ip"]
root_did = start_data["dcm_root_did"]
company = start_data["company"]
snow_company = start_data["billing_id"]
etype = start_data["etype"]
etype_yname = start_data["yname"]
case_category = "200"  # "System Malfunction or Alert" >> on London now an INT

if snow_company == "abfbc1c5134dbf009c615cb63244b0f4":
    case_assignment = "ca64f8911b39c0102c2ca7d4bd4bcbda"  # MSHS Network Engineers
else:
    case_assignment = "Fidelus TAC"

existing_case_number = start_data["ext_ticket_ref"]
existing_case_link = start_data["force_ticket_uri"]
existing_case_sysid = start_data["case_sys_id"]
ext_ticket_userid = fidelus.silo.external_ticket_user(event_id)
ext_ticket_username = fidelus.silo.user_from_id(ext_ticket_userid)
ci_sysid = start_data["ci_sysid"]
severity = start_data["severity"]
comment = ""


interface_name = ""
case_template = fidelus.silo.get_case_template(etype)

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


event_link = em7_host_url + "index.em7?exec=events&q_type=aid&q_arg=%s&q_sev=1&q_sort=0&q_oper=0" % event_id
snow_descr = "%s: %s" % (str(start_data["device"]), str(start_data["message"]))

notes_list.append("Event ID: %s" % event_id)
notes_list.append("Queried for initial RBA data")
notes_list.append("RBA Data: %s" % str(start_data))
notes_list.append("Using Event Link: %s" % event_link)
notes_list.append("ServiceNow Descr: %s" % snow_descr)
notes_list.append("Device ID: %s" % did)
notes_list.append("Company: %s" % company)
notes_list.append("EM7 Event Type: %s" % etype)
notes_list.append("SL1 Username triggering case: %s [%s]" % (ext_ticket_username, ext_ticket_userid))

# ------------------------------------------------------------------------------
# main runtime
# ------------------------------------------------------------------------------

# get the userid of the external ticket requester - used for event console ack 
# userid = fidelus.silo.userid_from_name(sl_username)



#  if the device id creating this case is a component, it will have no ip addr
#  reset "_fileter" to use the ci sys_id
if start_data["device_ip"]:
    pass
else:
    _filter = "sys_id=%s" % ci_sysid

# Get the ServiceNow CI, location and contact based on device ID
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


# some routines to filter out un-wanted cases
if "vlan" in start_data["message"].lower():
    if "threshold" or "bandwidth" in start_data["message"].lower():
        # don't continue with case creation, just log and stop
        # this is a vlan bandwidth event
        create_new_case = False
        update_case_notes = False
        correlate_only = False
        notes_list.append("This is a vlan interface bandwidth event, case creation and updates stopping")
        EM7_RESULT = make_display_notes(notes_list)
else:
    pass


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

if "Bandwidth" in emessage:
    device_active_cases = fidelus.servicenow.check_ci_cases_open(ci_sys_id, etype, "Bandwidth")
elif "Interface" in emessage:
    device_active_cases = fidelus.servicenow.check_ci_cases_open(ci_sys_id, etype, "Interface")
else:
    # non-Interface events
    # device_active_cases = fidelus.servicenow.check_ci_cases_open(ci_sys_id, etype, etype_yname) # This returns 10,000 cases, problem
    # device_active_cases = fidelus.servicenow.check_ci_cases_open(ci_sys_id, etype, "")
    device_active_cases = fidelus.servicenow.check_ci_cases_open(ci_sys_id, etype, None)

if "no correlation" in str(device_active_cases):
    create_new_case = True
    update_case_notes = False
    correlate_only = False
else:
    create_new_case = False
    update_case_notes = False
    correlate_only = True

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

if "DRF" in emessage:
    # check if this is a DRF related event. 
    # If so, check if there is an existing DRF case for this device. 
    # If so, correlate to the existing open case
    notes_list.append("This is a DRF event, checking for an open Case to correlate to.")
    device_active_cases = fidelus.servicenow.check_ci_cases_open(ci_sys_id, etype, "DRF")
    if "no correlation" in str(device_active_cases):
        create_new_case = True
        update_case_notes = False
        correlate_only = False
    else:
        create_new_case = False
        update_case_notes = False
        correlate_only = True


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
    
    snow_case_dict = {"work_notes": work_notes}
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
    # if existing_case_sysid is not None:
    #     dev_case_state = fidelus.servicenow.check_case_status(existing_case_sysid)
    # else:
    #     dev_case_state = 101010
    
    # if int(dev_case_state) in (3, 7, 10):
    #     create_new_case = True
    #
    #     comment = """The previous case for this Monitoring Issue Device/Event was Resolved but the Monitoring Detected Issue is NOT RESOLVED.
    #     FMS Engineers - investigate the Monitoring Event and ensure that the Monitoring Event is cleared prior to resolving this case.\n\n"""
    #
    
    if len(case_template) > 0:
        # we are overriding normal EM7 event messages in this case creation so there
        # are text manipulations we will need to accomplish they all will go here
        
        if case_template.has_key("short_descr"):
            if (case_template["short_descr"]) is not None and len(case_template["short_descr"]) > 1:
                case_short_descr = case_template["short_descr"]
                case_descr = case_template["descr"]
                
                # handle interface related case messaging if required
                if "nterface" in case_template["short_descr"]:
                    interface_name = start_data["yname"]
                    if len(start_data["label"]) > 0:
                        interface_alias = start_data["label"].split(',')[0]
                        interface_ifid = start_data["label"].split('if_id: ')[1]
                    else:
                        # use device id and interface name to get the interface alias
                        interface_alias = fidelus.silo.get_if_alias(did, interface_name)
                        interface_alias = interface_alias[0][0]
                        interface_ifid = ""
                    
                    notes_list.append("INTERFACE NAME: %s" % interface_name)
                    notes_list.append("INTERFACE ALIAS: %s" % interface_alias)
                    notes_list.append("INTERFACE IF_ID: %s" % interface_ifid)
                    
                    # urgency override for P1 intefaces check interface tag
                    interface_p1 = fidelus.silo.check_interface_p1(interface_ifid)
                    if len(interface_p1) > 0:
                        case_priority = 1
                    
                    case_short_descr = case_short_descr.replace("*interface_replace*", interface_name)
                    case_short_descr = case_short_descr.replace("*interface_alias*", interface_alias)
                    
                    case_descr = case_descr.replace("*interface_replace*", interface_name)
                    case_descr = case_descr.replace("*interface_alias*", interface_alias)
                
                if "device_replace" in case_short_descr:
                    # add the IP address per customer request
                    case_short_descr = case_short_descr + " IP: %s" % ip
                
                case_short_descr = case_short_descr.replace("*device_replace*", device_name)
                case_short_descr = case_short_descr.replace("*replace_device*", device_name)
                case_short_descr = case_short_descr.replace("*peer_ip_replace*", start_data["label"])
                
                case_descr = case_descr.replace("*device_replace*", device_name)
                case_descr = case_descr.replace("*replace_device*", device_name)
                
                case_descr = case_descr.replace("*event_replace*", start_data["message"])
                if interface_name: case_descr = case_descr.replace("*interface_replace*", interface_name)
                case_descr = case_descr.replace("*device_replace*", device_name)
                case_descr = case_descr.replace("*peer_ip_replace*", start_data["label"])
            
            else:
                # simple pass-through from SL1 event data into case
                case_short_descr = start_data["device"] + " IP: " + ip + " / " + start_data["message"]
                case_descr = "Fidelus Monitoring has detected the following Event information:\n %s" % case_short_descr
        
    else:
        # simple pass-through from SL1 event data into case
        case_short_descr = start_data["device"] + " IP: " + ip + " / " + start_data["message"]
        case_descr = "Fidelus Monitoring has detected the following Event information:\n %s" % case_short_descr
    
    notes_list.append("case Template: short descr: %s" % case_short_descr)
    notes_list.append("case Template: descr: %s" % case_descr)
    notes_list.append("case Template: category: %s" % case_category)
    notes_list.append("case Template: assignment group: %s" % case_assignment)
    notes_list.append("case Template: priority: %s" % case_priority)
    
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
        'account': str(start_data["billing_id"]),
        'description': comment + case_descr,
        'short_description': case_short_descr,
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
    
    fidelus.silo.update_ext_ref_and_uri(case_number, case_link, event_id, ext_ticket_userid)
    notes_list.append("Acknowledging event as system user")
    fidelus.silo.update_inc_case_history(event_id, **case_hist_dict)
    EM7_RESULT = make_display_notes(notes_list)
