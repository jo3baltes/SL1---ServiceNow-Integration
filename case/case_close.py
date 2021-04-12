#!/bin/python2.7
# -*- coding: utf-8 -*-

# Snippet to set Case state to closed. 

import fidelus.silo
import fidelus.servicenow
from datetime import datetime



now = str(datetime.now()).split(".")[0]
comments = "Testing, cancelling"
snow_case_dict = {'work_notes': comments,
                  'u_sciencelogic_event_cleared': 'true',
                  'state': 3,
                  'u_cause_code': 'other',
                  'resolution_code': 'Cancelled',
                  'close_notes': comments,
                  'resolved_by': 'cb2d39704ffc37001b59a9d18110c7ea',
                  'resolved_at': now
                  }

sn_case_sysid = "c227a13a1b562c50a00443b3cd4bcb9f"
fidelus.servicenow.update_case(snow_case_dict, sn_case_sysid)




