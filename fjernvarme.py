import requests
import hashlib
import plotly.express as px
import pandas as pd
from datetime import date, datetime, timedelta
import os

FJERN_USERID = os.environ['FJERN_USERID']
FJERN_PW = os.environ['FJERN_PW']

TOKEN_URL = (
    "https://api2.dff-edb.dk/lystrup/system/"
    "getsecuritytoken/project/app/consumer/"
)
AUTH_URL = "https://api2.dff-edb.dk/lystrup/system/login/project/app/consumer/"
DATA_URL = "https://api2.dff-edb.dk/lystrup/api/getaflaestilregneark"


class fjernvarmeData:
    def __init__(self, user_id, password):
        self.user_id = user_id
        self.password = password
        self.raw_data = None
        self.data = []
        self.info = {}

    def get_raw_data(self):
        token_url = f"{TOKEN_URL}{self.user_id}"
        r = requests.get(url=token_url).json()
        token = r["Token"]
        if not token:
            raise ValueError("Invalid user ID")
        password_bytes = bytes(str(self.password), encoding="ascii")
        password_hashed = hashlib.md5(password_bytes).hexdigest()
        with_token = password_hashed + token
        id = hashlib.md5(bytes(with_token, encoding="ascii")).hexdigest()
        auth_url = f"{AUTH_URL}{self.user_id}/installation/1/id/{id}"
        r = requests.get(url=auth_url).json()
        res = r["Result"]
        if not res:
            raise ValueError("Wrong password")
        data_query = f"?id={id}&unr={self.user_id}"
        data_url = f"{DATA_URL}{data_query}"
        get_data = requests.get(url=data_url)
        if get_data.status_code == 200:
            self.raw_data = get_data.text
            print("Raw data succesfully obtained.")
        else:
            print(f"Authentication failed (Code: {get_data.status_code}).")
            raise

    def parse_raw_data(self):
        if self.raw_data:
            for i, line in enumerate(self.raw_data.split("\r\n")):
                x = line.split(";")
                if len(x) == 3:
                    self.info[x[0]] = x[1]
                elif len(x) == 31:
                    if "Målernummer" not in x:
                        self.info["Målernummer"] = int(x[0])
                    date = datetime.strptime(x[1], "%d-%m-%Y").date()
                    desc = x[2]
                    total = int(x[3])
                    usage = int(x[4]) if x[4] else 0
                    cum_hours = int(x[10])
                    hours = int(x[11]) if x[11] else 0
                    self.data.append([date, desc, total, usage, cum_hours, hours])
            print("Data succesfully parsed.")
        else:
            print("No raw data available. Nothing was parsed.")

    def save_data(self, filename=f"fjernvarmedata_{date.today()}"):
        if self.data:
            with open(f"{filename}.csv", "w") as f:
                f.write("date;type;total;usage;cum_hours;hours\n")
                for row in self.data:
                    for i, item in enumerate(row):
                        if i == 0:
                            f.write(item.strftime('%d-%m-%Y'))
                        else:
                            f.write(str(item))
                        f.write(";")
                    f.write("\n")
            print("Data succesfully saved.")
        else:
            print("No parsed data available. Nothing was saved.")

    def load_data(self, filename):
        with open(filename) as f:
            self.data = []
            for i, line in enumerate(f.read().split("\n")):
                if i == 0 or not line:
                    continue
                date, desc, total, usage, cum_hours, hours, _ = line.split(";")
                date = datetime.strptime(date, "%d-%m-%Y").date()
                total = int(total)
                usage = int(usage)
                cum_hours = int(cum_hours)
                hours = int(hours)
                self.data.append([date, desc, total, usage, cum_hours, hours])


fjernvarme = fjernvarmeData(user_id=FJERN_USERID, password=FJERN_PW)
fjernvarme.get_raw_data()
fjernvarme.parse_raw_data()
daily_data = pd.DataFrame(fjernvarme.data, columns=['date', 'desc', 'total', 'usage', 'cum_hours', 'hours'])
daily_data = daily_data[daily_data['desc'] == 'Mellemafl.']
years = set(map(lambda x: x.year, daily_data['date']))
months = set(map(lambda x: x.month, daily_data['date']))
monthly_data = []

for year in years:
    for month in months:
        w = [(x.month == month) & (x.year == year) for x in daily_data['date']]
        s = sum(daily_data[w]['usage'])
        if s:
            monthly_data.append((date(year, month, 1), s))

monthly_data = pd.DataFrame(monthly_data, columns=['date', 'usage'])


def make_plot(data, range_dates=None, daily=True):
    if range_dates:
        data = data[(range_dates[0] <= data['date']) & (data['date'] <= range_dates[1])]
    if data.size == 0:
        return None
    if daily:
        fig = px.scatter(data, x='date', y='usage', color='hours', labels={"date": "Dato", "usage": "Forbrug (kWh)"}, color_continuous_scale='agsunset')
    else:
        fig = px.scatter(data, x='date', y='usage', labels={"x": "Dato", "y": "Forbrug (kWh)"})
    return fig


today = datetime.today()
last_day_prev_month = today.replace(day=1) - timedelta(days=1)
current_month = (date(today.year, today.month, 1), today.date())
prev_month = (date(last_day_prev_month.year, last_day_prev_month.month, 1), last_day_prev_month.date())
current_year = (date(today.year, 1, 1), today.date())
figs = []

fig1 = make_plot(daily_data, range_dates=current_month)
if fig1:
    fig1.update_layout(title_text="Forbrug per dag i indeværende måned", title_x=0.5, coloraxis_colorbar=dict(title="Antal timer", tickvals=[0, 10, 20, 30, 40, 50]))
    figs.append(fig1)

fig2 = make_plot(daily_data, range_dates=prev_month)
fig2.update_layout(title_text="Forbrug per dag i forrige måned", title_x=0.5, coloraxis_colorbar=dict(title="Antal timer", tickvals=[0, 10, 20, 30, 40, 50]))
figs.append(fig2)

fig3 = make_plot(daily_data, range_dates=current_year)
fig3.update_layout(title_text="Forbrug per dag i indeværende år", title_x=0.5, coloraxis_colorbar=dict(title="Antal timer", tickvals=[0, 10, 20, 30, 40, 50]))
figs.append(fig3)

fig4 = make_plot(daily_data)
fig4.update_layout(title_text="Forbrug per dag altid", title_x=0.5, coloraxis_colorbar=dict(title="Antal timer", tickvals=[0, 10, 20, 30, 40, 50]))
figs.append(fig4)

fig5 = make_plot(monthly_data, range_dates=current_year, daily=False)
fig5.update_layout(title_text="Forbrug per måned i indeværende år", title_x=0.5)
figs.append(fig5)

fig6 = make_plot(monthly_data, daily=False)
fig6.update_layout(title_text="Forbrug per måned altid", title_x=0.5)
figs.append(fig6)

with open('index.html', 'w') as f:
    for fig in figs:
        f.write(fig.to_html(full_html=False))
