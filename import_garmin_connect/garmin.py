import re
import requests
from urllib.parse import urlencode
from datetime import datetime
import logging


def authenticate(username, password):
    connect_qs = {
        "clientId": "GarminConnect",
        "connectLegalTerms": "true",
        "consumeServiceTicket": "false",
        "createAccountShown": "true",
        "cssUrl": "https://connect.garmin.com/gauth-custom-v1.2-min.css",
        "displayNameShown": "false",
        "embedWidget": "false",
        "gauthHost": "https://sso.garmin.com/sso",
        "generateExtraServiceTicket": "true",
        "generateNoServiceTicket": "false",
        "generateTwoExtraServiceTickets": "false",
        "globalOptInChecked": "false",
        "globalOptInShown": "true",
        "id": "gauth-widget",
        "initialFocus": "true",
        "locale": "en_US",
        "locationPromptShown": "true",
        "mobile": "false",
        "openCreateAccount": "false",
        "privacyStatementUrl": "https://www.garmin.com/en-US/privacy/connect/",
        "redirectAfterAccountCreationUrl": "https://connect.garmin.com/modern/",
        "redirectAfterAccountLoginUrl": "https://connect.garmin.com/modern/",
        "rememberMeChecked": "false",
        "rememberMeShown": "true",
        "service": "https://connect.garmin.com/modern/",
        "showConnectLegalAge": "false",
        "showPassword": "true",
        "showPrivacyPolicy": "false",
        "showTermsOfUse": "false",
        "source": "https://connect.garmin.com/signin/",
        "useCustomHeader": "false",
        "webhost": "https://connect.garmin.com/modern/",
    }

    connect_url = "https://sso.garmin.com/sso/signin"

    # We need a session to remember cookies between requests.
    session = requests.Session()
    response = session.post(
        connect_url + "?" + urlencode(connect_qs),
        headers={"Referer": connect_url},
        data={"username": username, "password": password, "embed": "false"},
    )
    response.raise_for_status()
    ticket = re.search(r'\?ticket=(.*)"', response.text).group(1)

    ticket_response = session.get(
        "https://connect.garmin.com/modern/?ticket=" + ticket,
        headers={"Referer": connect_url},
        allow_redirects=False,
    )

    return session


def find_display_name(session):
    response = session.get("https://connect.garmin.com/modern/")
    return re.search(r'displayName\\":\\"([^"]*)\\"', response.text).group(1)


def fetch_data(session, display_name, date, base_url, date_param, extra_params={}):
    if base_url.endswith("/"):
        raise ValueError("base_url must not end with a slash")

    if display_name:
        url = base_url + "/" + display_name
    else:
        url = base_url

    params = dict(**extra_params)
    if date_param is not None:
        params[date_param] = date.strftime("%Y-%m-%d")
    else:
        url += "/" + date.strftime("%Y-%m-%d")
    url = url + "?" + urlencode(params)
    logging.debug("GET " + url)
    return session.get(url).json()


def fetch_summary(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/usersummary-service/usersummary/daily",
        date_param="calendarDate",
    )


def convert_summary(date, data, tags):
    """
    Summary is a object with a whole bunch of aggregations of the whole day.
    """
    # Make some assertions to verify data.
    assert int(data["activeSeconds"]) >= 0
    assert int(data["totalSteps"]) >= 0

    copy_fields = [
        "abnormalHeartRateAlertsCount",  # can be None?
        "activeKilocalories",
        "activeSeconds",
        "activityStressDuration",
        "activityStressPercentage",
        "averageStressLevel",
        "bmrKilocalories",
        "burnedKilocalories",  # can be None
        "consumedKilocalories",  # can be None
        "dailyStepGoal",
        "floorsAscended",
        "floorsAscendedInMeters",
        "floorsDescended",
        "floorsDescendedInMeters",
        "highStressDuration",
        "highStressPercentage",
        "highlyActiveSeconds",
        "intensityMinutesGoal",
        "lastSevenDaysAvgRestingHeartRate",
        "lastSyncTimestampGMT",  # timestamp
        "lowStressDuration",
        "lowStressPercentage",
        "maxAvgHeartRate",
        "maxHeartRate",
        "maxStressLevel",
        "measurableAsleepDuration",
        "measurableAwakeDuration",
        "mediumStressDuration",
        "mediumStressPercentage",
        "minAvgHeartRate",
        "minHeartRate",
        "moderateIntensityMinutes",
        "netRemainingKilocalories",
        "remainingKilocalories",
        "restStressDuration",
        "restStressPercentage",
        "restingHeartRate",
        "sedentarySeconds",
        "sleepingSeconds",
        "stressDuration",
        "stressPercentage",
        "totalDistanceMeters",
        "totalKilocalories",
        "totalSteps",
        "totalStressDuration",
        "uncategorizedStressDuration",
        "uncategorizedStressPercentage",
        "userFloorsAscendedGoal",
        "vigorousIntensityMinutes",
        "wellnessActiveKilocalories",
        "wellnessDistanceMeters",
        "wellnessKilocalories",
    ]

    yield {
        "measurement": "summary",
        "tags": tags,
        "time": date.isoformat(),
        "fields": {key: data[key] for key in copy_fields},
    }


