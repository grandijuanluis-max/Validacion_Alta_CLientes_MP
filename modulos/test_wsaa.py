import sys
sys.path.append('/Users/juanluisgrandi/AI/MP')
import modulos.api_afip as api
import requests

tra_xml = api._generar_tra()
cms_b64 = api._firmar_tra(tra_xml)
soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:wsaa="http://wsaa.view.sua.dvadac.desas.afip.gov">
   <soapenv:Header/>
   <soapenv:Body>
      <wsaa:loginCms>
         <wsaa:in0>{cms_b64}</wsaa:in0>
      </wsaa:loginCms>
   </soapenv:Body>
</soapenv:Envelope>"""
headers = {'Content-Type': 'text/xml;charset=UTF-8', 'SOAPAction': ''}
resp = requests.post(api.WSAA_URL, data=soap_request, headers=headers)
print(resp.status_code)
print(resp.text)
