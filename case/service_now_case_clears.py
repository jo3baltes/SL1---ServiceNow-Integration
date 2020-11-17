#!/bin/python2.7
# -*- coding: utf-8 -*-

# Cron script

# Trigger automation after Sl1 Event clears
# This script updates event clearing state for any open ServiceNow Cases
#
# Process used:
# - query ServiceNow API for cases in state:
# --- Created by SL1
# --- Cases not in Closed / Resolved / Cancelled State
# - get the Case number and Event ID
# - check SL1 Event state
# - if cleared from SL1, update the Case "event cleared" state to True


import fidelus.silo
import fidelus.servicenow
from datetime import datetime
from silo_common.database import local_db
from silo_common.database import silo_cursor
from silo_common import database



def sn_case_update(event_id):
    """For input Event ID, buid the dictionary to send to ServiceNow for
        the case update."""
    comments = "The Monitoring Event that caused this case to Open has cleared."
    snow_case_dict = {"work_notes": comments, 
        'u_sciencelogic_event_cleared': 'true',
        'u_sciencelogic_event': 'https://monitor.fidelus.com/em7/index.em7?exec=event_print_ajax&aid=%s' % event_id,
        }
    return snow_case_dict

def event_from_case(case):
    """For an input case number, get the event id(s) active."""
    dbc = local_db()
    sql = """select id from master_events.events_active where 
                ext_ticket_ref = '%s' """ % case
    dbc.execute(sql)
    results = dbc.fetchall()
    return results



now = datetime.now()

# query ServiceNow for active SL1 created cases
cases = fidelus.servicenow.query_cases_sl_state()

for case in cases["result"]:
    if "ext_ticket_ref" in case["u_sciencelogic_event"]:
        # TODO: handle these different, there's no event id to use
        # get the event id for this case from SL1
        case_number = str(case["number"])
        sn_case_sysid = str(case["sys_id"])
        event = event_from_case(case_number)
        if len(event) == 0:
            print "Event Cleared, update Case"
            comments = "The Monitoring Event that caused this case to Open has cleared."
            snow_case_dict = {'work_notes': comments,
                              'u_sciencelogic_event_cleared': 'true'}
            fidelus.servicenow.update_case(snow_case_dict, sn_case_sysid)
    else:
        event_id = case["u_sciencelogic_event"].split("aid=")[1]
        number =  case["number"]
        sn_case_sysid = case["sys_id"]
        
        print "\n------------------------------------------------------------------"
        print "[%s]: Event ID: %s, Case: %s checking SL1 Event State" % (now, event_id, number)
        
        # confirm SL1 event state
        # query cleared events table and count result
        event_cleared = fidelus.silo.get_dev_event_data_clear(event_id)
        
        if len(event_cleared) == 0:
            # no record of cleared event, chaeck for active event
            print "No Cleared Event"
            active_event = fidelus.silo.confirm_event_active(event_id)
            if not active_event:
                print "No Cleared or Active Event, update the Case"
                snow_case_dict = sn_case_update(event_id)
                fidelus.servicenow.update_case(snow_case_dict, sn_case_sysid)
            elif active_event: print "Event ACTIVE"
        
        elif len(event_cleared) == 5:
            # the event is cleared, we can update ServiceNow
            print "Event Cleared, update Case"
            snow_case_dict = sn_case_update(event_id)
            fidelus.servicenow.update_case(snow_case_dict, sn_case_sysid)
