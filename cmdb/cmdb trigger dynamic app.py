#!/usr/local/bin/python2.7
# -*- coding: utf-8 -*-

###########################################################################
# cmdb trigger dynamic app.py
#
# Copyright (C) 2018 Fidelus Technologies, LLC/Joe Baltes <jbaltes@fidelus.com>
# All rights reserved.
#
###########################################################################
#
# Executes from EM7 as a dyanmic app. Triggers an alert into the device log
# which will trigger an RBA to interact with the SNOW CMDB.
#
###########################################################################
# History:
#
#  02.22.2018 Joe Baltes <jbaltes@fidelus.com>
#   - Initial Version (v1.0)
#
###########################################################################

__version__ = "1.0"

from silo_common.snippets.misc import generate_alert
from datetime import datetime


# self.internal_alerts.append((518,"ServiceNow CMDB Trigger"))

app_exec_time = str(datetime.now())

RESULT = [(0, app_exec_time)]

message = "ServiceNow CMDB Trigger"

Xid = str(this_device.did)
xtype = "1"
# generate_alert(message, Xid, xtype, yid, ytype, yname, value, threshold)
generate_alert(message, Xid, xtype)

snippet_argument = {'app_exec_time':''}
snippet_argument["app_exec_time"] = RESULT

result_handler.update(snippet_argument)
