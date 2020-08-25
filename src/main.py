import http.server
import socketserver
from urllib.parse import urlparse
from urllib.parse import parse_qs

import re
import datetime

import icalendar as ical
from todoist.api import TodoistAPI

print('Starting service...')


class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)  # Sending an '200 OK' response

        self.send_header("Content-type", "text/calendar")  # Setting the header
        self.end_headers()

        # Extract query param
        query_components = parse_qs(urlparse(self.path).query)
        if 'token' in query_components:
            token = query_components['token'][0]
        else:
            token = open('./config/todoist_token', 'r').read()

        if 'default_duration' in query_components:
            default_duration = query_components['default_duration'][0]
        else:
            default_duration = '1h'

        # Regex
        task_name_regex = re.compile(r'\[(.*)\]\(.*\)', re.IGNORECASE)

        # Write iCal
        cal = ical.Calendar()
        cal.add('prodid', '-//Todoist/iCal//NONSGML v1.0//EN')
        cal.add('version', '2.0')
        cal_stamp = datetime.datetime.today()

        # Connect to Todoist API
        api = TodoistAPI(token)
        api.sync()

        # Get project dict
        projects = {project['id']: project['name'] for project in api.projects.all()}

        # Get label dict
        labels = {label['id']: label['name'] for label in api.labels.all()}

        # Get all current tasks with due dates
        tasks = api.items.all()
        for task in tasks:
            if task['due']:
                # Get labels from task
                task_label = [labels[label] for label in task['labels']]

                # Remove links from task name
                task_name = task_name_regex.sub(r'\1', task['content'])

                # Calculate duration from labels
                duration = next((label for label in task_label if re.search(r'\dm|\dh|$', str(label)).group()), default_duration)
                duration_int = int(re.search('\d+', duration).group())
                duration_timedelta = datetime.timedelta(minutes=duration_int) if duration.endswith('m') else datetime.timedelta(hours=duration_int)

                # Get date from due date
                date = task['due']['date'].replace('Z', '')

                # Debug
                print(f'{task_name}\t|\t{duration}\t|\t{date}')

                # Summarize task properties
                event_summary = f'{task_name} [{projects[task["project_id"]]}]'
                event_start = datetime.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S') if 'T' in date else datetime.datetime.strptime(date, '%Y-%m-%d')
                event_start_uid = re.sub(r'\D', '', str(event_start))
                event_end = event_start + duration_timedelta if 'T' in date else event_start + datetime.timedelta(days=1)

                event = ical.Event()
                event.add('summary', event_summary)
                event.add('dtstart', event_start)
                event.add('dtend', event_end)
                event.add('dtstamp', cal_stamp)
                event.add('uid', f'{task["id"]}{event_start_uid}')
                cal.add_component(event)

        # Writing the HTML contents with UTF-8
        print(cal.to_ical())
        self.wfile.write(cal.to_ical())

        return


# Create an object of the above class
handler_object = MyHttpRequestHandler

PORT = 4000
my_server = socketserver.TCPServer(("", PORT), handler_object)

# Star the server
my_server.serve_forever()
