#!/usr/local/bin/python2.7

# module imports
import sps_dbs
from requests.auth import HTTPBasicAuth
import requests
import json
import suds
from suds.client import Client

requests.packages.urllib3.disable_warnings()


class ServiceNowObj:
    """
        object for all ServiceNow interactions
    """
    
    def __init__(self):
        # mandatory / base variables regardless ServiceNow connection type
        self.user = "app.ctc"
        self.passwd = "Ctc$oap33"
        self.host = "spscom.service-now.com"
        self.port = 443
        self.url_base = "https://" + self.host + "/"
    
    def _soap_connect(self):
        # ServiceNow SOAP/XML connection
        self.incident_wsdl = "incident.do?WSDL"
        self.incident_url = "nav_to.do?uri=incident.do?sys_id="
        _wsdl = self.url_base + self.incident_wsdl
        self._sn_soap_client = Client(_wsdl, username=self.user, password=self.passwd)
    
    def _rest_connect(self):
        # REST / JSON API connection
        # Authentication for REST connection
        self.auth = HTTPBasicAuth(self.user, self.passwd)
        self.headers = { "accept": "application/json;charset=utf-8",
                    "Content-Type": "application/json",}
        self._ci_table = "u_cmdb_ci_systems"
        self._srv_commit_table = "service_commitment"
        self._user_table = "sys_user"
    
    def _add_ci_guid(self, _ci_guid):
        # make sure that the ServiceNow object know's the CI guid
        self.ci_guid = _ci_guid
    
    
    # -- ServiceNow REST API functions begin ---------------------------------------------#
    
    def _get_company_data(self):
        # query ServiceNow for company and location guid based on CI guid
        _fields = "company.sys_id,location.sys_id"
        _query = "sys_id=%s" % self.ci_guid
        _rest_urls = self.url_base + "api/now/table/" + self._ci_table + "?sysparm_action=getRecords&sysparm_fields=" + _fields + "&sysparm_query=" + _query
        r = requests.get(url=_rest_urls, auth=self.auth, verify=False, headers=self.headers)
        _content = r.json()
        try:
            for item in _content['result']:
                self.company_guid = str(item["company.sys_id"])
                self.location_guid = str(item["location.sys_id"])
        except KeyError, e:
            self.company_guid = ""
            self.location_guid = ""
    
    def _get_service_line(self):
        # query ServiceNow for the CI's service line guid
        _fields = "sys_id,name,u_service_line_guid"
        _query = "sys_id=%s" % self.ci_guid
        _rest_urls = self.url_base + "api/now/table/" + self._ci_table + "?sysparm_action=getRecords&sysparm_fields=" + _fields + "&sysparm_query=" + _query
        r = requests.get(url=_rest_urls, auth=self.auth, verify=False, headers=self.headers)
        _content = r.json()
        try:
            for item in _content['result']:
                self.service_line_guid = str(item["u_service_line_guid"])
        except KeyError, e:
                self.service_line_guid = ""
    
    def _get_service_commitments(self):
        # query ServiceNow for service commitments based on service line guid
        _fields = "sys_id,name"
        _query = "u_service_line_guid=%s" % self.service_line_guid
        _rest_urls = self.url_base + "api/now/table/" + self._srv_commit_table  + "?sysparm_action=getRecords&sysparm_fields=" + _fields + "&sysparm_query=" + _query
        r = requests.get(url=_rest_urls, auth=self.auth, verify=False, headers=self.headers)
        _content = r.json()
        try:
            for item in _content["result"]:
                # only use one service commitment, in this order
                # 'break' is the only solution I could arrive at
                if "Level 1 Service Desk & Case Mgmt. (iCON Platform Only)" in item["name"]:
                    self.service_commitment = item["sys_id"]
                    break
                elif "Level 1" in item["name"]:
                    self.service_commitment = item["sys_id"]
                    break
                elif "Alarm Response" in item["name"]:
                    self.service_commitment = item["sys_id"]
                    break
                else:
                    self.service_commitment = ""
        except KeyError, e:
            self.service_commitment = ""
    
    def _get_site_contact(self, _filter_str):
        # query ServiceNow for site contacts based on location guid if set
        if len(self.location_guid) > 0:
            _fields = "sys_id,user_name,location"
            _query = "user_nameLIKE%s^location=%s" % (_filter_str, self.location_guid)
            _rest_urls = self.url_base + "api/now/table/" + self._user_table + "?sysparm_action=getRecords&sysparm_fields=" + _fields + "&sysparm_query=" + _query
            r = requests.get(url=_rest_urls, auth=self.auth, verify=False, headers=self.headers)
            _content = r.json()
            try:
                _site_contact_list = _content["result"]
                self.site_contact = str(_site_contact_list[0]["sys_id"])
            except KeyError, e:
                self.site_contact = "None Available"
    
    def _get_category(self):
        # query ServiceNow for incident/device category based on CI guid
        # category either stored in CI details, or default to Avaya / Voice
        _fields = "sys_id,u_category,u_subcategory,"
        _query = "sys_id=%s" % self.ci_guid
        _rest_urls = self.url_base + "api/now/table/" + self._ci_table + "?sysparm_action=getRecords&sysparm_fields=" + _fields + "&sysparm_query=" + _query
        r = requests.get(url=_rest_urls, auth=self.auth, verify=False, headers=self.headers)
        _content = r.json()
        for item in _content['result']:
            try:
                self.category = str(item["u_category"])
            except KeyError, e:
                self.category = "Avaya"
            try:
                self.sub_category = str(item["u_subcategory"])
            except KeyError, e:
                self.sub_category = "Voice"








