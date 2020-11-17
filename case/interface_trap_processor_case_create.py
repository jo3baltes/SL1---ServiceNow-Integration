import fidelus.silo
import fidelus.servicenow
import time
from time import sleep
from random import randint

# ------------------------------------------------------------------------------
# misc. functions
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


event_id = EM7_VALUES["%e"]
did = EM7_VALUES["%x"]

start_data = fidelus.silo.get_dev_event_data(event_id)

device_name = start_data["device"]
emessage = start_data["message"]
ip = start_data["device_ip"]
root_did = start_data["dcm_root_did"]
company = start_data["company"]
snow_company = start_data["billing_id"]
etype = start_data["etype"]
etype_yname = start_data["yname"]
event_yid = start_data["yid"]
event_suppress_group = start_data["suppress_group"]
case_category = "200"  # "System Malfunction or Alert" >> on London now an INT
case_create = False
existing_case_number = start_data["ext_ticket_ref"]
existing_case_link = start_data["force_ticket_uri"]
existing_case_sysid = start_data["case_sys_id"]
if company == "Mount Sinai - Network":
    case_assignment = "ca64f8911b39c0102c2ca7d4bd4bcbda"  # MSHS Network Engineers
else:
    case_assignment = "Fidelus TAC"

_filter = "u_sciencelogic_id=%s" % did

comment = ""
notes_list = []


# check interface for full list of tags
if_tags = fidelus.silo.interface_tags_collect(event_yid)
if event_yid == 0 or len(if_tags) == 0:
    # if yid == 0 then event isn't aligned to a device interface - this 
    # interface hasn't been enabled for monitoring
    # also with no tags, it's an non-actionable interface
    # ok to ack and clear immediately
    fidelus.silo.send_event_clear(event_id)
elif len(if_tags) > 0:
    # there's at least one tag set, inspect for action required
    # tags are:
    # 5019	Backup
    # 78	FTAC
    # 77	Internet
    # 11	MPLS
    # 5737	MSHS-Report-WAN
    # 1068	P1
    # 2542	Report-Internet
    # 2538	Report-WAN
    # 4	    test
    # 46	Verizon
    # 1069	WAN
    # 10	Windstream
    tag_action_list = [78, 77, 11, 1068, 5019, 1069]

for tag in if_tags:
    case_priority = 3  # assume case sev 3 until we find otherwise
    if tag[1] in tag_action_list:
        # interface is actionable
        if tag[1] == 1068:
            case_priority = 1
            case_create = True
        if tag[1] == 5019:
            case_priority = 3
            case_create = True
        elif tag[1] == 78:
            case_priority = 3
            case_create = True
    else:
        # interface tags are not requiring case creations, clear event
        case_create = False
        fidelus.silo.send_event_clear(event_id)

if case_create == True:
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
        contact = str(response_ci_did["result"][0]["location.u_nms_contact"]["value"])
        notes_list.append("ServiceNow Contact: %s" % contact)
    except (TypeError, KeyError), e:
        contact = ""
        notes_list.append("Error: No Contact found, error is: %s" % e)
    
    interface_name = start_data["yname"]
    interface_alias = fidelus.silo.get_if_alias(event_yid, interface_name)
    if not interface_alias: interface_alias = "None"
    
    case_short_descr = "DOWN - Interface - %s %s %s source: TRAP" % (device_name, ip, interface_name)
    
    case_descr = """
    Fidelus Managed Services has detected an interface state change for the following device interface:
    
    DEVICE = %s %s
    INTERFACE = %s is in "DOWN" state
    INTERFACE ALIAS = %s
    
    This event indicates one of the following conditions:
    	The interface status is "UP" but the operational status is "DOWN"
    	The interface cable is disconnected or has another fault
    	The hardware interface controller is an error state
    	There is an issue with the far end of the connection, if the connection is point to point
    
    Please note, this event may be informational only and may not require any immediate action. 
    
    The current impact to your environment is being investigated and additional information will be provided accordingly.
    """ % (ip, device_name, interface_name, interface_alias)
    
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
    else:
        notes_list.append("An error occurred")
        notes_list.append(str(case))
    
    fidelus.silo.update_ext_ref_and_uri(case_number, case_link, event_id)
    notes_list.append("Acknowledging event as system user")
    EM7_RESULT = make_display_notes(notes_list)
