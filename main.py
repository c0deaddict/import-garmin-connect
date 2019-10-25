import re
import requests
from influxdb import InfluxDBClient
from requests.auth import HTTPBasicAuth
from subprocess import check_output
from urllib.parse import urlencode
from datetime import datetime, timedelta


def authenticate(username, password):
    connect_qs = {
        'clientId': 'GarminConnect',
        'connectLegalTerms': 'true',
        'consumeServiceTicket': 'false',
        'createAccountShown': 'true',
        'cssUrl': 'https://connect.garmin.com/gauth-custom-v1.2-min.css',
        'displayNameShown': 'false',
        'embedWidget': 'false',
        'gauthHost': 'https://sso.garmin.com/sso',
        'generateExtraServiceTicket': 'true',
        'generateNoServiceTicket': 'false',
        'generateTwoExtraServiceTickets': 'false',
        'globalOptInChecked': 'false',
        'globalOptInShown': 'true',
        'id': 'gauth-widget',
        'initialFocus': 'true',
        'locale': 'en_US',
        'locationPromptShown': 'true',
        'mobile': 'false',
        'openCreateAccount': 'false',
        'privacyStatementUrl': 'https://www.garmin.com/en-US/privacy/connect/',
        'redirectAfterAccountCreationUrl': 'https://connect.garmin.com/modern/',
        'redirectAfterAccountLoginUrl': 'https://connect.garmin.com/modern/',
        'rememberMeChecked': 'false',
        'rememberMeShown': 'true',
        'service': 'https://connect.garmin.com/modern/',
        'showConnectLegalAge': 'false',
        'showPassword': 'true',
        'showPrivacyPolicy': 'false',
        'showTermsOfUse': 'false',
        'source': 'https://connect.garmin.com/signin/',
        'useCustomHeader': 'false',
        'webhost': 'https://connect.garmin.com/modern/'
    }

    connect_url = "https://sso.garmin.com/sso/signin"

    print("Connecting ...")

    # We need a session to remember cookies between requests.
    session = requests.Session()
    response = session.post(
        connect_url + "?" + urlencode(connect_qs),
        headers={'Referer': connect_url},
        data={
            'username': email,
            'password': password,
            'embed': 'false'
        }
    )
    response.raise_for_status()
    ticket = re.search(r'\?ticket=(.*)"', response.text).group(1)

    print("Fetching session id ...")
    ticket_response = session.get(
        "https://connect.garmin.com/modern/?ticket=" + ticket,
        headers={'Referer': connect_url},
        allow_redirects=False,
    )

    return session


def find_display_name(session):
    response = session.get("https://connect.garmin.com/modern/")
    return re.search(r'displayName\\":\\\"([^"]*)\\"', response.text).group(1)


def fetch_data(session, display_name, date, base_url, date_param, extra_params={}):
    params = dict(**extra_params)
    params[date_param] = date.strftime('%Y-%m-%d')
    url = base_url + display_name + '?' + urlencode(params)
    return session.get(url).json()


def fetch_summary(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/usersummary-service/usersummary/daily/",
        date_param="calendarDate"
    )


def convert_summary(date, data, tags):
    """
    Summary is a object with a whole bunch of aggregations of the whole day.
    Just import it directly into InfluxDB.
    """
    yield {
        'measurement': 'summary',
        'tags': tags,
        'time': date.isoformat(),
        'fields': data
    }


def fetch_activities(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/activitylist-service/activities/fordailysummary/",
        date_param="calendarDate"
    )


def fetch_sleep(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailySleepData/",
        date_param="date",
        extra_params={'nonSleepBufferMinutes': 60}
    )


def fetch_steps(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailySummaryChart/",
        date_param="date"
    )


def convert_steps(date, data, tags):
    """
    Data is a list of:
    {'activityLevelConstant': True,
      'endGMT': '2019-10-25T18:00:00.0',
      'primaryActivityLevel': 'active',
      'startGMT': '2019-10-25T17:45:00.0',
      'steps': 316}
    """
    for rec in data:
        yield {
            'measurement': 'steps',
            'tags': dict(**tags, activity=rec['primaryActivityLevel']),
            'time': rec['endGMT'] + 'Z',
            'fields': {
                'steps': int(rec['steps'])
            }
        }


def fetch_movements(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailyMovement/",
        date_param="calendarDate"
    )


def fetch_heartrate(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailyHeartRate/",
        date_param="date"
    )


def fetch_weight(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/weight-service/weight/latest",
        date_param="date"
    )


def get_password(name):
    result = check_output(["pass", name])
    return result.decode('utf-8').split('\n')[0];


email = "jos@codeaddict.org"
password = get_password("garmin.com/connect")
session = authenticate(email, password)
display_name = find_display_name(session)

date = datetime.now()
fetch_steps(session, display_name, date)

num_days = 7
start_date = datetime.now() - timedelta(1)
for date in (start_date - timedelta(n) for n in range(num_days)):
    print(date)
