import requests


def kick_off_slack_notification(msg):
    """
    Find user in database.
    """
    url = "https://ecvai6hn0l.execute-api.us-east-2.amazonaws.com/production/new-order-handler"
    resp = requests.post(url, data={"msg": msg})
    if resp != 200:
        print(f"Warning: occurred on API Gateway submission: status_code {resp.status_code}")
