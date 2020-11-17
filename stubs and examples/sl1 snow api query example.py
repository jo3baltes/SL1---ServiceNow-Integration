def getCIs(snow_record_offset):
    """
        Get the ServiceNow CIs for an input company
    """
    # set the fields to query
    # use dot walking to get lookup field values ex: company.name
    snow_fields = "sys_id,company,name,mac_address,display_value,u_sciencelogic_correlation,sys_domain"

    # build the query string
    # query = "opened_atBETWEENjavascript:gs.dateGenerate('%s','00:00:00')@javascript:gs.dateGenerate('%s','00:00:00')" % (_start_dt_str, _end_dt_str)
    snow_query = ""

    # build the url
    url = urls + "api/now/table/%s?sysparm_action=getRecords&sysparm_offset=%s&sysparm_fields=%s&sysparm_query=%s" % (snow_network_adapters_table, snow_record_offset, snow_fields, snow_query)

    # send the request
    r = requests.get(url=url, auth=auth, verify=False, headers=headers)
    _content = r.json()
    return _content



def getLocations(snow_record_offset):
    """
        Get the ServiceNow locations for an input company
    """
    # set the fields to query
    # use dot walking to get lookup field values ex: company.name
    snow_fields = "sys_id,company.name,name,display_value,sys_domain"

    # build the query string
    # query = "opened_atBETWEENjavascript:gs.dateGenerate('%s','00:00:00')@javascript:gs.dateGenerate('%s','00:00:00')" % (_start_dt_str, _end_dt_str)
    snow_query = ""

    # build the url
    url = urls + "api/now/table/%s?sysparm_action=getRecords&sysparm_offset=%s&sysparm_fields=%s&sysparm_query=%s" % (snow_location_table, snow_record_offset, snow_fields, snow_query)

    # send the request
    r = requests.get(url=url, auth=auth, verify=False, headers=headers)
    _content = r.json()
    return _content


snow_location_table = "cmn_location"


# get CIs with initial record offest of 0
foo = getLocations('0')

print "/------------------------------------------------------------------------/"
print "CI records from %s" % snow_location_table
for i in foo["result"]:
    print i
    print '\n'

# check for more and page through
if len(foo["result"]) >= 10000:
    print "/------------------------------------------------------------------------/"
    print "CI records from %s" % snow_location_table
    foo2 = getCIs(10000)
    for i in foo2["result"]: print i
