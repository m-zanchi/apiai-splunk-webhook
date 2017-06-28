#!/usr/bin/env python

from __future__ import print_function
from future.standard_library import install_aliases
install_aliases()

from urllib.parse import urlparse, urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import json
import os
import time
import http.client
from xml.dom import minidom

from flask import Flask
from flask import request
from flask import make_response

# Flask app should start in global layout
app = Flask(__name__)


@app.route('/webhook', methods=['POST'])
def webhook():
    req = request.get_json(silent=True, force=True)

    print("Request:")
    print(json.dumps(req, indent=4))

    res = processRequest(req)

    res = json.dumps(res, indent=4)
    print("Processed Response:")
    print(res)
    r = make_response(res)
    r.headers['Content-Type'] = 'application/json'
    return r


def processRequest(req):
    if req.get("result").get("action") != "SLA_Performance":
        return {}
    conn = http.client.HTTPSConnection("dh2.aiam.accenture.com")
    yql_query = makeYqlQuery(req)
    print("Query:")
    print(yql_query)
    if yql_query is None:
        return {}
	payload = urlencode({'q': yql_query})
	# userAndPass = b64encode(b"username:password").decode("ascii")
	headers = {
    'content-type': "application/x-www-form-urlencoded",
    'authorization': "Basic bWF0dGVvX3Jlc3Q6cmVzdGFjY2Vzcw=="
    }

	conn.request("POST", "/rest-ealadev/services/search/jobs", payload, headers)
	res = conn.getresponse()
	data = res.read()
	sid = minidom.parseString(data).getElementsByTagName('sid')[0].childNodes[0].nodeValue
    
    print("Splunk Job Created SID:" + sid)
    
    t_end = time.time() + 60
    while time.time() < t_end:
        time.sleep(5)
        searchstatus = conn.request('GET',"/rest-ealadev/services/search/jobs/" + sid, headers=headers)[1]
        res = conn.getresponse()
        data2 = res.read()
        props = minidom.parseString(data2).getElementsByTagName('s:key')
        for element in props:
            if element.getAttribute('name') == "isDone":
                isdonestatus = element.childNodes[0].nodeValue
                break
        isdonestatus = isdonestatus.search(searchstatus).groups()[0]
        if (isdonestatus == '1'):
            break
    if (isdonestatus == '0'):
	    return {}
    print("Splunk Job Finished")
    conn.request("GET", "/rest-ealadev/services/search/jobs/"+sid+"/results?count=0&output_mode=xml", headers=headers)
    res = conn.getresponse()
    data3 = res.read()
    print("Splunk Search Results")
    print(data3)
    res = makeWebhookResult(data3)	
    return res


def makeYqlQuery(req):
    result = req.get("result")
    parameters = result.get("parameters")
    priority = parameters.get("priority")
    if priority is None:
        return None

    return 'search * index="mz_sla" | where Priority="' + priority +'" | table Priority, SLA_Performance'


def makeWebhookResult(data3):
    Priority = minidom.parseString(data3).getElementsByTagName('text')[0].nodeValue
    SLA_Performance = minidom.parseString(data3).getElementsByTagName('text')[1].nodeValue
    speech = "Latest SLA Performance for " + Priority + " is " + SLA_Performance
    
    print("Speech:")
    print(speech)
    return {
        "speech": speech,
        "displayText": speech,
        # "data": data,
        # "contextOut": [],
        "source": "apiai-weather-webhook-sample"
    }


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))

    print("Starting app on port %d" % port)
    app.run(debug=False, port=port, host='0.0.0.0')