def fetch_activities(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/activitylist-service/activities/fordailysummary",
        date_param="calendarDate",
    )


def convert_activities(date, data, tags):
    copy_fields = [
        "activeCalories",
        "averageHR",
        "calories",
        "distance",
        "duration",
        "steps",
    ]

    for row in data:
        fields = {key: row[key] for key in copy_fields}
        fields["name"] = row["activityName"]

        yield {
            "measurement": "activity",
            "tags": tags,
            "time": row["startTimeGMT"] + "Z",
            "fields": fields,
        }


def fetch_sleep(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailySleepData",
        date_param="date",
        extra_params={"nonSleepBufferMinutes": 60},
    )


def convert_sleep(date, data, tags):
    dto = data["dailySleepDTO"]
    # levels = data["sleepLevels"]

    yield {
        "measurement": "sleep",
        "tags": tags,
        "time": dto["calendarDate"],
        "fields": {
            "awake": dto["awakeSleepSeconds"],
            "deep": dto["deepSleepSeconds"],
            "light": dto["lightSleepSeconds"],
            "nap": dto["napTimeSeconds"],
            "rem": dto["remSleepSeconds"],
            "time": dto["sleepTimeSeconds"],
        },
    }


def fetch_steps(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailySummaryChart",
        date_param="date",
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
    for row in data:
        yield {
            "measurement": "steps",
            "tags": dict(**tags, activity=row["primaryActivityLevel"]),
            "time": row["endGMT"] + "Z",
            "fields": {"steps": int(row["steps"])},
        }


def fetch_movements(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailyMovement",
        date_param="calendarDate",
    )


def fetch_heartrate(session, display_name, date):
    return fetch_data(
        session,
        display_name,
        date,
        base_url="https://connect.garmin.com/modern/proxy/wellness-service/wellness/dailyHeartRate",
        date_param="date",
    )


def convert_heartrate(date, data, tags):
    for [ts, bpm] in data["heartRateValues"]:
        if isinstance(bpm, (int, float)):
            yield {
                "measurement": "heartrate",
                "tags": tags,
                "time": datetime.utcfromtimestamp(ts / 1000).isoformat() + "Z",
                "fields": {"bpm": bpm},
            }


# broken
def fetch_weight(session, display_name, date):
    return fetch_data(
        session,
        display_name=None,  # no display_name in URL
        date=date,
        base_url="https://connect.garmin.com/modern/proxy/weight-service/weight/latest",
        date_param="date",
        extra_params={"ignorePriority": "true"},
    )


def convert_weight(date, data, tags):
    ts = data["timestampGMT"]
    weight = data["weight"]

    yield {
        "measurement": "weight",
        "tags": tags,
        "time": datetime.utcfromtimestamp(ts / 1000).isoformat() + "Z",
        "fields": {"weight": weight},
    }


def fetch_hydration(session, display_name, date):
    return fetch_data(
        session,
        display_name=None,  # no display_name in URL
        date=date,
        base_url="https://connect.garmin.com/modern/proxy/usersummary-service/usersummary/hydration/allData",
        date_param=None,  # append date to URL
    )


def convert_hydration(date, data, tags):
    copy_fields = [
        "activityIntakeInML",
        "sweatLossInML",
        "baseGoalInML",
        "goalInML",
        "valueInML",
        "lastEntryTimestampLocal",
    ]

    yield {
        "measurement": "hydration",
        "tags": tags,
        "time": date.isoformat(),
        "fields": {key: data[key] for key in copy_fields},
    }
