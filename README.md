# Berlin (BVG) and Brandenburg (VBB) transport widget for Home Assistant

Custom sensor component and lovelace card that displays upcoming departures from your defined public transport stops for Berlin and Brandenburg.

![](./docs/screenshots/timetable-card.jpg)

> I use [iOS Dark Mode Theme](https://github.com/basnijholt/lovelace-ios-dark-mode-theme) by @basnijholt, installed from [HACS](https://hacs.xyz/)

## 💿 Installation

The component consists of two parts:

1. A sensor, which tracks departures via [VBB public API](https://v5.vbb.transport.rest/api.html#get-stopsiddepartures) every 90 seconds
2. A widget (card) for the lovelace dashboard, which displays upcoming transport in a nice way

We will look at the installation of each of them separately below. But first, let's learn how to find the Stop IDs.

### How do I find my `stop_id`?

Unfortunately, I didn't have time to figure out a proper user-friendly approach of adding new components to Home Assistant, so you will have to do some routine work of finding the IDs of the nearest transport stops to you. Sorry about that :)

Simply use this URL: **https://v5.vbb.transport.rest/locations?results=1&query=alexanderplatz**

Replace `alexanderplatz` with the name of your own stop.

![](./docs/screenshots/stop-id-api.jpg)

> 🧐 **Pro tip:**
> You can also use their [location-based API](https://v5.vbb.transport.rest/api.html#get-stopsnearby) to find all stops nearby using your GPS coordinates.

### Install sensor component

**1.** Copy the whole [berlin_transport](./custom_components/) directory to the `custom_components` folder of your Home Assistant installation. If you can't find the `custom_components` directory at the same level with your `configuration.yml` — simply create it yourself and put `berlin_transport` there.

**2.** Go to Home Assistant web interface -> `Developer Tools` -> `Check and Restart` and click "Restart" button. It will reload all components in the system.

**3.** Now you can add your new custom sensor to the corresponding section in the `configuration.yml` file.

```yaml
sensor:
  - platform: berlin_transport
    departures:
      - name: "S+U Schönhauser Allee" # free-form name, only for display purposes
        stop_id: 900110001 # actual Stop ID for the API
      - name: "Stargarder Str." # you can add more that one stop to track
        stop_id: 900000110501
        
        # Optional parameter that filter out sensor stop direction by setting stop_id 
        # of any stop on a desired route.
        # stop_id can be found via the similar request:
        # [curl https://v5.vbb.transport.rest/locations\?query\=S+Hackescher+Markt | jq]
        # direction: 900000100002
        
        # Optional parameter with value in minutes that hide transport closer than N minutes
        # walking_time: 5
```

**4.** Restart Home Assistant core again and you should now see two new entities (however, it may take some time for them to fetch new data). If you don't see anything new — check the logs (Settings -> System -> Logs). Some error should pop up there.

### Add the lovelace card

When sensor component is installed and working you can add the new fancy widget for your dashboard.

**1.** Copy the [berlin-transport-timetable-card.js](./www) card module to the `www` directory of your Home Assistant. The same way you did for the sensor above. If it doesn't exist — create one.

**2.** Go to your Home Assistant dashboard, click "Edit dashboard" at the right top corner and after that in the same top right corner choose "Manage resources".

**3.** Add new resource with URL: `/local/berlin-transport-timetable-card.js` and click create. Go back to your dashboard and refresh the page.

**4.** Now you can add the custom card and integrate it with your sensor. Click "Add card -> Manual" or just go to "Raw configuration editor" and use this config.

```yaml
- type: custom:berlin-transport-timetable-card
  show_stop_name: true # show or hide the name of your stop in card title
  max_entries: 8 # number of upcoming departures to show (max: 10)
  entities:
    - sensor.stop_id_900110001 # use your entity IDs here
    - sensor.stargarder_str # they might be different from mine
```

## 🚨 Update
This update brings new sensor id generation. It will result in deactivation of sensors with the old ids. All of those inactive sensors can be manually deleted either from the lovelace card directly and refreshing the dashboard or from the entities list in `Settings`.

## 🎨 Styling

If you want to change any styles, font size or layout — the easiest way is to use [card_mod](https://github.com/thomasloven/lovelace-card-mod) component. It allows you to change any CSS classes to whatever you want.

## 👩‍💻 Technical details

This sensor uses VBB Public API to fetch all transport information.

- API docs: https://v5.vbb.transport.rest/api.html
- Rate limit: 100 req/min
- Format: [HAFAS](https://github.com/public-transport/hafas-client)

The component updates every 60-90 seconds, but it makes a separate request for each stop. That's usually enough, but I wouldn't recommend adding dozens of different stops so you don't hit the rate limit.

The VBB API is a bit unstable (as you can guess), so sometimes it gives random 503 or Timeout errors. This is normal. I haven't found how to overcome this, but it doesn't cause any problems other than warning messages in the logs.

After fetching the API, it creates one entity for each stop and writes 10 upcoming departures into `attributes.departures`. The entity state is not really used anywhere, it just shows the next departure in a human-readable format. If you have any ideas how to use it better — welcome to Github Issues.

> 🤔
> In principle, the HAFAS format is standardized in many other cities too, so you should have no problem adapting this component to more places if you wish. Check out [transport.rest](https://transport.rest/) for an inspiration.

## ❤️ Contributions

Contributions are welcome. Feel free to [open a PR](https://github.com/vas3k/home-assistant-berlin-transport/pulls) and send it to review. If you are unsure, [open an Issue](https://github.com/vas3k/home-assistant-berlin-transport/issues) and ask for advice.

## 🐛 Bug reports and feature requests

Since this is my small hobby project, I cannot guarantee you a 100% support or any help with configuring your dashboards. I hope for your understanding.

- **If you find a bug** - open [an Issue](https://github.com/vas3k/home-assistant-berlin-transport/issues) and describe the exact steps to reproduce it. Attach screenshots, copy all logs and other details to help me find the problem.
- **If you're missing a certain feature**, describe it in Issues and try to code it yourself. It's not hard. At the very least, you can try to [bribe me with a PayPal donation](https://www.paypal.com/paypalme/vas3kcom) to make the feature just for you :)

## 👮‍♀️ License

- [MIT](./LICENSE.md)
