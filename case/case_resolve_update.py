#!/bin/python2.7
# -*- coding: utf-8 -*-

# RunBook Automation

# Trigger automation after Sl1 Event clears
# This RBA updates event clearing 
# 
# Expectation: 
# - RBA triggers on Event Clearing
# - update Case: add comment about event clearing
# - set "u_sciencelogic_event_cleared" to true

import fidelus.silo
import fidelus.servicenow 
from time import sleep


# ------------------------------------------------------------------------------
# misc. functions
# ------------------------------------------------------------------------------

def make_display_notes(notes):
    if isinstance(notes, list):
        for note in notes:
            note = '<br>'.join(notes)
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(note))
    elif isinstance(notes, str):
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(notes))

# get the event data
notes_list = []
event_id = EM7_VALUES["%e"]

sleep(5)
start_data = fidelus.silo.get_dev_event_data_clear(event_id) 

notes_list.append("Starting Data for this Event: %s" % str(start_data))

try:
    event_case_uri = start_data["force_ticket_uri"]
    event_case_number = start_data["ext_ticket_ref"]
    event_case_sys_id = event_case_uri.split("?")[2].replace("sys_id=", "")
    
    notes_list.append("Case: %s" % event_case_number)
    notes_list.append("URI: %s" % event_case_uri)
    notes_list.append("Sys_id: %s" % event_case_sys_id)
    
    comments = "The Monitoring Event that caused this case to Open has cleared."
    
    snow_case_dict = {"work_notes": comments, 
        'u_sciencelogic_event_cleared': 'true',
        'u_sciencelogic_event': 'https://monitor.fidelus.com/em7/index.em7?exec=event_print_ajax&aid=%s' % event_id,
        }
    
    notes_list.append("SN Case JSON: %s" % str(snow_case_dict))
    
    # update case 
    case = fidelus.servicenow.update_case(snow_case_dict, event_case_sys_id)
    notes_list.append("SN API Response: %s" % str(case))
    
    EM7_RESULT = make_display_notes(notes_list)
    
except AttributeError, e:
    notes_list.append("No Case was created, ending")

# remove event from the DG suppression state table 
fidelus.silo.dg_state_remove(event_id)
EM7_RESULT = make_display_notes(notes_list)