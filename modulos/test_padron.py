import sys
sys.path.append('/Users/juanluisgrandi/AI/MP')
import modulos.api_afip as api
import requests

cuit = "30559927569"
token, sign = api._obtener_token_wsaa()
ns = api.PADRON_VERSION.lower()
cuit_limpio = cuit

soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:{ns}="http://{ns}.soap.ws.server.puc.sr/">
   <soapenv:Header/>
   <soapenv:Body>
      <{ns}:getPersona>
         <token>{token}</token>
         <sign>{sign}</sign>
         <cuitRepresentada>20234022041</cuitRepresentada>
         <idPersona>{cuit_limpio}</idPersona>
      </{ns}:getPersona>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {'Content-Type': 'text/xml;charset=UTF-8', 'SOAPAction': ''}
resp = requests.post(api.WS_PADRON_URL, data=soap_request, headers=headers)
print(resp.status_code)
print(resp.text)
