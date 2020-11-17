#!/bin/python2.7
# -*- coding: utf-8 -*-


from fidelus_libs.itsm.service_now_client import ServiceNowClientConnector



user = "EM7 Service Account"
passwd = "nzPHSMrkMUQcb6QGrCJY"
url = "https://fidelus.service-now.com"
port = 443


# init the conenction, and make connection
snc = ServiceNowClientConnector(url, user, passwd, port)
snc = ServiceNowClientConnector()
resp = snc.session()


