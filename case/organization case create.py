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
# active_events = None
# create_new_case = True
# update_case_notes = False
# correlate_only = False
# case_sys_id = None
# case_hist_dict = {}
notes_list = []
event_id = EM7_VALUES["%e"]
xid = EM7_VALUES["%x"]  # entity ID creating this case
xtype = EM7_VALUES["%1"]


# _filter = "u_sciencelogic_id=%s" % did
start_data = fidelus.silo.get_org_event(event_id)

if len(start_data) == 0:
    start_data = fidelus.silo.get_org_event(event_id)
    device = ""
    did = ""
    ip = ""
else:
    device_name = start_data["device"]
    ip = start_data["device_ip"]
    root_did = start_data["dcm_root_did"]

emessage = start_data["message"]
company = start_data["company"]
snow_company = start_data["billing_id"]
etype = start_data["etype"]
etype_yname = start_data["yname"]
case_category = "200"  # "System Malfunction or Alert" >> on London now an INT
case_assignment = "ca64f8911b39c0102c2ca7d4bd4bcbda"  # MSHS Network Engineers
existing_case_number = start_data["ext_ticket_ref"]
existing_case_link = start_data["force_ticket_uri"]
existing_case_sysid = start_data["case_sys_id"]
severity = start_data["severity"]
comment = ""

interface_name = ""
case_template = fidelus.silo.get_case_template(etype)