# testing stuff here
_ci_guid = "457d8a1c6f960280aa25b50d5d3ee417"

# bogus CI to test errors
_ci_guid = "1324124123123123123sdfsdfsdf123123123"



tester = ServiceNowObj()
tester._rest_connect() # init REST connection
tester._add_ci_guid(_ci_guid) # add the ServiceNow CI guid
tester._get_company_data() # get Company / Location for CI
tester._get_service_line() # get service line
tester._get_service_commitments() # get service commitments for the CI
tester._get_site_contact("Monitoring Contact") # have to pass the filter for contact name here
tester._get_category()





# make the EM7 db connection
dbMySQL = MySQLdb.connect(host = "localhost", port = 7706, user = "root",
    passwd = "em7admin", db = "master_biz")
cursorMySQL = dbMySQL.cursor(MySQLdb.cursors.DictCursor)




# -- EM7 database functions ---------------------------------------------#

import sps_dbs


class EM7obj:
    """
        object for all EM7 interactions
    """
    
    def __init__(self):
        # mandatory / base variables regardless EM7 connection type
        pass
    
    def insertFromDict(table, dict):
        """Take dictionary object dict and produce sql for
        inserting it into the named table"""
        sql = 'INSERT INTO ' + table
        sql += ' ('
        sql += ', '.join(dict)
        sql += ') VALUES ('
        sql += ', '.join(map(dictValuePad, dict))
        sql += ');'
        return sql
    
    def updateFromDict(table, dict):
        # TODO abstract this, take table "key" as an input
        """Take dictionary object dict and produce sql for
        inserting it into the named table"""
        sql = "UPDATE " + table + " SET "
        for k,v in dict.items():
            sql += "%s = '%s', "
        sql += " date_sn_updated = now()"
        sql += " where aid = \'" + str(dict['id']) + "\';"
        return sql
    
    def dictValuePad(key):
        return '%(' + str(key) + ')s'
    
    # -- EM7 database lookup functions ---------------------------------------------#
    def getEventDetail(self, _event_id):
        # from an input event id, get the device info for that active event
        _dev_sql = """select mea.id, mea.Xid, mea.Xname, mea.roa_id, mea.emessage, mea.eseverity,
                mea.date_active, mea.tid, mbla.id
                from master_events.events_active mea
                inner join master_biz.legend_asset mbla on mea.Xid = mbla.did
                where mea.id = %s """ % _event_id
        
        sps_dbs.cursorMySQL.execute(_dev_sql)
        self._event_dev_info = sps_dbs.cursorMySQL.fetchall()
    
    def _get_em7_crmid(self, _org_id):
        # get the company name and crm ID for the input org ID, return dict
        _sql = """select company, crm_id from master_biz.organizations where roa_id = %s """ % (_org_id)
        sps_dbs.cursorMySQL.execute(_sql)
        _company_detail = sps_dbs.cursorMySQL.fetchall()
        _company_detail = _company_detail[0]
        self._company_detail
    
    # -- EM7 Device / Asset / Org "Notes" query functions ---------------------------------------------#
    def _get_EM7notes_value(self, _type, _filter, _xid):
        # based on input type, filter string and XID value, query EM7 Notes for data
        # used for ServiceNow data linkage to ServiceNow records
            # _filter will be one of Location, CI, Assignment Group (literal strings)
            # CI - can be queried for CI based on Device ID or Org ID (set w/ xtype value as below)
            # Assignment Group - can be queried for CI based on Device ID or Org ID (set w/ xtype value as below)
        # Xtype 0 is an Org ID
        # Xtype 1 is a Device ID
        # Xtype 2 is a Asset ID
        
        if _type == "org":
            _xtype = 0
        if _type == "device":
            _xtype = 1
        if _type == "asset":
            _xtype = 2

        _sql = """select notes from master_biz.notes where xtype = %s and Xid = %s
            and notes like '%%ServiceNow %s%%' """ % (_xtype, _xid, _filter)

        sps_dbs.cursorMySQL.execute(_sql)
        _sn_linkage_data = sps_dbs.cursorMySQL.fetchall()

        # get just data to return
        if len(_sn_linkage_data) > 0:
            _sn_data = _sn_linkage_data[0]["notes"]
            _sn_data_str = _sn_data.split("=")[1]
            # remove lead/trailing spaces if they are present
            if " " in _sn_data_str:
                _sn_data_str = _sn_data_str.strip()
            return _sn_data_str
        else:
            return None



def get_custom_attrib(_dev_id, _filter):
    # based on input device id and filter string, query EM7 db for custom attributes
    _sql = """select ent_id, %s from master_custom.ent_device_custom
                where ent_id = %s""" % (_filter, _dev_id)
    cursorMySQL.execute(_sql)
    _data = cursorMySQL.fetchone()
    if _data is None:
        return None
    else:
        for k, v in _data.items():
            if k == _filter:
                if len(v) > 3:
                    return v
                else:
                    return None
