from silo_common.database import local_db
import fidelus.silo
import time
from time import sleep
from random import randint
import time
from time import sleep
from random import randint



def format_notifier(notes):
    """Reformat the notes for SL notification log."""
    if isinstance(notes, list):
        for note in notes:
            note = '<br>'.join(notes)
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(note)) 
    elif isinstance(notes, str):
        return "<p><font style='font: 9pt Helvetica;'>%s</font>" % (str(notes))

def rba_stage_add(**kwargs):
    """Add new data to the staging table for RBA correlation process."""
    dbc = local_db()
    sql = "insert into {tablename} ({columns}) values {values};" .format(
                tablename = "fidelus.rba_case_staging",
                columns = ', '.join(kwargs.keys()),
                values = tuple(kwargs.values())
            )
    dbc.execute(sql)



# init RBA variables
event_id = EM7_VALUES["%e"]
start_data = fidelus.silo.get_dev_event_data(event_id)
did = EM7_VALUES["%x"]
org = EM7_VALUES["%o"]
event_message = EM7_VALUES["%M"]
event_type = EM7_VALUES["%3"]
date_active = EM7_VALUES["%6"]
date_first = EM7_VALUES["%D"]
event_yid = EM7_VALUES["%y"]
case_create = None
dg_id = None  # will be determined in the code
dg_name = None  # will be determined in the code

# device_name = start_data["device"]
# emessage = start_data["message"]
# ip = start_data["device_ip"]
# root_did = start_data["dcm_root_did"]
# company = start_data["company"]
# snow_company = start_data["billing_id"]
# etype = start_data["etype"]
# etype_yname = start_data["yname"]
# event_yid = start_data["yid"]
# event_suppress_group = start_data["suppress_group"]
# case_category = "200"  # "System Malfunction or Alert" >> on London now an INT
# case_create = False
# existing_case_number = start_data["ext_ticket_ref"]
# existing_case_link = start_data["force_ticket_uri"]
# existing_case_sysid = start_data["case_sys_id"]
# if company == "Mount Sinai - Network":
#     case_assignment = "ca64f8911b39c0102c2ca7d4bd4bcbda"  # MSHS Network Engineers
# else:
#     case_assignment = "Fidelus TAC"
# 
# _filter = "u_sciencelogic_id=%s" % did


# get device group ID and name
dg = fidelus.silo.device_group_query(did)
for i in dg:
    if not "Backup" in i[1]:
        dg_id = dg[0][0]
        dg_name = dg[0][1]


output = []
output.append("Device Information:")
output.append("Device ID: %s" % did)
output.append("Device Group ID: %s" % dg_id)
output.append("Device Group: %s" % dg_name)
output.append("Org: %s" % org)
output.append("------------------------------------------")
output.append("Event Information:")
output.append("Event ID: %s" % event_id)
output.append("Event Message: %s" % event_message)
output.append("Event Policy: %s" % event_type)
output.append("Event Timestamp First: %s" % date_first)
output.append("Event Timestamp Active: %s" % date_active)
output.append("------------------------------------------")


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
    # add event to the outage staging table for later processing into cases
    event = {
              "eid": event_id,
              "org": org,
              "xid": did,
              "emessage": event_message,
              "etype": event_type,
              "dgid": dg_id,
              "dg_name": dg_name,
              "date_add": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
              "date_active": date_active,
              "date_first": date_first
          }
    
    rba_stage_add(**event)
    
    output.append("Added event to fidelus.rba_case_staging table")
    
    EM7_RESULT = fidelus.silo.format_notifier(output)