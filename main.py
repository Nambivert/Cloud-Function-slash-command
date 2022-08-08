import os
import json
from flask import Flask
from flask import request
from flask import jsonify
import functions_framework
from slack.signature import SignatureVerifier
import requests
from jinja2 import Environment, FileSystemLoader

app = Flask(__name__)

def trigger_pd_incident(request):
    # Triggers a PagerDuty incident without a previously generated incident key
    # Uses Events V2 API - documentation: https://v2.developer.pagerduty.com/docs/send-an-event-events-api-v2

    header = {
        "Content-Type": "application/json"
    }

    payload = { # Payload is built with the least amount of fields required to trigger an incident
        "routing_key": os.environ['ROUTING_KEY'], 
        "event_action": "trigger",
        "payload": {
            "summary": request.form['text'],
            "source": "Triggered using Slash command: firealarm",
            "severity": "critical"
        }
    }

    response = requests.post('https://events.pagerduty.com/v2/enqueue', 
                            data=json.dumps(payload),
                            headers=header)
	
    if response.json()["status"] == "success":
        print('Incident created with with dedup key (also known as incident / alert key) of ' + '"' + response.json()['dedup_key'] + '"') 
    else:
        print(response.text) # print error message if not successful

def send_message_to_slack_channel(request):
  user_name = request.form['user_name']
  channel_name = request.form['channel_name']
  text = request.form['text']

  message = ("Incident was triggered by"+ '\t' + str(user_name) + '\t' + "in the channel" + '\t' + str(channel_name))
  title = (f"{text}")
  slack_data = {
      "username": user_name,
      "icon_emoji": ":satellite:",
      "channel" : channel_name,
      "blocks": [
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": "Incident Description:" + '\t' + str(title) + '\n' + "Trigged by:" + '\t' + str(user_name) + '\n' + "Triggered in channel:" + '\t' + str(channel_name),
			}
		}
	]
  }
  
  headers = {'Content-Type': "application/json"}
  response = requests.post(os.environ['WEBHOOK_URL'], data=json.dumps(slack_data), headers=headers)
  if response.status_code != 200:
      print(response.status_code, response.text)

def format_message_slack(request):
  user_name = request.form['user_name']
  channel_name = request.form['channel_name']
  text = request.form['text']
  message = {
        'response_type': 'in_channel',
        'text': f'Incident Name: {text}. Username: {user_name}, Channel Name: {channel_name}',
    }
  return message

# [START functions_verify_webhook]
def verify_signature(request):
    request.get_data()  # Decodes received requests into request.data
    verifier = SignatureVerifier(os.environ['SLACK_SECRET'])
    if not verifier.is_valid_request(request.data, request.headers):
        raise ValueError('Invalid request/credentials.')
# [END functions_verify_webhook]

@app.route("/")
def home():
  return "It Works!"

@app.route("/firealarm", methods=["POST"])
def slack_firealarm():
  # Your code here
  if request.method != 'POST':
        return 'Only POST requests are accepted', 405

  verify_signature(request)
  trigger_pd_incident(request)
  res = format_message_slack(request)
  send_message_to_slack_channel(request)
  # Return an HTTP response
  return jsonify(res)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
