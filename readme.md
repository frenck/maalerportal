# Målerportal

This is a custom component for Home Assistant to integrate Målerportal.

Requires Home Assistant **2025.11** or newer.

## Prerequisites

1. HACS is installed.<br/>
   Guide: https://www.hacs.xyz/docs/use/configuration/basic/#to-set-up-the-hacs-integration<br/>
   Guide docker: https://www.simplysmart.house/blog/how-to-install-HACS-on-home-assistant-Docker
2. An API key from the Målerportal consumer app. Open https://consumer.meterportal.eu, go to **Menu → Smart Home → Create API key** and copy the key. It is shown only once, so keep it until the integration is set up.

## Installation

- Go to "HACS" on the left-hand side of the Home Assistant dashboard
- Click the button in the top right corner <br/>
    ![alt text](documentation/image.png)
- Add this repository (https://github.com/maalerportal/maalerportal) as a custom repository<br/>
![alt text](documentation/image2.png)
- After clicking the add button
- Press the X button
- Search for and download the "Målerportal" integration.
- Restart Home Assistant.
- After the restart go to "Settings" → "Devices & Services" → "Add Integration"
- Search and click on "Målerportal"
- Paste your API key
- Select which meters you want to add to Home Assistant (you can always add more later)
- **Wait 1-2 minutes** for the integration to fetch your historical meter data

**Note:** The first data fetch may take a few minutes as it retrieves up to 30 days of historical readings for the Energy Dashboard.

## Configuration

### Update interval

Click **Configure** on the integration entry to set how often readings are fetched from Målerportal (15 to 120 minutes, default 30). The virtual meter of a consumption-type meter is refreshed at most once an hour.

To fetch readings right away, run the **Refresh meter readings** action (`maalerportal.refresh`) from **Developer tools → Actions**. Leave **Installation ID** empty to refresh every meter.

### Replacing the API key

- If Målerportal rejects the key because it was deleted or expired, the integration shows **Attention required**. Open it and paste a new key from the consumer app in the **Update Målerportal API key** dialog. Your entities, entity IDs and Energy Dashboard history are kept.
- To rotate the key before it stops working, open the three-dot menu on the integration entry and choose **Reconfigure**. The **Replace Målerportal API key** dialog takes the new key.

## Sensor types

The integration creates the following sensors, depending on what each meter reports:

| Applies to | Sensors created |
|------------|-----------------|
| **Meters that report a cumulative reading** (water, heat and some electricity meters) | Meter reading, Energy Dashboard sensor |
| **Meters that report consumption per period** (most electricity meters, some water meters) | Virtual meter reading, Energy Dashboard sensor |
| **Heat, when the meter reports them** | Supply temperature, Return temperature, Temperature difference, Heat power, Heat volume |
| **All meters, when the meter reports them** | Price per unit, Battery days remaining, ambient and water temperature (min/max), flow (min/max) |
| **Meters with more than one counter** | Meter reading and Energy Dashboard sensor for each extra cold water, hot water, electricity or heat counter |
| **All meters, diagnostics** | Last contact with Målerportal, Last reading from meter |

**Note:** Sensors marked "(Energy Dashboard)" or "(Energi-dashboard)" are specifically designed for use with Home Assistant's Energy Dashboard and contain historical data.

### Units

Units follow what your utility reports to Målerportal: water in m³ or L, energy in kWh, MWh or GJ, flow in L/h or m³/h. The integration never converts values itself. Home Assistant converts history when a unit changes, and on water, energy and flow sensors you can pick a display unit under the entity's settings. A unit Home Assistant does not accept for that sensor's device class is shown as sent, without a device class. If Home Assistant knows the unit but not for that kind of sensor, a warning in the log names the meter counter; otherwise the detail is in the debug log.

### The two diagnostic timestamps

- **Last contact with Målerportal** is the last time Home Assistant got a successful answer from the Målerportal API.
- **Last reading from meter** is the newest timestamp the meter itself reported.

If the first is recent and the second is old, the meter is not sending data to your utility. If both are old, Home Assistant cannot reach Målerportal.

## Add meters to your Energy Dashboard

### Electricity meters
1. Go to **Settings** → **Dashboards** → **Energy**
2. Under "Electricity grid", click **Add consumption**
3. Select the sensor ending with "El (Energy Dashboard)" or "Electricity (Energy Dashboard)"
4. For solar/export: Click **Add return to grid** and select the export sensor
5. Click **Save**

### Water meters
1. Go to **Settings** → **Dashboards** → **Energy**
2. Scroll down to "Water consumption"
3. Click **Add water source**
4. Select the sensor ending with "(Energy Dashboard)" - choose the correct one for cold or hot water
5. Click **Save**

### Heat meters
1. Go to **Settings** → **Dashboards** → **Energy**
2. Under "Gas consumption", click **Add gas source**
3. Select the heat sensor ending with "(Energy Dashboard)"
4. Click **Save**

After saving, click **"Show me my energy dashboard!"** to see your consumption data.

## Troubleshooting

- **Attention required / reauthentication:** Målerportal rejected the API key. See [Replacing the API key](#replacing-the-api-key).
- **Readings look stale:** readings are fetched at the configured update interval, every 30 minutes by default. Run the **Refresh meter readings** action to fetch now, and compare the two diagnostic timestamps to see whether Målerportal or the meter is behind.
- **Entities disappeared:** the integration removes an entity when Målerportal has stopped providing its meter counter at two consecutive startups of the integration (a Home Assistant restart, or a reload after changing the options or the API key). Entities are never removed while the API cannot be reached.
- **Visit:** the device page has a **Visit** link that opens the matching page in the consumer app.
- **Logs:** add `custom_components.maalerportal: debug` under `logger:` in `configuration.yaml` to see every request and reading.
